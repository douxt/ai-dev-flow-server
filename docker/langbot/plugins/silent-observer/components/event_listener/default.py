import asyncio, base64, io, json, os, random, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
BJT = timezone(timedelta(hours=8))
_DB_PATH = '/app/data/plugins/dou__langbot-silent-observer/chat_index.db'
_TIMING_LOG = '/tmp/silent_timing.log'

def _write_timing(entry: dict):
    """写计时日志（JSONL，每行一个事件）。轻量、不抛异常。"""
    try:
        entry['ts'] = time.time()
        with open(_TIMING_LOG, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass

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
from store.kb_store import canonical_session_name
from service.vision import VisionService
from service.timeline import TimelineService
from service.quote import QuoteService
from service.retrieval import RetrievalService
from store.reflection_store import ReflectionStore
from service.correction import CorrectionDetector
from service.reflection import ReflectionGenerator, ReflectionInjector, SelfReflectionScanner
from store.summary_store import SummaryStore, SummaryDocument, CompressionLogStore
from service.context_compressor import (
    split_messages, build_compression_prompt, parse_summary_response, should_compress,
    _extract_llm_text,
)

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

# 反思注入门槛。度量口径：对称归一化后 chroma l2² 距离 d = 2-2cos
# （0=同句，1=正交，2=反相关）。旧值 0.45 建立在 norm 不对称+cosine 公式错的
# 伪口径上，数学不可达（2026-08-31 探针实锤，见 docs/plans/2026-08-31-reflect-dist-norm-fix）。
# 1.4=cos≥0.3：放行实证锚点（口语查询 vs JSON doc 强相关样本 cos≈0.39/d≈1.22），
# 不相关文本典型 d≈1.6-1.8 挡外。inject candidates 攒 ≥20 条真实分布后收紧。
_REF_INJECT_MAX_DISTANCE = 1.4

# 事件日志路径（测试 monkeypatch 用，生产默认 /tmp）
_EVENT_LOG = os.environ.get('SILENT_EVENT_LOG', '/tmp/silent_event.log')

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
        self._reflection_round_count = 0  # is_trigger 轮次计数（不持久化，重启归零可接受）
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

        # === 反思层初始化 ===
        ref_enabled = bool(config.get('reflection_enabled', False)) or os.environ.get('SILENT_REFLECTION_ENABLED', '0') == '1'
        ref_model_uuid = str(config.get('reflection_model_uuid', '') or os.environ.get('SILENT_REFLECTION_MODEL_UUID', ''))
        ref_daily_limit = int(os.environ.get('SILENT_REFLECTION_DAILY_LIMIT', '0') or config.get('reflection_daily_limit', 0))
        ref_hourly_limit = int(os.environ.get('SILENT_REFLECTION_HOURLY_LIMIT', '0') or config.get('reflection_hourly_limit', 0))
        self.reflection_enabled = ref_enabled and bool(ref_model_uuid) and bool(emb_uuid)
        if self.reflection_enabled:
            self.reflection_store = ReflectionStore(self.plugin, emb_uuid)
            self.correction_detector = CorrectionDetector(self.plugin, self.bot_qq, ref_model_uuid)
            self.reflection_generator = ReflectionGenerator(self.plugin, ref_model_uuid)
            self.reflection_injector = ReflectionInjector()
            self.reflection_scanner = SelfReflectionScanner(self.plugin, ref_model_uuid)
            self._last_reply_text = {}
        else:
            self.reflection_store = None
            self.correction_detector = None
            self.reflection_generator = None
            self.reflection_injector = None
            self.reflection_scanner = None
            self._last_reply_text = {}  # always available for save_reply cache

        # 运行时状态（不持久化）
        self._image_cache = {}
        self._reply_pending = {}
        self._reply_tasks = {}
        self._face_cache = {}
        self._bg_queue = asyncio.Queue(maxsize=10)
        self._bg_workers = [asyncio.create_task(self._bg_worker()) for _ in range(3)]

        # 启动自愈：归一化旧格式存储向量（幂等，带 vnorm 戳即跳过）——须晚于 bg_queue 构造
        if self.reflection_store:
            self._run_background(self.reflection_store.migrate_unit_vectors())

        # === 上下文压缩初始化 ===
        self.compressor_enabled = bool(config.get('compression_enabled', False))
        if self.compressor_enabled:
            comp_model_uuid = str(config.get('compression_model_uuid', '') or ref_model_uuid)
            if not comp_model_uuid:
                print('[silent] compression disabled: no model_uuid (set compression_model_uuid or reflection_model_uuid)',
                      file=sys.stderr, flush=True)
                self.compressor_enabled = False
                self.summary_store = None
            else:
                self.compression_model_uuid = comp_model_uuid
                self.compression_tail_max_chars = int(config.get('compression_tail_max_chars', 1500))
                self.compression_cooldown_minutes = int(config.get('compression_cooldown_minutes', 10))
                self.compression_history_count = int(config.get('compression_history_count', 200))
                self._compression_cooldown_seconds = self.compression_cooldown_minutes * 60
                self._compression_min_tail_items = 3  # 保底：压缩后至少保留 3 条原文
                self.summary_store = SummaryStore(_DB_PATH)
                self.compression_log_store = CompressionLogStore(_DB_PATH)
                self._compression_queue = asyncio.Queue(maxsize=20)
                self._compression_inflight = set()
                self._compression_worker_task = asyncio.create_task(self._compression_worker())
                self._compression_stats = {
                    'ok': 0, 'fail': 0, 'parse_none': 0, 'timeout': 0,
                    'cooldown_skip': 0, 'queue_full': 0, 'no_signal': 0, 'inflight_skip': 0,
                }
                print(f'[silent] compression enabled: model={comp_model_uuid} tail={self.compression_tail_max_chars} '
                      f'history={self.compression_history_count} cooldown={self.compression_cooldown_minutes}m',
                      file=sys.stderr, flush=True)
        else:
            self.compressor_enabled = False
            self.summary_store = None

        # 周期持久化（每 5 分钟）
        asyncio.create_task(self._periodic_save())

        init_msg = f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count} kb_enabled={self.kb_enabled} vision_enabled={self.vision_enabled} reflection_enabled={self.reflection_enabled} compression_enabled={self.compressor_enabled}'
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
            asyncio.create_task(self.store.backfill_chat_index())

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            _t0 = time.time()
            session_name = canonical_session_name(f'{ctx.event.launcher_type}_{ctx.event.launcher_id}')
            self._strip_base64(ctx.event.message_chain)
            is_at = self._has_at(ctx.event.message_chain)
            is_trigger = is_at or random.random() < self.prob
            # 引用图片检测（轻量同步，不调 API）
            quote_has_img = self._quote_has_image(ctx.event.message_chain)
            # 提取引用文本 + 表情文本（gate 阶段有 message_chain，inject 阶段没有）
            # 必须在 normalize_face_components 之前提取，否则 Face 已被转为 Plain
            quote_text = await self._extract_quote(ctx.event.message_chain)
            face_text = self._extract_faces(ctx.event.message_chain)
            # Face → Plain 替换：必须在 _save_text_only 之前，否则 Unknown Face 存入 KB
            mc = ctx.event.message_chain
            if mc:
                self._normalize_face_components(mc)
            if face_text:
                self._face_cache[session_name] = face_text
            _save_ms = 0
            if is_trigger:
                _t_save = time.time()
                doc_id = await self._save_text_only(ctx.event)
                _save_ms = (time.time() - _t_save) * 1000
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
                if self.kb_enabled:
                    has_img = self._has_image(ctx.event.message_chain)
                    has_img_in_quote = quote_has_img
                    if doc_id and self.vision_enabled and (has_img or has_img_in_quote):
                        self._image_cache[doc_id] = {'status': 'pending', 'desc': '[图片]', 'time': time.time()}
                        self._run_background(self._save_with_vision(ctx.event, doc_id))
                    self._log_gate_msg(f'[silent] gate: allowed ({trigger}) doc_id={doc_id}')
                else:
                    self._log_gate_msg(f'[silent] gate: allowed ({trigger}) [no kb]')
                self._bump_reflection_counter(session_name)  # 仅 is_trigger 计数（防 prevent_default 消息污染）
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
                self._log_gate_msg('[silent] gate: prevented')
                print(f'[silent] gate: prevented (is_at=False)', file=sys.stderr, flush=True)
                ctx.prevent_default()

            _gate_ms = (time.time() - _t0) * 1000
            _write_timing({'stage': 'gate', 'session': session_name, 'trigger': is_trigger,
                           'save_ms': round(_save_ms) if is_trigger else 0,
                           'total_ms': round(_gate_ms)})

            # === 上下文压缩：消息存储后触发后台检查 ===
            if self.compressor_enabled and self.kb_enabled and is_trigger:
                self._trigger_compression(session_name)

            # === 反思层：纠正检测钩子（所有消息路径之后） ===
            if self.reflection_enabled:
                last_reply_ts = self._reply_ts.get(session_name, 0)
                if last_reply_ts > 0:
                    window = self.correction_detector._dynamic_window(
                        self._last_reply_text.get(session_name, '')
                    )
                    if time.time() - last_reply_ts < window:
                        self._run_background(self._maybe_generate_reflection(
                            ctx.event, session_name,
                        ))

        @self.handler(events.NormalMessageResponded)
        async def save_reply(ctx: context.EventContext):
            # 流式去重：同一 session 1 秒内只存第一条
            session_name = canonical_session_name(f'{ctx.event.launcher_type}_{ctx.event.launcher_id}')
            _ts = time.time()
            _last = self._reply_ts.get(session_name, 0)
            self._reply_ts[session_name] = _ts
            if _ts - _last < 1.0:
                return
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            self._last_reply_text[session_name] = text
            if self.kb_enabled:
                time_str = _now().strftime('%Y-%m-%d %H:%M')
                meta = _build_msg_metadata(session_name, '机器豆', '0', time_str, text, 'BOT', '')
                doc_id = _build_document_id(session_name, time_str, '0', text)
                self._run_background(self.store.store_message(meta, doc_id))
            self._last_trigger.pop(session_name, None)
            print(f'[silent] bot reply saved: {text[:30]}', file=sys.stderr, flush=True)

        @self.handler(events.PromptPreProcessing)
        async def inject(ctx: context.EventContext):
            _t_inject = time.time()
            with open('/tmp/silent_gate.log', 'a') as f:
                f.write('[silent] inject START\n')
            # 清掉 LangBot 原生 conversation 历史，避免与 timeline 双重注入
            ctx.event.prompt.clear()
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
            session_name = ''
            _vision_wait_ms = 0
            _query_ms = 0
            try:
                session_name = canonical_session_name(ctx.event.session_name)
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

                # === 反思层：person 会话纠正检测（/sync 消息不触发 GroupMessageReceived）===
                if self.reflection_enabled and session_name.startswith('person_'):
                    try:
                        api_tmp = QueryBasedAPIProxy(
                            query_id=ctx.query_id,
                            plugin_runtime_handler=self.plugin.plugin_runtime_handler,
                        )
                        qvars = await api_tmp.get_query_vars()
                        user_msg = str(qvars.get('user_message_text', '') or '')
                        sender_id = str(qvars.get('sender_id', '') or '')
                        if user_msg:
                            last_reply_ts = self._reply_ts.get(session_name, 0)
                            if last_reply_ts > 0:
                                window = self.correction_detector._dynamic_window(
                                    self._last_reply_text.get(session_name, '')
                                )
                                if time.time() - last_reply_ts < window:
                                    self._run_background(self._maybe_generate_reflection(
                                        ctx.event, session_name, user_msg, sender_id,
                                    ))
                    except Exception as _e:
                        safe_log('reflection', f'person correction check error: {_e}')

                api = QueryBasedAPIProxy(
                    query_id=ctx.query_id,
                    plugin_runtime_handler=self.plugin.plugin_runtime_handler,
                )

                # 等待当前消息的 vision 识图完成（防时序竞态：inject 先于 vision upsert）
                _t_vision_wait = time.time()
                if trigger_doc_id and self.vision_enabled:
                    for _ in range(60):  # 最多等 60s
                        cached = self._image_cache.get(trigger_doc_id)
                        if cached and cached['status'] == 'done':
                            break
                        await asyncio.sleep(0.5)
                _vision_wait_ms = (time.time() - _t_vision_wait) * 1000

                # === 反思层：检索注入 ===
                # 注：本段自带 try/except（inject error 日志）；embed/rerank 故障降级为不注入
                if self.reflection_enabled and self.reflection_store:
                    try:
                        ref_query = ''
                        if trigger_mc:
                            ref_query = await self.timeline_service.extract_text(trigger_mc, max_length=200)
                        if ref_query:
                            refs = await self.reflection_store.search_similar(ref_query, top_k=10)
                            if refs:
                                # distance 门槛：不相关不注入；观察日志供阈值校准
                                dists = [r.get('distance') if r.get('distance') is not None else 99 for r in refs]
                                safe_log('reflection', f'inject candidates: {[(str(r.get("id", ""))[:12], d) for r, d in zip(refs, dists)]}')
                                refs = [r for r, d in zip(refs, dists) if d <= _REF_INJECT_MAX_DISTANCE]
                            if refs:
                                # 护栏①：≤5 条直接注入，砍掉大部分 rerank 调用（10s 超时护栏②在 rerank 内）
                                if len(refs) > 5:
                                    refs = await self.reflection_generator.rerank(ref_query, refs)
                                ref_prompt = self.reflection_injector.build_reflection_prompt(refs)
                                if ref_prompt:
                                    ctx.event.prompt.append(
                                        provider_message.Message(role='system', content=ref_prompt)
                                    )
                    except Exception as e:
                        safe_log('reflection', f'inject error: {e}')

                _t_query = time.time()
                items = await self.store.get_recent_messages(session_name, 200)
                _query_ms = (time.time() - _t_query) * 1000
                if items:
                    items.sort(key=lambda i: i.get('metadata', {}).get('timestamp_unix', 0))
                    if trigger_doc_id:
                        items = [i for i in items if i.get('id') != trigger_doc_id]
                    if not self.compressor_enabled:
                        items = items[-self.history_count:]

                lines = _format_timeline(items)
                lines = self.timeline_service.deduplicate(lines)
                lines = self.timeline_service.truncate_by_chars(lines)
                lines, _identified, _pending, _failed = self.timeline_service.enhance_image_markers(lines)

                # === 上下文摘要注入（模式指令之前、timeline 之前） ===
                summary_text = ''
                if self.compressor_enabled and self.summary_store:
                    try:
                        doc = self.summary_store.load_or_default(session_name)
                        if doc.message_count > 0:
                            summary_text = self._format_summary(doc)
                            if summary_text:
                                ctx.event.prompt.append(
                                    provider_message.Message(role='system', content=summary_text)
                                )
                        # Tail 去重：过滤掉已被摘要覆盖的消息
                        covered = doc.covered_until_ts
                        if covered > 0:
                            filtered = [i for i in items
                                        if i.get('metadata', {}).get('timestamp_unix', 0) >= covered]
                            # 保底：至少保留最近 N 条原文
                            if len(filtered) < self._compression_min_tail_items:
                                filtered = items[-self._compression_min_tail_items:]
                            lines = _format_timeline(filtered)
                            lines = self.timeline_service.deduplicate(lines)
                            lines = self.timeline_service.truncate_by_chars(lines)
                            lines, _, _, _ = self.timeline_service.enhance_image_markers(lines)
                    except Exception as e:
                        safe_log('compression', f'inject summary error: {e}')
                        # 降级：照常注 timeline

                # DEBUG: dump prompt for analysis
                await self._dump_prompt_debug(api, now_str, trigger, _identified, _pending, _failed, lines, face_text, summary_text=summary_text)

                lock_dur = time.time() - self._lock_set_ts.pop(session_name, time.time())
                self._log_event('inject', session_name, trigger=trigger, lock_dur=f'{lock_dur:.1f}s')
                if trigger == 'random':
                    self._inject_random += 1
                    ctx.event.prompt.append(provider_message.Message(role='system', content='[随机插话] 从【】内群聊历史中挑选最值得评论的话题自由发挥。'))
                    self._emit_timeline(ctx, lines)
                    ctx.event.prompt.append(provider_message.Message(role='system', content='以上是群聊历史。接下来有一条用户消息——它只是随机触发器，不是你该回复的内容。无视它，用历史中的话题回应。'))
                else:
                    self._inject_at += 1
                    query_vars = await api.get_query_vars()
                    at_text = str(query_vars.get('user_message_text', '') or '')
                    # quote_text 已在 gate 阶段从 message_chain 的 Quote 组件提取
                    _log_gate(f'[{session_name}] quote_text={quote_text[:100] if quote_text else "(empty)"}')
                    if at_text.strip():
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[@模式]'))
                        self._emit_timeline(ctx, lines)
                    elif quote_text:
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[空@模式] 用户空@了你，但引用了消息。你必须优先结合上面引用的内容直接回答（20-50字）。不要回复"在线""收到"等状态确认。'))
                        self._emit_timeline(ctx, lines)
                        trigger = 'empty_at'
                    else:
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[空@模式] 用户空@了你。你必须从【】内群聊最近记录中挑选一个具体话题直接评论（20-50字）。不要回复"在线""收到"等状态确认，不要打招呼，直接说话题。'))
                        self._emit_timeline(ctx, lines)
                        trigger = 'empty_at'

                # === 防模仿压制条款（注入链最末尾，离生成点最近） ===
                # 无条件注入：反思关闭/未命中也需要压制归档行回显（timeline 泄露源）
                ctx.event.prompt.append(provider_message.Message(role='system', content=(
                    '你收到的提示词包含[群聊背景][先前经验]及"[时间] 昵称: 文本"式归档行，它们仅供你内部理解。'
                    '回复中严禁：a) 以"用户问""根据群聊背景""用户说"等旁白口吻叙述；'
                    'b) 回显归档行或反思条目的格式文本；c) 把内部文本当作用户原话引用。'
                )))

            except Exception as e:
                import traceback
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write('[silent] inject ERROR: %s\n%s\n' % (e, traceback.format_exc()))
            # 成功率日志
            stats = self._vision_stats
            if stats['total'] > 0:
                print(f'[silent] vision stats: total={stats["total"]} ok={stats["success"]} fail={stats["fail"]}', file=sys.stderr, flush=True)
            print(f'[silent] inject: timeline={len(items)} ({trigger})', file=sys.stderr, flush=True)
            _inject_ms = (time.time() - _t_inject) * 1000
            _write_timing({'stage': 'inject', 'session': session_name, 'trigger': trigger,
                           'timeline_count': len(items), 'vision_wait_ms': round(_vision_wait_ms),
                           'query_ms': round(_query_ms),
                           'total_ms': round(_inject_ms)})
            # DEBUG: dump full prompt
            self._dump_raw_prompt(ctx)

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

    @staticmethod
    def _emit_timeline(ctx, lines):
        ctx.event.prompt.append(provider_message.Message(
            role='system',
            content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'
        ))

    async def _dump_prompt_debug(self, api, now_str, trigger, _identified, _pending, _failed, lines, face_text, summary_text=''):
        """DEBUG: dump inject prompt analysis 到 /tmp/silent_prompt_dump.log。"""
        try:
            query_vars = await api.get_query_vars()
            at_text = str(query_vars.get('user_message_text', '') or '')
            with open('/tmp/silent_prompt_dump.log', 'a') as f:
                f.write(f'\n=== PROMPT DUMP [{_now().strftime("%H:%M:%S")}] ===\n')
                f.write(f'[1] time: {now_str}\n')
                f.write(f'[2] trigger: {trigger}\n')
                f.write(f'[3] ai_identified={_identified} ai_pending={_pending} ai_failed={_failed}\n')
                f.write(f'[4] timeline ({len(lines)} lines):\n' + '\n'.join(lines) + '\n')
                f.write(f'[5] user: {at_text[:200]}\n')
                _face_in_timeline = sum(1 for l in lines if '[QQ表情:' in l)
                _face_info = face_text if face_text else (f'timeline 含 {_face_in_timeline} 条' if _face_in_timeline else '(无)')
                f.write(f'[6] face: {_face_info}\n')
                f.write(f'[7] summary: {summary_text[:500] if summary_text else "(无)"}\n')
        except:
            pass

    @staticmethod
    def _dump_raw_prompt(ctx):
        """DEBUG: dump LLM raw prompt 到 /tmp/silent_gate.log。"""
        try:
            with open('/tmp/silent_gate.log', 'a') as f:
                f.write(f'=== LLM RAW PROMPT [{datetime.now(BJT).strftime("%H:%M:%S")}] ===\n')
                for i, msg in enumerate(ctx.event.prompt):
                    role = getattr(msg, 'role', '?')
                    content = str(getattr(msg, 'content', ''))
                    f.write(f'--- [{i}] role={role} ({len(content)}c) ---\n{content}\n')
                f.write('=== END RAW PROMPT ===\n\n')
        except:
            pass

    def _log_gate_msg(self, msg: str):
        """写 gate 日志到 stderr + /tmp/silent_gate.log（best-effort）。"""
        print(msg, file=sys.stderr, flush=True)
        try:
            with open('/tmp/silent_gate.log', 'a') as f:
                f.write(msg + '\n')
        except:
            pass

    def _log_event(self, kind, session, **kwargs):
        now = time.time()
        gap = ''
        if session in self._last_msg_ts:
            gap = f' gap={now - self._last_msg_ts[session]:.1f}s'
        self._last_msg_ts[session] = now
        extras = ' '.join(f'{k}={v}' for k, v in kwargs.items())
        try:
            with open(_EVENT_LOG, 'a') as f:
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

    @staticmethod
    def _extract_sender(event):
        """从 event 提取 (sender_name, sender_title, sender_role)。"""
        sender = getattr(event.message_event, 'sender', None)
        if sender:
            name = getattr(sender, 'member_name', '') or str(event.sender_id)
            title = getattr(sender, 'special_title', '') or ''
            role = _norm_role(getattr(sender, 'permission', None))
        else:
            name = str(event.sender_id)
            title = ''
            role = ''
        return name, title, role

    async def _save_text_only(self, event):
        """只存文本到 KB，不等待识图。gate 触发路径使用。"""
        chain_types = [c.type for c in (event.message_chain or [])]
        # NapCat 收到合并转发时，message_chain 只有 ['Source']，无实际内容
        # 识别为转发群聊记录，明确标记
        is_forward_only = chain_types == ['Source']
        text = ''
        if is_forward_only:
            text = '[转发消息（内容未展开，无法查看具体消息和图片）]'
            _log_gate(f'_save_text_only: forward-only (Source only) from {event.sender_id}')
        else:
            text = await self.timeline_service.extract_text(event.message_chain) or getattr(event, 'text_message', '')
            if 'Unknown' in text:
                mc_types = [f'{c.type}' for c in (event.message_chain or [])]
                _log_gate(f'_save_text_only: HAS_UNKNOWN text_len={len(text)} chain_types={mc_types} text100={text[:100]}')
        sender_name, sender_title, sender_role = self._extract_sender(event)
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
            sender_name, sender_title, sender_role = self._extract_sender(event)
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
        sender_name, sender_title, sender_role = self._extract_sender(event)
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

    # ── 反思层 ────────────────────────────────────────────

    async def _maybe_generate_reflection(self, event, session_name: str, user_text: str = "", sender_id: str = ""):
        """后台检测纠正信号并生成反思。"""
        try:
            if not user_text:
                user_text = await self.timeline_service.extract_text(event.message_chain, max_length=300)
            bot_reply = self._last_reply_text.get(session_name, '')
            if not user_text or not bot_reply:
                return
            if not sender_id:
                sender_id = str(getattr(event, 'sender_id', ''))
            if not await self.reflection_store.check_rate_limit(session_name, sender_id):
                return
            recent = await self.store.get_recent_messages(session_name, 10) if self.store else []
            signal = await self.correction_detector.detect(
                session_name, user_text, bot_reply, recent,
            )
            if not signal:
                return
            reflection = await self.reflection_generator.generate(signal)
            if not reflection:
                return
            await self._persist_reflection(reflection)
        except Exception as e:
            safe_log('reflection', f'generate error: {type(e).__name__}: {str(e)[:120]}')

    def _bump_reflection_counter(self, session_name: str):
        """每 is_trigger 消息 +1，每 10 轮触发自我反思。gate 只留一行调用。"""
        self._reflection_round_count += 1
        if self.reflection_enabled and self._reflection_round_count % 10 == 0:
            self._run_background(self._maybe_self_reflect(session_name))

    async def _maybe_self_reflect(self, session_name: str):
        """主动反思：扫描最近 10 条消息，发现 bot 自身错误并沉淀."""
        try:
            if not self.reflection_enabled or not self.reflection_store or not self.reflection_scanner:
                return
            # 限流必须在 scan 的 LLM 调用之前（sender 固定 'self-reflect'，10min 冷却全局生效）
            if not await self.reflection_store.check_rate_limit(session_name, 'self-reflect'):
                return
            recent = await self.store.get_recent_messages(session_name, 10) if self.store else []
            texts = [i.get('metadata', {}).get('text', '') for i in recent if i.get('metadata', {}).get('text')]
            if not texts:
                return
            reflection = await self.reflection_scanner.scan(texts)
            if not reflection:
                return
            await self._persist_reflection(reflection)
            safe_log('reflection', f'self-reflect: stored {reflection.get("scenario", "")[:40]}')
        except Exception as e:
            safe_log('reflection', f'self-reflect error: {type(e).__name__}: {str(e)[:120]}')

    async def _persist_reflection(self, reflection: dict):
        """去重/合并/存储共享路径（纠正 + self-reflect 两条管线复用）."""
        existing_id, existing, level = await self.reflection_store.find_duplicate(
            reflection.get('scenario', ''),
            reflection.get('mistake', ''),
            reflection.get('entities', []),
        )
        if level == 'direct' and existing_id:
            existing['confirm_count'] = existing.get('confirm_count', 0) + 1
            existing['last_hit'] = datetime.now(BJT).isoformat()
            existing['source_msg_ids'] = list(set(
                existing.get('source_msg_ids', []) + reflection.get('source_msg_ids', [])
            ))
            if existing['confirm_count'] >= 3 and existing.get('importance') == 'low':
                existing['importance'] = 'medium'
            # when/then backfill：新字段随合并扩散到旧记录
            existing.setdefault('when', reflection.get('when'))
            existing.setdefault('then', reflection.get('then'))
            await self.reflection_store.update_reflection(existing_id, existing)
            safe_log('reflection', f'merged: {existing_id} confirm={existing["confirm_count"]}')
        elif level == 'candidate' and existing_id:
            existing['confirm_count'] = existing.get('confirm_count', 0) + 1
            existing['last_hit'] = datetime.now(BJT).isoformat()
            existing.setdefault('when', reflection.get('when'))
            existing.setdefault('then', reflection.get('then'))
            await self.reflection_store.update_reflection(existing_id, existing)
            safe_log('reflection', f'candidate merge: {existing_id}')
        elif level == 'entity_link':
            safe_log('reflection', f'entity_link: {existing.get("linked_entities", [])}')
            await self.reflection_store.store_reflection(reflection)
        else:
            await self.reflection_store.store_reflection(reflection)

    async def _reflection_decay_loop(self):
        """每日衰减扫描（30天降权/90天归档）."""
        while True:
            await asyncio.sleep(86400)  # 24h
            try:
                all_refs = await self.reflection_store.list_all(limit=200)
                for item in all_refs:
                    meta = item.get('metadata', {})
                    doc_id = item.get('id', '')
                    action = self.reflection_store.should_decay(meta)
                    if action == 'archive':
                        await self.reflection_store.archive_reflection(doc_id)
                        safe_log('reflection', f'decay: archived {doc_id}')
                    elif action == 'downgrade':
                        new_imp = 'medium' if meta.get('importance') == 'high' else 'low'
                        meta['importance'] = new_imp
                        await self.reflection_store.update_reflection(doc_id, meta)
                        safe_log('reflection', f'decay: downgraded {doc_id} → {new_imp}')
            except Exception as e:
                safe_log('reflection', f'decay error: {e}')

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

    # ── 上下文压缩 ─────────────────────────────────────────────

    def _trigger_compression(self, session_name: str):
        """入队前预判 cooldown，避免无效入队。"""
        if self.summary_store is None:
            return
        session_name = canonical_session_name(session_name)
        doc = self.summary_store.load_or_default(session_name)
        if time.time() < doc.cooldown_until:
            self._compression_stats['cooldown_skip'] += 1
            return
        try:
            self._compression_queue.put_nowait(session_name)
        except asyncio.QueueFull:
            self._compression_stats['queue_full'] += 1  # 队列满则丢弃，等下一轮

    async def _compression_worker(self):
        """独立单 worker，避免 30s 压缩阻塞 vision/存储任务。"""
        while True:
            session_name = await self._compression_queue.get()
            try:
                await self._process_compression(session_name)
            except Exception as e:
                print(f'[silent] compression worker error: {e}', file=sys.stderr, flush=True)
            finally:
                self._compression_queue.task_done()

    async def _process_compression(self, session_name: str):
        if self.store is None or self.summary_store is None:
            return
        session_name = canonical_session_name(session_name)
        # per-session 并发保护
        if session_name in self._compression_inflight:
            self._compression_stats['inflight_skip'] += 1
            return
        self._compression_inflight.add(session_name)
        _t0 = time.time()
        prompt = ''
        status = 'no_signal'
        error = ''
        input_chars = 0
        output_chars = 0
        summary_before = 0
        summary_after = 0
        covered_until_ts = 0.0
        msg_count = 0
        try:
            doc = self.summary_store.load_or_default(session_name)
            items = await self.store.get_recent_messages(session_name, self.compression_history_count)
            items.sort(key=lambda i: i.get('metadata', {}).get('timestamp_unix', 0))
            if not should_compress(doc.covered_until_ts, items,
                                   self.compression_tail_max_chars, doc.cooldown_until):
                self._compression_stats['no_signal'] += 1
                return
            to_summarize, to_keep = split_messages(items, self.compression_tail_max_chars)
            if not to_summarize:
                self._compression_stats['no_signal'] += 1
                return
            msg_count = len(to_summarize)
            summary_before = len(doc.facts) + len(doc.topics) + len(doc.decisions) + len(doc.refs)
            prompt = build_compression_prompt(doc, to_summarize)
            input_chars = len(prompt)
            try:
                resp_text_ref = []
                new_doc = await self._call_compression_model(prompt, resp_text_ref)
                resp_text = resp_text_ref[0] if resp_text_ref else ''
                output_chars = len(resp_text)
            except asyncio.TimeoutError:
                status = 'timeout'
                error = '60s timeout'
                self._compression_stats['timeout'] += 1
            except Exception as e:
                status = 'fail'
                error = str(e)[:200]
                self._compression_stats['fail'] += 1
                import traceback
                print(f'[silent] compression failed: {e}\n{traceback.format_exc()}',
                      file=sys.stderr, flush=True)

            if status in ('timeout', 'fail'):
                doc.cooldown_until = time.time() + self._compression_cooldown_seconds
                self.summary_store.upsert(session_name, doc)
                duration_ms = int((time.time() - _t0) * 1000)
                safe_log('compression',
                         f'{session_name}: {status} {error} input={input_chars}chars '
                         f'output={output_chars}chars {duration_ms}ms '
                         f'stats=ok={self._compression_stats["ok"]} fail={self._compression_stats["fail"]} '
                         f'timeout={self._compression_stats["timeout"]}')
                self._log_compression(session_name, _t0, duration_ms, input_chars,
                                      output_chars, msg_count, summary_before, 0,
                                      doc.covered_until_ts, status, error)
                return

            if new_doc is None:
                status = 'parse_none'
                self._compression_stats['parse_none'] += 1
                doc.cooldown_until = time.time() + self._compression_cooldown_seconds
                self.summary_store.upsert(session_name, doc)
                duration_ms = int((time.time() - _t0) * 1000)
                safe_log('compression',
                         f'{session_name}: parse_none input={input_chars}chars '
                         f'output={output_chars}chars {duration_ms}ms '
                         f'stats=ok={self._compression_stats["ok"]} fail={self._compression_stats["fail"]} '
                         f'parse_none={self._compression_stats["parse_none"]}')
                self._log_compression(session_name, _t0, duration_ms, input_chars,
                                      output_chars, msg_count, summary_before, 0,
                                      doc.covered_until_ts, status, '')
                return

            # 成功
            status = 'ok'
            self._compression_stats['ok'] += 1
            if to_keep:
                new_doc.covered_until_ts = to_keep[0].get('metadata', {}).get('timestamp_unix', doc.covered_until_ts)
            else:
                new_doc.covered_until_ts = items[-1].get('metadata', {}).get('timestamp_unix', doc.covered_until_ts) if items else doc.covered_until_ts
            new_doc.message_count = msg_count + doc.message_count
            new_doc.cooldown_until = time.time() + self._compression_cooldown_seconds
            summary_after = len(new_doc.facts) + len(new_doc.topics) + len(new_doc.decisions) + len(new_doc.refs)
            covered_until_ts = new_doc.covered_until_ts
            self.summary_store.upsert(session_name, new_doc)
            delta = summary_after - summary_before
            duration_ms = int((time.time() - _t0) * 1000)
            safe_log('compression',
                     f'{session_name}: {msg_count}msgs→{summary_after}chars Δ{delta:+d} '
                     f'in≈{input_chars}chars out≈{output_chars}chars {duration_ms}ms '
                     f'covered={covered_until_ts:.0f} '
                     f'stats=ok={self._compression_stats["ok"]} fail={self._compression_stats["fail"]} '
                     f'parse_none={self._compression_stats["parse_none"]} timeout={self._compression_stats["timeout"]}')
            self._log_compression(session_name, _t0, duration_ms, input_chars,
                                  output_chars, msg_count, summary_before,
                                  summary_after, covered_until_ts, status, '')
        finally:
            self._compression_inflight.discard(session_name)

    def _log_compression(self, session_name, started_at, duration_ms, input_chars,
                         output_chars, msg_count, summary_before, summary_after,
                         covered_until_ts, status, error):
        """写 compression_log 行，失败不影响主流程."""
        try:
            self.compression_log_store.insert(
                session_name, started_at, duration_ms, input_chars,
                output_chars, msg_count, summary_before, summary_after,
                covered_until_ts, status, error, self.compression_model_uuid,
            )
        except Exception as e:
            print(f'[silent] compression_log insert error: {e}', file=sys.stderr, flush=True)

    async def _call_compression_model(self, prompt: str, resp_collector: list | None = None):
        """调压缩模型，60s 超时。失败抛异常由上层写 cooldown。
        resp_collector 可选，用于收集原始响应文本（输出字符数统计）."""
        messages = [provider_message.Message(role='user', content=prompt)]
        resp = await asyncio.wait_for(
            self.plugin.invoke_llm(self.compression_model_uuid, messages),
            timeout=60,
        )
        # invoke_llm 返回 Message 对象，先提取纯文本——上层 len() 需要 str
        resp_text = _extract_llm_text(resp)
        if resp_collector is not None:
            resp_collector.append(resp_text)
        return parse_summary_response(resp_text)

    def _format_summary(self, doc: SummaryDocument) -> str:
        """格式化摘要为注入文本：分隔线 + bullet 格式."""
        from datetime import datetime, timezone, timedelta
        BJT = timezone(timedelta(hours=8))
        covered_str = datetime.fromtimestamp(doc.covered_until_ts, tz=BJT).strftime('%Y-%m-%d %H:%M') if doc.covered_until_ts > 0 else "无"

        lines = [f"─── 群聊背景（覆盖至 {covered_str}）───"]

        if doc.facts:
            lines.append(doc.facts)

        if doc.topics:
            # bullet 行 → 顿号连接的短标签
            topic_items = [t[2:] if t.startswith('- ') else t for t in doc.topics.split('\n') if t.strip()]
            lines.append(f"话题：{'、'.join(topic_items)}")

        if doc.decisions:
            lines.append("决策：")
            lines.append(doc.decisions)

        if doc.refs:
            lines.append(f"参考：{doc.refs}")

        if len(lines) == 1:
            return ""
        return "\n".join(lines)
