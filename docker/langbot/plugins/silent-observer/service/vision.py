"""视觉识别服务 — URL-first 策略 + 熔断器 + 每日配额."""
import asyncio, base64, sys, time
from datetime import timedelta

from langbot_plugin.api.entities.builtin.provider import message as provider_message

from util.image import open_image, resize_image
from util.logs import safe_log
from util.text import clean_description

_ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
_MAX_PIXELS = 1024 * 1024


class VisionService:
    def __init__(self, plugin, vision_model_uuid: str, vision_daily_limit: int,
                 vision_max_images: int = 5, daily_count_ref: list | None = None,
                 daily_date_ref: list | None = None, fail_streak_ref: list | None = None,
                 circuit_open_ref: list | None = None, stats_ref: dict | None = None):
        self._plugin = plugin
        self.vision_model_uuid = vision_model_uuid
        self.vision_daily_limit = vision_daily_limit
        self.vision_max_images = vision_max_images
        # 可变状态（通过引用共享，由主类持久化）
        self._daily_count = daily_count_ref or [0]
        self._daily_date = daily_date_ref or [None]
        self._fail_streak = fail_streak_ref or [0]
        self._circuit_open_until = circuit_open_ref or [None]
        self._stats = stats_ref or {'total': 0, 'success': 0, 'fail': 0, 'total_tokens': 0}
        self._semaphore: asyncio.Semaphore | None = None  # lazy init

    @property
    def stats(self) -> dict:
        return self._stats

    def _has_image(self, message_chain) -> bool:
        if message_chain is None:
            return False
        for c in message_chain:
            if c.type == 'Image':
                return True
            if c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None and self._has_image(origin):
                    return True
        return False

    def _collect_images(self, message_chain) -> list:
        """收集 message_chain 中所有 Image 组件，返回 [(chain_index, component)]"""
        result = []
        if message_chain is None:
            return result
        for i, c in enumerate(message_chain):
            if c.type == 'Image':
                result.append((i, c))
            elif c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    result.extend(self._collect_images(origin))
        return result

    async def describe_images(self, message_chain, trace_id: str = '') -> dict:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(2)
        imgs = self._collect_images(message_chain)
        if not imgs:
            return {}
        model_uuid = self.vision_model_uuid
        result = {}
        tasks = []
        for idx, img in imgs[:self.vision_max_images]:
            tasks.append(self._describe_one(idx, img, model_uuid, trace_id))
        if tasks:
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, _), r in zip(imgs[:self.vision_max_images], gathered):
                if isinstance(r, Exception):
                    safe_log('gate', f'[{trace_id}] vision: img[{idx}] exception {type(r).__name__}: {str(r)[:120]}')
                    result[idx] = '[图片]'
                else:
                    result[idx] = r
        for idx, _ in imgs[self.vision_max_images:]:
            result[idx] = '[图片(略)]'
        for idx, _ in imgs:
            if idx not in result:
                result[idx] = '[图片]'
        return result

    async def _describe_one(self, idx, img, model_uuid, trace_id):
        t_start = time.time()
        logs: list[str] = []

        # URL-first 策略
        img_url = getattr(img, 'url', None) or ''
        if img_url:
            try:
                t_api_start = time.time()
                async with self._semaphore:
                    resp = await asyncio.wait_for(
                        self._plugin.invoke_llm(
                            llm_model_uuid=model_uuid,
                            messages=[
                                provider_message.Message(
                                    role='user',
                                    content=[
                                        provider_message.ContentElement.from_text(
                                            '请用一句话描述这张图片的内容（直接描述，不要前缀如"这张图片"）。'),
                                        provider_message.ContentElement.from_image_url(img_url),
                                    ]
                                )
                            ],
                        ),
                        timeout=45,
                    )
                t_total = time.time() - t_start
                raw_text = self._extract_llm_text(resp)
                desc = clean_description(raw_text)
                safe_log('gate', f'[{trace_id}] vision: img[{idx}] url_ok lat={t_total:.1f}s desc="{desc}"')
                self._record_vision_result(True)
                return desc
            except Exception as e:
                safe_log('gate', f'[{trace_id}] vision: img[{idx}] url failed ({type(e).__name__}: {str(e)[:80]}), fallback to base64')

        # base64 fallback
        try:
            bytes_data, mime = await asyncio.wait_for(img.get_bytes(), timeout=5)
            t_get = time.time() - t_start
        except asyncio.TimeoutError:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] get_bytes timeout')
            return '[图片(下载失败)]'
        except Exception as e:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] get_bytes error {type(e).__name__}: {str(e)[:120]}')
            return '[图片(下载失败)]'

        if mime not in _ALLOWED_MIME:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] mime={mime} not allowed')
            return '[图片(不支持的格式)]'
        if not bytes_data:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] empty bytes')
            return '[图片(空)]'

        need_resize = False
        try:
            img_obj = open_image(bytes_data)
            w, h = img_obj.size
            if w > 1024 or h > 1024 or w * h > _MAX_PIXELS:
                need_resize = True
            img_obj.close()
        except Exception:
            need_resize = False

        if need_resize:
            try:
                loop = asyncio.get_running_loop()
                bytes_data = await loop.run_in_executor(None, resize_image, bytes_data)
            except Exception as e:
                safe_log('gate', f'[{trace_id}] vision: img[{idx}] resize error {type(e).__name__}')
                return '[图片(处理错误)]'

        b64 = base64.b64encode(bytes_data).decode('ascii')
        if len(b64) > 10 * 1024 * 1024:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] base64 too large ({len(b64) // 1024}KB)')
            return '[图片过大]'

        data_uri = f'data:{mime};base64,{b64}'
        try:
            t_api_start = time.time()
            async with self._semaphore:
                resp = await asyncio.wait_for(
                    self._plugin.invoke_llm(
                        llm_model_uuid=model_uuid,
                        messages=[
                            provider_message.Message(
                                role='user',
                                content=[
                                    provider_message.ContentElement.from_text(
                                        '请用一句话描述这张图片的内容（直接描述，不要前缀如"这张图片"）。'),
                                    provider_message.ContentElement.from_image_base64(data_uri),
                                ]
                            )
                        ],
                    ),
                    timeout=45,
                )
            t_api = time.time() - t_api_start
            raw_text = self._extract_llm_text(resp)
            desc = clean_description(raw_text)
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] b64_ok get={t_get:.1f}s llm={t_api:.1f}s desc="{desc}"')
            self._record_vision_result(True)
            return desc
        except asyncio.TimeoutError:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] llm timeout')
            self._record_vision_result(False)
            return '[图片(超时)]'
        except Exception as e:
            safe_log('gate', f'[{trace_id}] vision: img[{idx}] llm_fail {type(e).__name__}: {str(e)[:120]}')
            self._record_vision_result(False)
            return '[图片]'

    @staticmethod
    def _extract_llm_text(resp) -> str:
        """从 invoke_llm 返回值中提取文本"""
        if resp is None:
            return ''
        if isinstance(resp, str):
            return resp
        content = getattr(resp, 'content', None)
        if content is None:
            return str(resp) if resp else ''
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for c in content:
                if hasattr(c, 'text') and c.text:
                    parts.append(c.text)
                elif isinstance(c, dict) and c.get('type') == 'text':
                    parts.append(c.get('text', ''))
            return ' '.join(parts)
        return str(content) if content else ''

    def _record_vision_result(self, success: bool):
        self._stats['total'] += 1
        if success:
            self._stats['success'] += 1
            self._fail_streak[0] = 0
        else:
            self._stats['fail'] += 1
            self._fail_streak[0] += 1
            if self._fail_streak[0] >= 5:
                from datetime import datetime, timezone, timedelta
                BJT = timezone(timedelta(hours=8))
                self._circuit_open_until[0] = datetime.now(BJT) + timedelta(minutes=5)
                print(f'[silent] WARNING vision: circuit opened ({self._fail_streak[0]} consecutive failures)',
                      file=sys.stderr, flush=True)

    def check_quota(self) -> bool:
        from datetime import datetime, timezone, timedelta
        BJT = timezone(timedelta(hours=8))
        today = datetime.now(BJT).date()
        if self._daily_date[0] != today:
            self._daily_count[0] = 0
            self._daily_date[0] = today
        if self._circuit_open_until[0] and datetime.now(BJT) < self._circuit_open_until[0]:
            safe_log('gate', f'vision: circuit open until {self._circuit_open_until[0].strftime("%H:%M:%S")}')
            return False
        if self.vision_daily_limit > 0 and self._daily_count[0] >= self.vision_daily_limit:
            safe_log('gate', f'vision: daily limit reached ({self._daily_count[0]}/{self.vision_daily_limit})')
            return False
        self._daily_count[0] += 1
        return True
