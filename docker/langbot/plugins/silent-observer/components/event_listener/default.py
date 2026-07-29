import asyncio, base64, io, json, random, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
BJT = timezone(timedelta(hours=8))
_DB_PATH = '/app/data/plugins/dou__langbot-silent-observer/chat_index.db'

from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.platform.message import Plain as PlatformPlain
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

from util.face import QQ_FACE_NAME, extract_faces, face_to_text, is_face_component, normalize_face_components
from util.image import open_image, resize_image
from util.logs import safe_log
from util.text import ROLE_CN, build_document_id, build_msg_metadata, clean_description, format_timeline, norm_role
from store import KBStore
from service.vision import VisionService
from service.timeline import TimelineService
from service.quote import QuoteService
from service.retrieval import RetrievalService

# 兼容旧代码的别名
_QQ_FACE_NAME = QQ_FACE_NAME
_ROLE_CN = ROLE_CN
_log_gate = lambda msg: safe_log('gate', msg)
_build_document_id = build_document_id
_build_msg_metadata = build_msg_metadata
_format_timeline = format_timeline
_norm_role = norm_role
_resize_image = resize_image
_clean_description = clean_description

def _get_db():
    """获取 SQLite 连接（WAL + 超时，防并发锁）"""
    db = sqlite3.connect(_DB_PATH, timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    return db

def _now():
    return datetime.now(BJT)


class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()
        # 修复 LangBot 缺少 Face 组件注册的 bug
        from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Face as LangBotFace
        _orig = MessageChain._get_component_types.__func__
        def _patched(cls):
            types = _orig(cls)
            if 'Face' not in types:
                types['Face'] = LangBotFace
            return types
        MessageChain._get_component_types = classmethod(_patched)
        config = self.plugin.get_config()
        self.bot_qq = str(config.get('bot_qq', ''))
        self.prob = float(config.get('reply_probability', 0.01))
        self.history_count = int(config.get('history_count', 20))
        self.timeline_max_chars = int(config.get('timeline_max_chars', 2000))
        self.vision_max_images = int(config.get('vision_max_images', 5))
        kb_id = str(config.get('kb_id', ''))
        emb_uuid = str(config.get('embedding_model_uuid', ''))
        if kb_id and emb_uuid:
            self.kb_enabled = True
            self.kb_id = kb_id
            self.embedding_model_uuid = emb_uuid
            self.store = KBStore(self.plugin, kb_id, emb_uuid, _DB_PATH)
        else:
            self.kb_enabled = False
            self.kb_id = ''
            self.embedding_model_uuid = ''
            self.store = None
            if kb_id or emb_uuid:
                print('[silent] WARNING: kb_id and embedding_model_uuid must both be set, KB disabled', file=sys.stderr, flush=True)
        self.vision_enabled = bool(config.get('vision_enabled', False))
        self.vision_model_uuid = str(config.get('vision_model_uuid', ''))
        self.vision_all_messages = bool(config.get('vision_all_messages', False))
        self.vision_daily_limit = int(config.get('vision_daily_limit', 0))
        self.debug_dump = bool(config.get('debug_dump', False))
        if self.vision_enabled and not self.vision_model_uuid:
            print('[silent] WARNING: vision_enabled=true but vision_model_uuid empty, disabling', file=sys.stderr, flush=True)
            self.vision_enabled = False
        if self.vision_enabled and self.vision_model_uuid:
            try:
                models = await self.plugin.list_llm_models()
                match = [m for m in models if m.get('uuid') == self.vision_model_uuid and 'vision' in (m.get('abilities') or [])]
                if not match:
                    print(f'[silent] WARNING: model {self.vision_model_uuid} not found or lacks vision, disabling', file=sys.stderr, flush=True)
                    self.vision_enabled = False
            except Exception as e:
                print(f'[silent] WARNING: cannot verify vision model: {e}, keeping enabled', file=sys.stderr, flush=True)
        if self.vision_all_messages and not self.vision_enabled:
            print('[silent] INFO: vision_all_messages=true ignored (vision_enabled=false)', file=sys.stderr, flush=True)
        # 状态默认值（持久化前）
        self._vision_daily_count = 0
        self._vision_daily_date = _now().date()
        self._vision_fail_streak = 0
        self._vision_circuit_open_until = None
        self._vision_stats = {'total': 0, 'success': 0, 'fail': 0, 'total_tokens': 0}
        self._last_trigger = {}
        self._lock_set_ts = {}
        self._reply_ts = {}
        self._last_msg_ts = {}
        self._gate_hits = 0
        self._gate_misses = 0
        self._lock_skips = 0
        self._inject_random = 0
        self._inject_at = 0
        self._stats_start = time.time()

        # 持久化：恢复上次运行时状态
        from store import StateStore
        self._state_store = StateStore(self.plugin)
        saved = await self._state_store.load()
        if saved:
            self._restore_state(saved)

        # 服务层初始化（依赖注入，使用恢复后的状态值）
        self.vision_service = VisionService(
            self.plugin, self.vision_model_uuid, self.vision_daily_limit,
            vision_max_images=self.vision_max_images,
            daily_count_ref=[self._vision_daily_count],
            daily_date_ref=[self._vision_daily_date],
            fail_streak_ref=[self._vision_fail_streak],
            circuit_open_ref=[self._vision_circuit_open_until],
            stats_ref=self._vision_stats,
        )
        self.timeline_service = TimelineService(self.timeline_max_chars, self.history_count)
        self.quote_service = QuoteService(self.timeline_service.extract_text)
        self.retrieval_service = RetrievalService(self.store, self.timeline_max_chars, self.history_count) if self.store else None

        # 运行时状态（不持久化）
        self._image_cache = {}
        self._reply_pending = {}
        self._reply_tasks = {}
        self._face_cache = {}
        self._bg_queue = asyncio.Queue(maxsize=10)
        self._bg_workers = [asyncio.create_task(self._bg_worker()) for _ in range(3)]

        # 周期持久化（每 5 分钟）
        asyncio.create_task(self._periodic_save())

        init_msg = f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count} kb_enabled={self.kb_enabled} vision_enabled={self.vision_enabled}'
        if saved:
            init_msg += f' [restored: gate={self._gate_hits}/{self._gate_misses} vision={self._vision_daily_count}]'
        print(init_msg, file=sys.stderr, flush=True)
        try:
            with open('/tmp/silent_init.log', 'w') as f:
                f.write(init_msg + '\n')
        except:
            pass

        if self.kb_enabled:
            self.store.init_chat_index()

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            session_name = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            self._strip_base64(ctx.event.message_chain)
            is_at = self._has_at(ctx.event.message_chain)
            is_trigger = is_at or random.random() < self.prob
            # 引用图片检测（轻量同步，不调 API）
            quote_has_img = self._quote_has_image(ctx.event.message_chain)
            # 提取引用文本 + 表情文本（gate 阶段有 message_chain，inject 阶段没有）
            quote_text = await self._extract_quote(ctx.event.message_chain)
            face_text = self._extract_faces(ctx.event.message_chain)
            if face_text:
                self._face_cache[session_name] = face_text
            if is_trigger and self.kb_enabled:
                doc_id = await self._save_text_only(ctx.event)
                has_img = self._has_image(ctx.event.message_chain)
                has_img_in_quote = quote_has_img
                if doc_id and self.vision_enabled and (has_img or has_img_in_quote):
                    self._image_cache[doc_id] = {'status': 'pending', 'desc': '[图片]', 'time': time.time()}
                    self._run_background(self._save_with_vision(ctx.event, doc_id))
                trigger = 'at' if is_at else 'random'
                locked = session_name in self._last_trigger and not is_at
                if not locked:
                    self._last_trigger[session_name] = (trigger, doc_id, ctx.event.message_chain)
                    self._lock_set_ts[session_name] = time.time()
                else:
                    self._lock_skips += 1
                    self._log_event('lock_skip', session_name, doc_id=doc_id)
                self._gate_hits += 1
                self._log_event('hit', session_name, trigger=trigger, locked=str(locked), doc_id=doc_id)
                gate_msg = f'[silent] gate: allowed ({trigger}) doc_id={doc_id}'
                print(gate_msg, file=sys.stderr, flush=True)
                try:
                    with open('/tmp/silent_gate.log', 'a') as f:
                        f.write(gate_msg + '\n')
                except:
                    pass
            elif is_trigger:
                doc_id = await self._save_text_only(ctx.event)
                trigger = 'at' if is_at else 'random'
                locked = session_name in self._last_trigger and not is_at
                if not locked:
                    self._last_trigger[session_name] = (trigger, doc_id, ctx.event.message_chain)
                    self._lock_set_ts[session_name] = time.time()
                else:
                    self._lock_skips += 1
                    self._log_event('lock_skip', session_name, doc_id=doc_id)
                self._gate_hits += 1
                self._log_event('hit', session_name, trigger=trigger, locked=str(locked), doc_id=doc_id)
                gate_msg = f'[silent] gate: allowed ({trigger}) [no kb]'
                print(gate_msg, file=sys.stderr, flush=True)
                try:
                    with open('/tmp/silent_gate.log', 'a') as f:
                        f.write(gate_msg + '\n')
                except:
                    pass
            else:
                if self.kb_enabled:
                    doc_id = await self._save_text_only(ctx.event)
                    if doc_id and self.vision_enabled and self.vision_all_messages and self._has_image(ctx.event.message_chain):
                        self._image_cache[doc_id] = {'status': 'pending', 'desc': '[图片]', 'time': time.time()}
                        self._run_background(self._save_with_vision(ctx.event, doc_id))
                    elif doc_id:
                        self._run_background(self._save_and_store(ctx.event))
                self._gate_misses += 1
                self._log_event('miss', session_name)
                try:
                    with open('/tmp/silent_gate.log', 'a') as f:
                        f.write(f'[silent] gate: prevented\n')
                except: pass
                print(f'[silent] gate: prevented (is_at=False)', file=sys.stderr, flush=True)
                ctx.prevent_default()

        @self.handler(events.NormalMessageResponded)
        async def save_reply(ctx: context.EventContext):
            # 流式去重：同一 session 1 秒内只存第一条
            session_name = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            _ts = time.time()
            _last = self._reply_ts.get(session_name, 0)
            self._reply_ts[session_name] = _ts
            if _ts - _last < 1.0:
                return
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            if self.kb_enabled:
                time_str = _now().strftime('%Y-%m-%d %H:%M')
                meta = _build_msg_metadata(session_name, '机器豆', '0', time_str, text, 'BOT', '')
                doc_id = _build_document_id(session_name, time_str, '0', text)
                self._run_background(self.store.store_message(meta, doc_id))
            self._last_trigger.pop(session_name, None)
            print(f'[silent] bot reply saved: {text[:30]}', file=sys.stderr, flush=True)

        @self.handler(events.PromptPreProcessing)
        async def inject(ctx: context.EventContext):
            with open('/tmp/silent_gate.log', 'a') as f:
                f.write('[silent] inject START\n')
            # Face → Plain 替换：防 pipeline 渲染成 [Unknown]
            # 注：inject 阶段 mc 始终为 None（PromptPreProcessing 不携带 message_chain），
            # 但 _extract_text（gate 同步执行）已将 Face 文本写入 chat_index，timeline 携带表情信息。
            mc = getattr(ctx.event, 'message_chain', None)
            if mc:
                self._normalize_face_components(mc)
            # 同时注入 UTC 和北京时间,消除时区歧义(防 LLM 时区幻觉)
            now_bj = _now()
            now_utc = now_bj.astimezone(timezone.utc)
            now_str = (
                f'北京时间 {now_bj.strftime("%Y-%m-%d %H:%M:%S")} '
                f'(UTC {now_utc.strftime("%H:%M:%S")})'
            )
            ctx.event.prompt.append(provider_message.Message(role='system', content=f'当前时间:{now_str}。以下【】中所有时间戳均为北京时间,禁止转换为UTC或其他时区。'))
            items = []
            trigger = 'at'
            try:
                session_name = ctx.event.session_name
                # 注入 gate 阶段提取的表情文本（inject 阶段无 message_chain，必须在 KB 检查前注入）
                face_text = self._face_cache.pop(session_name, '')
                if face_text:
                    ctx.event.prompt.append(provider_message.Message(role='system', content=f'[表情] 用户发送了 QQ 表情：{face_text}'))
                trigger_info = self._last_trigger.pop(session_name, ('at', None, ''))
                if isinstance(trigger_info, tuple):
                    trigger = trigger_info[0]
                    trigger_doc_id = trigger_info[1] if len(trigger_info) > 1 else None
                    trigger_mc = trigger_info[2] if len(trigger_info) > 2 else None
                    quote_text = await self.quote_service.extract(trigger_mc) if trigger_mc else ''
                else:
                    trigger, trigger_doc_id, trigger_mc = trigger_info, None, None
                    quote_text = await self.quote_service.extract(trigger_mc) if trigger_mc else ''

                if not self.kb_enabled or not self.kb_id:
                    return

                api = QueryBasedAPIProxy(
                    query_id=ctx.query_id,
                    plugin_runtime_handler=self.plugin.plugin_runtime_handler,
                )

                # 等待当前消息的 vision 识图完成（防时序竞态：inject 先于 vision upsert）
                if trigger_doc_id and self.vision_enabled:
                    for _ in range(60):  # 最多等 60s
                        cached = self._image_cache.get(trigger_doc_id)
                        if cached and cached['status'] == 'done':
                            break
                        await asyncio.sleep(0.5)
                items = await self.store.get_recent_messages(session_name, 200)
                if items:
                    items.sort(key=lambda i: i.get('metadata', {}).get('timestamp_unix', 0))
                    if trigger_doc_id:
                        items = [i for i in items if i.get('id') != trigger_doc_id]
                    items = items[-self.history_count:]

                lines = _format_timeline(items)
                # 去重：连续相同 bot 消息只保留第一条（防 relay 重复污染 + 自我引用级联放大）
                _deduped = []
                for _l in lines:
                    if not _deduped or _l != _deduped[-1]:
                        _deduped.append(_l)
                lines = _deduped

                # 字符数限制：从最旧开始丢弃完整消息
                max_chars = self.timeline_max_chars
                total_chars = sum(len(l) for l in lines)
                while lines and total_chars > max_chars:
                    total_chars -= len(lines.pop(0))

                # 🔖 强化 timeline 中图片识别标记（仅行内标记，不追加全局总结防 LLM 混淆）
                import re
                _identified = 0
                _pending = 0
                _failed = 0
                for _i, _line in enumerate(lines):
                    if '🖼️ 图' not in _line:
                        continue
                    _idx = _line.index('🖼️ 图')
                    _pfx = _line[:_idx]
                    _rest = _line[_idx:]
                    if '：⏳ 识别中' in _rest:
                        lines[_i] = _pfx + _rest.replace('🖼️ 图', '⏳ [AI识图中] 图', 1)
                        _pending += 1
                    else:
                        _m = re.match(r'🖼️ 图\d+：\[图片([^\]]*)\]', _rest)
                        if _m:
                            _img_prefix = _rest[:_rest.index('：')]
                            _desc = _m.group(1).strip()
                            if _desc.startswith('('):
                                _reason = _desc.strip('()')
                                lines[_i] = _pfx + _rest.replace('🖼️ 图', f'❌ [AI识图失败:{_reason}] 图', 1)
                                _failed += 1
                            else:
                                _img_prefix_new = _img_prefix.replace('🖼️ 图', '🤖 [AI识图] 图', 1)
                                _after = _rest[len(f'{_img_prefix}：[图片{_desc}]'):]
                                lines[_i] = _pfx + f'{_img_prefix_new}：[{_desc}]' + _after
                                _identified += 1

                # DEBUG: dump prompt for analysis
                query_vars2 = await api.get_query_vars()
                at_text2 = str(query_vars2.get('user_message_text', '') or '')
                try:
                    with open('/tmp/silent_prompt_dump.log', 'a') as f:
                        f.write(f'\n=== PROMPT DUMP [{_now().strftime("%H:%M:%S")}] ===\n')
                        f.write(f'[1] time: {now_str}\n')
                        f.write(f'[2] trigger: {trigger}\n')
                        f.write(f'[3] ai_identified={_identified} ai_pending={_pending} ai_failed={_failed}\n')
                        f.write(f'[4] timeline ({len(lines)} lines):\n' + '\n'.join(lines) + '\n')
                        f.write(f'[5] user: {at_text2[:200]}\n')
                        _face_in_timeline = sum(1 for l in lines if '[QQ表情:' in l)
                        _face_info = face_text if face_text else (f'timeline 含 {_face_in_timeline} 条' if _face_in_timeline else '(无)')
                        f.write(f'[6] face: {_face_info}\n')
                except:
                    pass

                lock_dur = time.time() - self._lock_set_ts.pop(session_name, time.time())
                self._log_event('inject', session_name, trigger=trigger, lock_dur=f'{lock_dur:.1f}s')
                if trigger == 'random':
                    self._inject_random += 1
                    ctx.event.prompt.append(provider_message.Message(role='system', content='[随机插话] 从【】内群聊历史中挑选最值得评论的话题自由发挥。'))
                    ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'))
                    ctx.event.prompt.append(provider_message.Message(role='system', content='以上是群聊历史。接下来有一条用户消息——它只是随机触发器，不是你该回复的内容。无视它，用历史中的话题回应。'))
                else:
                    self._inject_at += 1
                    query_vars = await api.get_query_vars()
                    at_text = str(query_vars.get('user_message_text', '') or '')
                    # quote_text 已在 gate 阶段从 message_chain 的 Quote 组件提取
                    _log_gate(f'[{session_name}] quote_text={quote_text[:100] if quote_text else "(empty)"}')
                    if at_text.strip():
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[@模式]'))
                        ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'))
                    elif quote_text:
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[空@模式] 用户空@了你，但引用了消息。你必须优先结合上面引用的内容直接回答（20-50字）。不要回复"在线""收到"等状态确认。'))
                        ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'))
                        trigger = 'empty_at'
                    else:
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[空@模式] 用户空@了你。你必须从【】内群聊最近记录中挑选一个具体话题直接评论（20-50字）。不要回复"在线""收到"等状态确认，不要打招呼，直接说话题。'))
                        ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'))
                        trigger = 'empty_at'

            except Exception as e:
                import traceback
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write('[silent] inject ERROR: %s\n%s\n' % (e, traceback.format_exc()))
            # 成功率日志
            stats = self._vision_stats
            if stats['total'] > 0:
                print(f'[silent] vision stats: total={stats["total"]} ok={stats["success"]} fail={stats["fail"]}', file=sys.stderr, flush=True)
            print(f'[silent] inject: timeline={len(items)} ({trigger})', file=sys.stderr, flush=True)
            # DEBUG: dump full prompt
            try:
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write(f'=== LLM RAW PROMPT [{_now().strftime("%H:%M:%S")}] ===\n')
                    for i, msg in enumerate(ctx.event.prompt):
                        role = getattr(msg, 'role', '?')
                        content = str(getattr(msg, 'content', ''))
                        f.write(f'--- [{i}] role={role} ({len(content)}c) ---\n{content}\n')
                    f.write('=== END RAW PROMPT ===\n\n')
            except:
                pass

        # 定期清理 _image_cache
        async def cache_cleanup_loop():
            while True:
                await asyncio.sleep(600)  # 每 10 分钟
                now = time.time()
                stale = [k for k, v in self._image_cache.items() if now - v['time'] > 300]
                for k in stale:
                    del self._image_cache[k]
                if stale:
                    print(f'[silent] cache cleanup: removed {len(stale)} stale entries', file=sys.stderr, flush=True)
        if self.kb_enabled:
            asyncio.create_task(cache_cleanup_loop())

        async def stats_report_loop():
            while True:
                await asyncio.sleep(60)
                elapsed = time.time() - self._stats_start
                total = self._gate_hits + self._gate_misses
                rate = self._gate_hits / total * 100 if total > 0 else 0
                try:
                    with open('/tmp/silent_stats.log', 'w') as f:
                        f.write(f'uptime: {elapsed:.0f}s\n')
                        f.write(f'gate_total: {total}\n')
                        f.write(f'gate_hits: {self._gate_hits} ({rate:.0f}%)\n')
                        f.write(f'gate_misses: {self._gate_misses}\n')
                        f.write(f'lock_skips: {self._lock_skips}\n')
                        f.write(f'inject_random: {self._inject_random}\n')
                        f.write(f'inject_at: {self._inject_at}\n')
                        f.write(f'effective_rate: {self._inject_random / total * 100:.1f}%' if total > 0 else 'effective_rate: N/A')
                except:
                    pass
        asyncio.create_task(stats_report_loop())

    def _collect_state(self) -> dict:
        """收集持久化状态。_last_trigger 剥离不可序列化的 message_chain。"""
        return {
            'vision_daily_count': self._vision_daily_count,
            'vision_daily_date': self._vision_daily_date.isoformat() if self._vision_daily_date else None,
            'vision_fail_streak': self._vision_fail_streak,
            'vision_circuit_open_until': self._vision_circuit_open_until,
            'vision_stats': self._vision_stats,
            'last_trigger': {k: [v[0], v[1]] for k, v in self._last_trigger.items()},
            'lock_set_ts': self._lock_set_ts,
            'reply_ts': self._reply_ts,
            'last_msg_ts': self._last_msg_ts,
            'gate_hits': self._gate_hits,
            'gate_misses': self._gate_misses,
            'lock_skips': self._lock_skips,
            'inject_random': self._inject_random,
            'inject_at': self._inject_at,
            'stats_start': self._stats_start,
        }

    def _restore_state(self, state: dict) -> None:
        """从持久化 dict 恢复状态。缺失字段保留默认值。"""
        self._vision_daily_count = state.get('vision_daily_count', 0)
        date_str = state.get('vision_daily_date')
        self._vision_daily_date = datetime.fromisoformat(date_str).date() if date_str else _now().date()
        self._vision_fail_streak = state.get('vision_fail_streak', 0)
        self._vision_circuit_open_until = state.get('vision_circuit_open_until')
        self._vision_stats = state.get('vision_stats', {'total': 0, 'success': 0, 'fail': 0, 'total_tokens': 0})
        self._last_trigger = {k: (v[0], v[1], None) for k, v in state.get('last_trigger', {}).items()}
        self._lock_set_ts = state.get('lock_set_ts', {})
        self._reply_ts = state.get('reply_ts', {})
        self._last_msg_ts = state.get('last_msg_ts', {})
        self._gate_hits = state.get('gate_hits', 0)
        self._gate_misses = state.get('gate_misses', 0)
        self._lock_skips = state.get('lock_skips', 0)
        self._inject_random = state.get('inject_random', 0)
        self._inject_at = state.get('inject_at', 0)
        self._stats_start = state.get('stats_start', time.time())

    async def _periodic_save(self):
        """每 5 分钟将运行时状态持久化到 plugin storage。"""
        while True:
            await asyncio.sleep(300)
            try:
                await self._state_store.save(self._collect_state())
            except Exception as e:
                print(f'[silent] periodic save failed: {e}', file=sys.stderr, flush=True)

    def _log_event(self, kind, session, **kwargs):
        now = time.time()
        gap = ''
        if session in self._last_msg_ts:
            gap = f' gap={now - self._last_msg_ts[session]:.1f}s'
        self._last_msg_ts[session] = now
        extras = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        try:
            with open('/tmp/silent_event.log', 'a') as f:
                f.write(f'{now:.3f} {session} {kind}{gap} {extras}\n')
        except:
            pass

    def _has_at(self, message_chain) -> bool:
        if message_chain is None:
            return False
        for c in message_chain:
            if c.type == 'At' and str(getattr(c, 'target', '')) == self.bot_qq:
                return True
            if c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None and self._has_at(origin):
                    return True
            if c.type == 'Forward':
                nodes = getattr(c, 'node_list', []) or []
                _log_gate(f'Forward debug: node_count={len(nodes)}, nodes={nodes}')
                for node in getattr(c, 'node_list', []) or []:
                    mc = getattr(node, 'message_chain', None)
                    if mc is not None and self._has_at(mc):
                        return True
        return False

    @staticmethod
    def _is_face_component(c):
        return is_face_component(c)

    def _extract_faces(self, message_chain):
        return extract_faces(message_chain)

    def _face_to_text(self, c):
        return face_to_text(c)

    def _normalize_face_components(self, message_chain):
        normalize_face_components(message_chain)

    async def _extract_text(self, message_chain, max_length=300, image_descriptions=None, depth=0):
        return await self.timeline_service.extract_text(message_chain, max_length, image_descriptions, depth)
    def _quote_has_image(self, message_chain) -> bool:
        return self.quote_service.has_image(message_chain)
    async def _extract_quote(self, message_chain, depth=0) -> str:
        return await self.quote_service.extract(message_chain, depth)
    async def _save_text_only(self, event):
        """只存文本到 KB，不等待识图。gate 触发路径使用。"""
        chain_types = [c.type for c in (event.message_chain or [])]
        # NapCat 收到合并转发时，message_chain 只有 ['Source']，无实际内容
        # 识别为转发群聊记录，明确标记
        is_forward_only = chain_types == ['Source']
        text = ''
        if is_forward_only:
            text = '[合并转发群聊记录]'
            _log_gate(f'_save_text_only: forward-only (Source only) from {event.sender_id}')
        else:
            text = await self.timeline_service.extract_text(event.message_chain) or getattr(event, 'text_message', '')
            if 'Unknown' in text:
                mc_types = [f'{c.type}' for c in (event.message_chain or [])]
                _log_gate(f'_save_text_only: HAS_UNKNOWN text_len={len(text)} chain_types={mc_types} text100={text[:100]}')
        sender = getattr(event.message_event, 'sender', None)
        if sender:
            sender_name = getattr(sender, 'member_name', '') or str(event.sender_id)
            sender_title = getattr(sender, 'special_title', '') or ''
            sender_role = _norm_role(getattr(sender, 'permission', None))
        else:
            sender_name = str(event.sender_id)
            sender_title = ''
            sender_role = ''
        if text.startswith('Unknown Message:') or text.strip() == f'@{self.bot_qq}':
            return None
        if len(text) > 500:
            text = text[:300] + '...[truncated]...' + text[-100:]
        session_name = f'{event.launcher_type}_{event.launcher_id}'
        time_str = _now().strftime('%Y-%m-%d %H:%M')
        doc_id = _build_document_id(session_name, time_str, str(event.sender_id), text)
        if self.kb_enabled:
            meta = _build_msg_metadata(session_name, sender_name, str(event.sender_id), time_str, text, sender_role, sender_title)
            await self.store.store_message(meta, doc_id)
            if sender_title or (sender_role and sender_role not in ('Permission.MEMBER', 'MEMBER')):
                self._run_background(self.store.backfill_sender(str(event.sender_id), sender_name, sender_title, sender_role))
        return doc_id

    async def _save_with_vision(self, event, doc_id):
        """后台识图任务。完成后 upsert KB 更新该条记录。"""
        trace_id = ''
        try:
            msg_id = str(getattr(getattr(event, 'message_event', None), 'message_id', ''))
            if msg_id:
                trace_id = f'msg_{msg_id[-12:]}'
        except:
            pass
        # 去重：检查 _image_cache 是否已有 done 结果
        cached = self._image_cache.get(doc_id)
        if cached and cached['status'] == 'done':
            _log_gate(f'[{trace_id}] vision: already done, skip')
            return
        _log_gate(f'[{trace_id}] vision: start (async)')
        try:
            image_descs = await self.vision_service.describe_images(event.message_chain, trace_id)
            text = await self.timeline_service.extract_text(event.message_chain, image_descriptions=image_descs)
            error_placeholder = lambda v: v.startswith('[图片') and ':' not in v
            ok = sum(1 for v in image_descs.values() if not error_placeholder(v))
            fail = len(image_descs) - ok
            _log_gate(f'[{trace_id}] vision: done ok={ok} fail={fail}')
            # upsert KB
            session_name = f'{event.launcher_type}_{event.launcher_id}'
            time_str = _now().strftime('%Y-%m-%d %H:%M')
            sender = getattr(event.message_event, 'sender', None)
            sender_name = getattr(sender, 'member_name', '') or str(event.sender_id) if sender else str(event.sender_id)
            sender_title = getattr(sender, 'special_title', '') or '' if sender else ''
            sender_role = _norm_role(getattr(sender, 'permission', None)) if sender else ''
            if len(text) > 500:
                text = text[:300] + '...[truncated]...' + text[-100:]
            meta = _build_msg_metadata(session_name, sender_name, str(event.sender_id), time_str, text, sender_role, sender_title)
            await self.store.store_message(meta, doc_id)
            _log_gate(f'[{trace_id}] vision: KB upserted, text len={len(meta["text"])}')
            # 更新缓存：存所有图片描述（不只用第一张）
            descs = [d for d in image_descs.values() if d != '[图片]']
            self._image_cache[doc_id] = {'status': 'done', 'desc': ' | '.join(descs) if descs else '[图片]', 'time': time.time()}
        except Exception as e:
            _log_gate(f'[{trace_id}] vision: error {type(e).__name__}: {str(e)[:120]}')
            self._image_cache[doc_id] = {'status': 'failed', 'desc': '[图片(识别失败)]', 'time': time.time()}

    async def _save_and_store(self, event):
        """非触发消息的后台归档。不等待识图。"""
        text = await self.timeline_service.extract_text(event.message_chain) or getattr(event, 'text_message', '')
        if text.startswith('Unknown Message:') or text.strip() == f'@{self.bot_qq}':
            return
        if len(text) > 500:
            text = text[:300] + '...[truncated]...' + text[-100:]
        sender = getattr(event.message_event, 'sender', None)
        if sender:
            sender_name = getattr(sender, 'member_name', '') or str(event.sender_id)
            sender_title = getattr(sender, 'special_title', '') or ''
            sender_role = _norm_role(getattr(sender, 'permission', None))
        else:
            sender_name = str(event.sender_id)
            sender_title = ''
            sender_role = ''
        session_name = f'{event.launcher_type}_{event.launcher_id}'
        time_str = _now().strftime('%Y-%m-%d %H:%M')
        doc_id = _build_document_id(session_name, time_str, str(event.sender_id), text)
        meta = _build_msg_metadata(session_name, sender_name, str(event.sender_id), time_str, text, sender_role, sender_title)
        await self.store.store_message(meta, doc_id)

    async def _store_message(self, metadata, doc_id):
        return await self.store.store_message(metadata, doc_id)

    @staticmethod
    def _strip_base64(message_chain, top_level=True):
        """仅清除 Quote/Forward 嵌套中 Image 的 base64。顶层 Image 保留 base64 供 vision 下载。
        解决 napcat Quote/Forward 内图片塞 base64 导致 WS 消息体膨胀的问题。"""
        if message_chain is None:
            return
        for c in message_chain:
            if c.type == 'Image':
                if not top_level:
                    try:
                        c.base64 = ''
                    except Exception:
                        pass
            elif c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    DefaultEventListener._strip_base64(origin, top_level=False)
            elif c.type == 'Forward':
                nodes = getattr(c, 'node_list', []) or []
                for node in nodes:
                    mc = getattr(node, 'message_chain', None)
                    if mc is not None:
                        DefaultEventListener._strip_base64(mc, top_level=False)

    def _has_image(self, message_chain) -> bool:
        return self.vision_service._has_image(message_chain)
    def _collect_images(self, message_chain):
        return self.vision_service._collect_images(message_chain)
    async def _describe_images(self, message_chain, trace_id='', max_images=5) -> dict:
        return await self.vision_service.describe_images(message_chain, trace_id)
    async def _describe_one(self, idx, img, model_uuid, trace_id):
        return await self.vision_service._describe_one(idx, img, model_uuid, trace_id)
    def _extract_llm_text(self, resp) -> str:
        return VisionService._extract_llm_text(resp)
    def _record_vision_result(self, success: bool):
        self.vision_service._record_vision_result(success)
        self._vision_fail_streak = self.vision_service._fail_streak[0]
        self._vision_circuit_open_until = self.vision_service._circuit_open_until[0]
    async def _check_vision_quota(self) -> bool:
        svc = self.vision_service
        svc._daily_count[0] = self._vision_daily_count
        svc._daily_date[0] = self._vision_daily_date
        svc._circuit_open_until[0] = self._vision_circuit_open_until
        svc.vision_daily_limit = self.vision_daily_limit
        result = svc.check_quota()
        self._vision_daily_count = svc._daily_count[0]
        self._vision_daily_date = svc._daily_date[0]
        return result
    async def _backfill_sender(self, sender_id, new_name, title, role):
        return await self.store.backfill_sender(sender_id, new_name, title, role)
    async def _get_recent_messages(self, api, session_name, limit):
        return await self.store.get_recent_messages(session_name, limit)
    async def _search_history(self, api, queries, session_name='', top_k=10):
        return await self.store.search_history(queries, session_name, top_k)

    async def _migrate_buffer_if_needed(self):
        await self.store.migrate_buffer_if_needed()
    def _run_background(self, coro):
        """将协程放入有界后台队列，由 worker pool 消费。"""
        try:
            self._bg_queue.put_nowait(coro)
        except asyncio.QueueFull:
            print('[silent] bg queue full, dropping task', file=sys.stderr, flush=True)

    async def _bg_worker(self):
        while True:
            coro = await self._bg_queue.get()
            try:
                await coro
            except Exception as e:
                print(f'[silent] bg worker error: {e}', file=sys.stderr, flush=True)
            finally:
                self._bg_queue.task_done()
