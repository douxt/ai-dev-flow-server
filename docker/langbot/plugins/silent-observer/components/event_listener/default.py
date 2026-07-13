import asyncio, base64, hashlib, io, json, random, sqlite3, sys, time
from datetime import datetime, timezone, timedelta
BJT = timezone(timedelta(hours=8))
_DB_PATH = '/app/data/plugins/dou__langbot-silent-observer/chat_index.db'
_ROLE_CN = {'OWNER': '群主', 'ADMINISTRATOR': '管理员', 'MEMBER': '成员'}

# QQ 经典黄脸表情 face_id → 中文名，napcat 偶尔不提供 face_name 时的 fallback
_QQ_FACE_NAME = {
    0:'微笑',1:'撇嘴',2:'色',3:'发呆',4:'得意',5:'流泪',6:'害羞',7:'闭嘴',8:'睡',9:'大哭',
    10:'尴尬',11:'发怒',12:'调皮',13:'呲牙',14:'惊讶',15:'难过',16:'酷',18:'偷笑',19:'可爱',
    20:'白眼',21:'傲慢',22:'饥饿',23:'困',24:'惊恐',25:'流汗',26:'憨笑',27:'大兵',28:'奋斗',
    29:'咒骂',30:'疑问',31:'嘘',32:'晕',33:'折磨',34:'衰',35:'骷髅',36:'敲打',37:'再见',
    38:'擦汗',39:'抠鼻',40:'鼓掌',41:'糗大了',42:'坏笑',43:'左哼哼',44:'右哼哼',45:'哈欠',
    46:'鄙视',47:'委屈',48:'快哭了',49:'阴险',50:'亲亲',51:'吓',52:'可怜',53:'菜刀',54:'西瓜',
    55:'啤酒',56:'篮球',57:'乒乓',58:'咖啡',59:'饭',60:'猪头',61:'玫瑰',62:'凋谢',63:'示爱',
    64:'爱心',65:'心碎',66:'蛋糕',67:'闪电',68:'炸弹',69:'刀',70:'足球',71:'瓢虫',72:'便便',
    73:'月亮',74:'太阳',75:'礼物',76:'拥抱',77:'强',78:'弱',79:'握手',80:'胜利',81:'抱拳',
    82:'勾引',83:'拳头',84:'差劲',85:'爱你',86:'NO',87:'OK',88:'爱情',89:'飞吻',90:'跳跳',
    91:'发抖',92:'怄火',93:'转圈',94:'磕头',95:'回头',96:'跳绳',97:'挥手',98:'激动',99:'街舞',
    100:'献吻',101:'左太极',102:'右太极',103:'双喜',104:'鞭炮',105:'灯笼',106:'发财',107:'K歌',
    108:'购物',109:'邮件',110:'帅',111:'喝彩',112:'祈祷',113:'爆筋',114:'棒棒糖',115:'喝奶',
    116:'下面',117:'香蕉',118:'飞机',119:'开车',120:'高铁左车头',121:'车厢',122:'高铁右车头',
    123:'多云',124:'下雨',125:'钞票',126:'熊猫',127:'灯泡',128:'风车',129:'闹钟',130:'打伞',
    131:'彩球',132:'钻戒',133:'沙发',134:'纸巾',135:'药',136:'手枪',137:'青蛙',
    # napcat 常见但有 face_name 的高频 ID，以防万一
    178:'斜眼笑',264:'捂脸',
}

def _now():
    return datetime.now(BJT)
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

_ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
_MAX_PIXELS = 2048 * 2048
_VISION_SEMAPHORE = None  # lazy init in _describe_images
_API_SEM = asyncio.Semaphore(3)  # 限制并发 WS 调用，防止 plugin runtime 断连


def _log_gate(msg):
    try:
        with open('/tmp/silent_gate.log', 'a') as f:
            f.write(msg + '\n')
    except:
        pass


class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()
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
        else:
            self.kb_enabled = False
            self.kb_id = ''
            self.embedding_model_uuid = ''
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
        self._vision_daily_count = 0
        self._vision_daily_date = _now().date()
        self._vision_fail_streak = 0
        self._vision_circuit_open_until = None
        self._vision_stats = {'total': 0, 'success': 0, 'fail': 0, 'total_tokens': 0}
        self._image_cache = {}  # doc_id → {status, desc, time}
        self._last_trigger = {}
        self._lock_set_ts = {}  # session → lock设置时间戳
        self._bg_tasks: set[asyncio.Task] = set()
        self._MAX_BG_TASKS = 50
        # 触发统计
        self._gate_hits = 0
        self._gate_misses = 0
        self._lock_skips = 0
        self._inject_random = 0
        self._inject_at = 0
        self._last_msg_ts = {}  # session → 上一条消息时间戳
        self._stats_start = time.time()
        # 迁移已完成，禁用避免重复
        # if self.kb_enabled:
        #     asyncio.create_task(self._migrate_buffer_if_needed())
        init_msg = f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count} kb_enabled={self.kb_enabled} vision_enabled={self.vision_enabled}'
        print(init_msg, file=sys.stderr, flush=True)
        try:
            with open('/tmp/silent_init.log', 'w') as f:
                f.write(init_msg + '\n')
        except:
            pass

        self._init_chat_index()

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            session_name = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            is_at = self._has_at(ctx.event.message_chain)
            is_trigger = is_at or random.random() < self.prob
            # 提取引用文本（从 message_chain 的 Quote 组件）
            quote_text = await self._extract_quote(ctx.event.message_chain)
            if is_trigger and self.kb_enabled:
                doc_id = await self._save_text_only(ctx.event)
                # 不仅检测 message_chain 中的 Image 组件，也检测引用文本中的 [图片] 占位
                has_img = self._has_image(ctx.event.message_chain)
                has_img_in_quote = '[图片' in (quote_text or '')
                if doc_id and self.vision_enabled and (has_img or has_img_in_quote):
                    self._image_cache[doc_id] = {'status': 'pending', 'desc': '[图片]', 'time': time.time()}
                    self._run_background(self._save_with_vision(ctx.event, doc_id))
                trigger = 'at' if is_at else 'random'
                locked = session_name in self._last_trigger and not is_at
                if not locked:
                    self._last_trigger[session_name] = (trigger, doc_id, quote_text)
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
                    self._last_trigger[session_name] = (trigger, doc_id, quote_text)
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
            session_name = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            if self.kb_enabled:
                time_str = _now().strftime('%Y-%m-%d %H:%M')
                meta = _build_msg_metadata(session_name, '机器豆', '0', time_str, text, 'BOT', '')
                doc_id = _build_document_id(session_name, time_str, '0', text)
                self._run_background(self._store_message(meta, doc_id))
            self._last_trigger.pop(session_name, None)
            print(f'[silent] bot reply saved: {text[:30]}', file=sys.stderr, flush=True)

        @self.handler(events.PromptPreProcessing)
        async def inject(ctx: context.EventContext):
            with open('/tmp/silent_gate.log', 'a') as f:
                f.write('[silent] inject START\n')
            now_str = _now().strftime('%Y年%m月%d日 %H:%M:%S 北京时间')
            ctx.event.prompt.append(provider_message.Message(role='system', content=f'当前时间：{now_str}'))
            items = []
            trigger = 'at'
            try:
                session_name = ctx.event.session_name
                trigger_info = self._last_trigger.pop(session_name, ('at', None, ''))
                if isinstance(trigger_info, tuple):
                    trigger = trigger_info[0]
                    trigger_doc_id = trigger_info[1] if len(trigger_info) > 1 else None
                    quote_text = trigger_info[2] if len(trigger_info) > 2 else ''
                else:
                    trigger, trigger_doc_id, quote_text = trigger_info, None, ''

                if not self.kb_enabled or not self.kb_id:
                    return

                api = QueryBasedAPIProxy(
                    query_id=ctx.query_id,
                    plugin_runtime_handler=self.plugin.plugin_runtime_handler,
                )

                # 时间线
                items = await self._get_recent_messages(api, session_name, 200)
                if items:
                    items.sort(key=lambda i: i.get('metadata', {}).get('timestamp_unix', 0))
                    if trigger_doc_id:
                        items = [i for i in items if i.get('id') != trigger_doc_id]
                    items = items[-self.history_count:]

                lines = _format_timeline(items)

                # 字符数限制：从最旧开始丢弃完整消息
                max_chars = self.timeline_max_chars
                total_chars = sum(len(l) for l in lines)
                while lines and total_chars > max_chars:
                    total_chars -= len(lines.pop(0))

                # 🔖 强化 timeline 中图片识别标记
                import re
                _identified = 0
                _pending = 0
                for _i, _line in enumerate(lines):
                    if '🖼️ 图' not in _line:
                        continue
                    _idx = _line.index('🖼️ 图')
                    _pfx = _line[:_idx]
                    _rest = _line[_idx:]
                    if '：⏳ 识别中' in _rest:
                        lines[_i] = _pfx + _rest.replace('🖼️ 图', '⏳ [AI识图中] 图', 1)
                        _pending += 1
                    elif '：[图片:' in _rest:
                        _m = re.match(r'🖼️ 图\d+：\[图片:\s*(.*?)\]', _rest)
                        if _m:
                            _img_prefix = _rest[:_rest.index('：')]
                            _img_prefix_new = _img_prefix.replace('🖼️ 图', '🤖 [AI识图] 图', 1)
                            _desc = _m.group(1)
                            _after = _rest[len(f'{_img_prefix}：[图片: {_desc}]'):]
                            lines[_i] = _pfx + f'{_img_prefix_new}：[{_desc}]' + _after
                            _identified += 1
                if _identified:
                    lines.append(f'📌 [AI识图] 以上含 {_identified} 张已识别图片，请据此回答。')

                # DEBUG: dump prompt for analysis
                try:
                    with open('/tmp/silent_prompt_dump.log', 'a') as f:
                        f.write(f'\n=== PROMPT DUMP [{_now().strftime("%H:%M:%S")}] ===\n')
                        f.write(f'[1] time: {now_str}\n')
                        f.write(f'[2] trigger: {trigger}\n')
                        f.write(f'[3] ai_identified={_identified} ai_pending={_pending}\n')
                        f.write(f'[4] timeline ({len(lines)} lines):\n' + '\n'.join(lines) + '\n')
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

    async def _extract_text(self, message_chain, max_length=300, image_descriptions=None, depth=0):
        if message_chain is None:
            return ''
        if depth > 5:
            return '[引用链过长]'
        if image_descriptions is None:
            image_descriptions = {}
        # NapCat 合并转发消息的 message_chain 只有 ['Source']
        chain_types = [c.type for c in message_chain]
        if chain_types == ['Source']:
            return '[合并转发群聊记录]'
        parts = []
        img_num = 0
        for i, c in enumerate(message_chain):
            t = c.type
            if t == 'Plain':
                parts.append(getattr(c, 'text', ''))
            elif t == 'At':
                parts.append(f'@{getattr(c, "display", None) or getattr(c, "target", "")}')
            elif t == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    inner = await self._extract_text(origin, max_length, image_descriptions=image_descriptions, depth=depth+1)
                    parts.append(f'[引用内容]\n{inner}')
            elif t == 'Forward':
                nodes = getattr(c, 'node_list', []) or []
                if nodes:
                    for ni, node in enumerate(nodes[:5]):
                        mc = getattr(node, 'message_chain', None)
                        inner = await self._extract_text(mc, max_length, image_descriptions=image_descriptions, depth=depth+1) if mc is not None else ''
                        sender = getattr(node, 'sender_name', '')
                        if not sender:
                            sender = str(getattr(node, 'sender_id', getattr(node, 'user_id', '')))
                        if inner:
                            parts.append(f'[合并转发 {sender}]\n{inner}')
                        else:
                            parts.append(f'[合并转发 {sender}: 无文本]')
                    if len(nodes) > 5:
                        parts.append(f'[共{len(nodes)}条,仅展示前5条]')
                else:
                    parts.append('[合并转发:无内容]')
            elif t == 'Source':
                pass
            elif t == 'Image':
                img_num += 1
                desc = image_descriptions.get(i) if image_descriptions else None
                if desc and desc != '[图片]':
                    parts.append(f'🖼️ 图{img_num}：{desc}')
                else:
                    parts.append(f'🖼️ 图{img_num}：⏳ 识别中...')
            elif t == 'Face':
                name = getattr(c, 'face_name', '') or _QQ_FACE_NAME.get(getattr(c, 'face_id', 0), '')
                if name:
                    parts.append(f'[表情:{name}]')
                else:
                    parts.append(f'[表情:{getattr(c, "face_id", "?")}]')
            else:
                parts.append(f'[{t}]')
            if len(' '.join(parts)) > max_length:
                return ' '.join(parts)[:max_length] + '...[截断]'
        return ' '.join(parts)

    async def _extract_at_text(self, query) -> str:
        mc = getattr(query, 'message_chain', None)
        if mc is None:
            return ''
        parts = []
        for c in mc:
            t = getattr(c, 'type', '')
            if t == 'Plain':
                parts.append(getattr(c, 'text', ''))
            elif t == 'At':
                pass
            elif t == 'Image':
                parts.append('[图片]')
            elif t == 'Face':
                name = getattr(c, 'face_name', '') or _QQ_FACE_NAME.get(getattr(c, 'face_id', 0), '')
                if name:
                    parts.append(f'[表情:{name}]')
                else:
                    parts.append(f'[表情:{getattr(c, "face_id", "?")}]')
            elif t == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    parts.append(f'[引用] {await self._extract_text(origin, 200, depth=1)}')
        return ' '.join(parts).strip()

    async def _extract_quote(self, message_chain) -> str:
        """从 message_chain 的 Quote 组件提取引用文本"""
        if message_chain is None:
            return ''
        for c in message_chain:
            if c.type == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    # 检查 origin 是否包含 Forward 组件
                    origin_types = [x.type for x in (origin if hasattr(origin, '__iter__') else [])]
                    has_fwd = 'Forward' in origin_types
                    if origin_types == ['Source']:
                        return '[合并转发群聊记录]'
                    inner = await self._extract_text(origin, 300, depth=1)
                    # origin 包含 Forward 时加标记
                    if has_fwd:
                        return f'[合并转发] {inner}' if inner else '[合并转发群聊记录]'
                    if not inner and origin_types:
                        return '[合并转发群聊记录]'
                    return inner
            elif c.type == 'Forward':
                # Forward 内查找 Quote
                nodes = getattr(c, 'node_list', []) or []
                for node in nodes:
                    mc = getattr(node, 'message_chain', None)
                    if mc is not None:
                        result = await self._extract_quote(mc)
                        if result:
                            return result
        return ''

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
            text = getattr(event, 'text_message', '') or await self._extract_text(event.message_chain)
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
            await self._store_message(meta, doc_id)
            if sender_title or (sender_role and sender_role not in ('Permission.MEMBER', 'MEMBER')):
                self._run_background(self._backfill_sender(str(event.sender_id), sender_name, sender_title, sender_role))
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
            image_descs = await self._describe_images(event.message_chain, trace_id, self.vision_max_images)
            text = await self._extract_text(event.message_chain, image_descriptions=image_descs)
                        error_placeholder = lambda v: v.startswith('[图片') and v.endswith(']')
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
            await self._store_message(meta, doc_id)
            _log_gate(f'[{trace_id}] vision: KB upserted, text len={len(meta["text"])}')
            # 更新缓存：存所有图片描述（不只用第一张）
            descs = [d for d in image_descs.values() if d != '[图片]']
            self._image_cache[doc_id] = {'status': 'done', 'desc': ' | '.join(descs) if descs else '[图片]', 'time': time.time()}
        except Exception as e:
            _log_gate(f'[{trace_id}] vision: error {type(e).__name__}: {str(e)[:120]}')
            self._image_cache[doc_id] = {'status': 'failed', 'desc': '[图片(识别失败)]', 'time': time.time()}

    async def _save_and_store(self, event):
        """非触发消息的后台归档。不等待识图。"""
        text = getattr(event, 'text_message', '') or await self._extract_text(event.message_chain)
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
        await self._store_message(meta, doc_id)

    async def _store_message(self, metadata, doc_id):
        try:
            async with _API_SEM:
                vectors = await self.plugin.invoke_embedding(self.embedding_model_uuid, [metadata['text']])
                await self.plugin.vector_upsert(
                    collection_id=self.kb_id,
                    vectors=vectors,
                    ids=[doc_id],
                    metadata=[metadata],
                    documents=[metadata['text']],
                )
        except Exception as e:
            print(f'[silent] store error: {e}', file=sys.stderr, flush=True)
        try:
            db = sqlite3.connect(_DB_PATH)
            db.execute(
                "INSERT OR REPLACE INTO chat_index (doc_id, session_id, timestamp_unix, formatted_text) VALUES (?, ?, ?, ?)",
                (doc_id, metadata['session_id'], metadata['timestamp_unix'], metadata['text'])
            )
            db.commit()
            db.close()
        except Exception as e:
            print(f'[silent] chat_index write error: {e}', file=sys.stderr, flush=True)

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

    def _collect_images(self, message_chain):
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

    async def _describe_images(self, message_chain, trace_id='', max_images=5) -> dict:
        global _VISION_SEMAPHORE
        if _VISION_SEMAPHORE is None:
            _VISION_SEMAPHORE = asyncio.Semaphore(2)
        imgs = self._collect_images(message_chain)
        if not imgs:
            return {}
        model_uuid = self.vision_model_uuid
        result = {}
        tasks = []
        for idx, img in imgs[:max_images]:
            tasks.append(self._describe_one(idx, img, model_uuid, trace_id))
        if tasks:
            gathered = await asyncio.gather(*tasks, return_exceptions=True)
            for (idx, _), r in zip(imgs[:max_images], gathered):
                if isinstance(r, Exception):
                    _log_gate(f'[{trace_id}] vision: img[{idx}] exception {type(r).__name__}: {str(r)[:120]}')
                    result[idx] = '[图片]'
                else:
                    result[idx] = r
        for idx, _ in imgs[max_images:]:
            result[idx] = '[图片(略)]'
        for idx, _ in imgs:
            if idx not in result:
                result[idx] = '[图片]'
        return result

    async def _describe_one(self, idx, img, model_uuid, trace_id):
        logs = []
        t_start = time.time()
        try:
            bytes_data, mime = await asyncio.wait_for(img.get_bytes(), timeout=5)
            t_get = time.time() - t_start
            logs.append(f'get_bytes={mime} size={len(bytes_data) // 1024}KB ({t_get:.2f}s)')
        except asyncio.TimeoutError:
            _log_gate(f'[{trace_id}] vision: img[{idx}] get_bytes timeout')
            return '[图片(下载失败)]'
        except Exception as e:
            _log_gate(f'[{trace_id}] vision: img[{idx}] get_bytes error {type(e).__name__}: {str(e)[:120]}')
            return '[图片(下载失败)]'

        if mime not in _ALLOWED_MIME:
            _log_gate(f'[{trace_id}] vision: img[{idx}] mime={mime} not allowed')
            return '[图片(不支持的格式)]'

        if not bytes_data:
            _log_gate(f'[{trace_id}] vision: img[{idx}] empty bytes')
            return '[图片(空)]'

        need_resize = False
        try:
            img_obj = open_image(bytes_data)
            w, h = img_obj.size
            if w > 2048 or h > 2048 or w * h > _MAX_PIXELS:
                need_resize = True
            img_obj.close()
        except Exception:
            need_resize = False

        if need_resize:
            try:
                loop = asyncio.get_running_loop()
                bytes_data = await loop.run_in_executor(None, _resize_image, bytes_data)
                logs.append(f'resized ({time.time() - t_start:.2f}s)')
            except Exception as e:
                _log_gate(f'[{trace_id}] vision: img[{idx}] resize error {type(e).__name__}')
                return '[图片(处理错误)]'

        b64 = base64.b64encode(bytes_data).decode('ascii')
        if len(b64) > 10 * 1024 * 1024:
            _log_gate(f'[{trace_id}] vision: img[{idx}] base64 too large ({len(b64) // 1024}KB)')
            return '[图片过大]'

        data_uri = f'data:{mime};base64,{b64}'
        try:
            t_api_start = time.time()
            resp = await asyncio.wait_for(
                self.plugin.invoke_llm(
                    llm_model_uuid=model_uuid,
                    messages=[
                        provider_message.Message(
                            role='user',
                            content=[
                                provider_message.ContentElement.from_text('请用一句话描述这张图片的内容（直接描述，不要前缀如"这张图片"）。'),
                                provider_message.ContentElement.from_image_base64(data_uri),
                            ]
                        )
                    ],
                ),
                timeout=20,
            )
            t_api = time.time() - t_api_start
            raw_text = self._extract_llm_text(resp)
            desc = _clean_description(raw_text)
            logs.append(f'llm_ok lat={t_api:.1f}s desc="{desc}"')
            self._record_vision_result(True)
            return desc
        except asyncio.TimeoutError:
            _log_gate(f'[{trace_id}] vision: img[{idx}] llm timeout')
            self._record_vision_result(False)
            return '[图片(超时)]'
        except Exception as e:
            _log_gate(f'[{trace_id}] vision: img[{idx}] llm_fail {type(e).__name__}: {str(e)[:120]}')
            self._record_vision_result(False)
            return '[图片]'
        finally:
            _log_gate(f'[{trace_id}] vision: img[{idx}] ' + ' '.join(logs))

    def _extract_llm_text(self, resp) -> str:
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
        self._vision_stats['total'] += 1
        if success:
            self._vision_stats['success'] += 1
            self._vision_fail_streak = 0
        else:
            self._vision_stats['fail'] += 1
            self._vision_fail_streak += 1
            if self._vision_fail_streak >= 5:
                self._vision_circuit_open_until = _now() + timedelta(minutes=5)
                print(f'[silent] WARNING vision: circuit opened ({self._vision_fail_streak} consecutive failures)', file=sys.stderr, flush=True)

    async def _check_vision_quota(self) -> bool:
        today = _now().date()
        if self._vision_daily_date != today:
            self._vision_daily_count = 0
            self._vision_daily_date = today
        if self._vision_circuit_open_until and _now() < self._vision_circuit_open_until:
            _log_gate(f'vision: circuit open until {self._vision_circuit_open_until.strftime("%H:%M:%S")}')
            return False
        if self.vision_daily_limit > 0 and self._vision_daily_count >= self.vision_daily_limit:
            _log_gate(f'vision: daily limit reached ({self._vision_daily_count}/{self.vision_daily_limit})')
            return False
        self._vision_daily_count += 1
        return True

    async def _backfill_sender(self, sender_id, new_name, title, role):
        """回填历史消息中该 sender_id 的裸名，替换为含群名片/头衔的名字"""
        label = new_name
        if title:
            label += f'[{title}]'
        if role and role != 'MEMBER':
            label += f'({_ROLE_CN.get(role, role)})'
        try:
            raw = await self.plugin.vector_list(
                self.kb_id,
                filters={"$and": [{"sender_id": sender_id}, {"type": "chat_history"}]},
                limit=200, offset=0,
            )
            items = raw.get('items', []) if isinstance(raw, dict) else []
        except Exception as e:
            print(f'[silent] backfill query error: {e}', file=sys.stderr, flush=True)
            return

        ids_to_update = []
        metas_to_update = []
        for item in items:
            meta = item.get('metadata', {})
            old_name = meta.get('sender_name', '')
            if old_name == label:
                continue
            if '[' in old_name or '(' in old_name:
                continue
            old_text = meta.get('text', '')
            new_text = f"[{meta.get('timestamp', '?')}] {label}: {old_text.split(']: ', 1)[-1] if ']: ' in old_text else old_text}"
            meta['sender_name'] = label
            meta['text'] = new_text
            ids_to_update.append(item.get('id'))
            metas_to_update.append(meta)

        if ids_to_update:
            try:
                await self.plugin.vector_upsert(
                    collection_id=self.kb_id,
                    ids=ids_to_update,
                    metadata=metas_to_update,
                    documents=[m['text'] for m in metas_to_update],
                )
                print(f'[silent] backfill: {sender_id} → {label} ({len(ids_to_update)} 条)', file=sys.stderr, flush=True)
            except Exception as e:
                print(f'[silent] backfill update error: {e}', file=sys.stderr, flush=True)

    async def _get_recent_messages(self, api, session_name, limit):
        try:
            db = sqlite3.connect(_DB_PATH)
            rows = db.execute(
                "SELECT doc_id, formatted_text, timestamp_unix FROM chat_index WHERE session_id = ? ORDER BY timestamp_unix DESC LIMIT ?",
                (session_name, limit)
            ).fetchall()
            db.close()
            return [
                {'id': row[0], 'metadata': {'text': row[1], 'timestamp_unix': row[2]}, 'document': row[1]}
                for row in rows
            ]
        except Exception as e:
            print(f'[silent] chat_index read error: {e}', file=sys.stderr, flush=True)
            return []

    async def _search_history(self, api, queries, session_name='', top_k=10):
        """混合搜索：Vector + Keyword（RRF融合），对标 LTM + 业界最佳实践"""
        try:
            with open('/tmp/silent_gate.log', 'a') as f:
                f.write('[silent] _search_history ENTER: %d queries\n' % len(queries))
        except:
            pass
        if not queries:
            return []
        valid_queries = [q for q in queries if q and q.strip()]
        if not valid_queries:
            return []
        import math
        q = valid_queries[0]
        rrf_scores = {}
        doc_map = {}
        K = 60

        # === Vector 通道 ===
        try:
            vectors = await self.plugin.invoke_embedding(self.embedding_model_uuid, [q])
            qv = vectors[0]
            norm = math.sqrt(sum(v*v for v in qv))
            if norm > 0:
                qv = [v / norm for v in qv]
            vec_filters = {"type": "chat_history"}
            if session_name:
                vec_filters = {"$and": [{"type": "chat_history"}, {"session_id": session_name}]}
            vec_raw = await self.plugin.vector_search(
                collection_id=self.kb_id,
                query_vector=qv,
                top_k=top_k,
                filters=vec_filters,
            )
            for rank, entry in enumerate(vec_raw or []):
                if not isinstance(entry, dict):
                    continue
                doc_id = entry.get('id', '')
                meta = entry.get('metadata', {})
                doc_text = meta.get('text', '') or entry.get('document', '')
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (K + rank + 1)
                if doc_id not in doc_map:
                    doc_map[doc_id] = {'id': doc_id, 'document': doc_text, 'metadata': meta,
                                       'distance': entry.get('distance', 99)}
            try:
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write('[silent] vector: %d results\n' % len(vec_raw or []))
            except:
                pass
        except Exception as e:
            try:
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write('[silent] vector error: %s\n' % e)
            except:
                pass

        # === Keyword 通道：逐词搜索，RRF 合并 ===
        try:
            import jieba
            words = [w for w in jieba.cut(q) if len(w) >= 2]
            stopwords = {'之前', '有没有', '没有人', '有人', '聊过', '吗', '什么', '怎么', '为什么', '可以', '这个', '那个', '一下', '在吗', '能不能', '是否', '还有', '以及', '或者', '不过', '但是', '因为', '所以', '如果', '虽然', '而且', '然后', '的话', '吧', '呢', '啊', '哈', '哦', '嗯', '一个', '哪些', '哪个', '那种', '什么样', '真是', '就是', '不是'}
            words = [w for w in words if w not in stopwords]
            words = list(set(words))
            kw_rank = 0
            for kw in words:
                try:
                    kw_filters = {"type": "chat_history"}
                    if session_name:
                        kw_filters = {"$and": [{"type": "chat_history"}, {"session_id": session_name}]}
                    kw_raw = await self.plugin.vector_search(
                        collection_id=self.kb_id,
                        query_vector=[0.0] * 384,
                        top_k=5,
                        filters=kw_filters,
                        search_type='full_text',
                        query_text=kw,
                    )
                    for entry in (kw_raw or []):
                        if not isinstance(entry, dict):
                            continue
                        doc_id = entry.get('id', '')
                        meta = entry.get('metadata', {})
                        doc_text = meta.get('text', '') or entry.get('document', '')
                        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (K + kw_rank + 1)
                        if doc_id not in doc_map:
                            doc_map[doc_id] = {'id': doc_id, 'document': doc_text, 'metadata': meta,
                                               'distance': entry.get('distance', 99)}
                        kw_rank += 1
                except:
                    pass
            try:
                with open('/tmp/silent_gate.log', 'a') as f:
                    kw_count = sum(1 for did in rrf_scores if did in doc_map and doc_map[did].get('distance', 99) < 0.01)
                    f.write('[silent] keyword: %d docs from %d words\n' % (kw_count, len(words)))
            except:
                pass
        except Exception as e:
            try:
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write('[silent] keyword error: %s\n' % e)
            except:
                pass

        # RRF 排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = [doc_map[did] for did in sorted_ids if did in doc_map]
        return results[:5]

    async def _migrate_buffer_if_needed(self):
        """一次性迁移：buffer 消息 → KB（仅在 KB 为空时执行）"""
        def _log(msg):
            print(msg, file=sys.stderr, flush=True)
            try:
                with open('/tmp/silent_init.log', 'a') as f:
                    f.write(msg + '\n')
            except:
                pass
        try:
            result = await self.plugin.vector_list(self.kb_id, filters={"type": "chat_history"}, limit=1, offset=0)
            total = result.get('total', -1) if isinstance(result, dict) else -1
            if total > 0:
                _log(f'[silent] migration: KB already has {total} docs, skip')
                return
        except Exception as e:
            _log(f'[silent] migration: vector_list check failed: {e}')
        migrated = 0
        try:
            raw = await self.plugin.get_plugin_storage('buffer:group_1104330614')
            data = json.loads(raw if isinstance(raw, str) else raw.decode('utf-8'))
            msgs = data.get('messages', [])
            for m in msgs:
                time_str = m.get('time', '?')
                sender_name = m.get('sender_name', '?')
                sender_id = str(m.get('sender_id', ''))
                text = m.get('text', '')
                label = sender_name
                title = m.get('sender_title', '')
                role = m.get('sender_role', '')
                if title:
                    label += f'[{title}]'
                elif role and role not in ('Permission.MEMBER', 'MEMBER'):
                    label += f'({role})'
                display = f"[{time_str}] {label}: {text}"
                doc_id = _build_document_id('group_1104330614', time_str, sender_id, text)
                meta = {
                    'text': display, 'sender_name': sender_name, 'sender_id': sender_id,
                    'timestamp': time_str, 'timestamp_unix': 0.0,
                    'session_id': 'group_1104330614', 'type': 'chat_history',
                }
                await self._store_message(meta, doc_id)
                migrated += 1
            _log(f'[silent] migration: {migrated} msgs from group_1104330614')
        except Exception as e:
            _log(f'[silent] migration skip group_1104330614: {e}')
        try:
            raw = await self.plugin.get_plugin_storage('buffer:group_116381172')
            data = json.loads(raw if isinstance(raw, str) else raw.decode('utf-8'))
            msgs = data.get('messages', [])
            for m in msgs:
                time_str = m.get('time', '?')
                sender_name = m.get('sender_name', '?')
                sender_id = str(m.get('sender_id', ''))
                text = m.get('text', '')
                label = sender_name
                title = m.get('sender_title', '')
                role = m.get('sender_role', '')
                if title:
                    label += f'[{title}]'
                elif role and role not in ('Permission.MEMBER', 'MEMBER'):
                    label += f'({role})'
                display = f"[{time_str}] {label}: {text}"
                doc_id = _build_document_id('group_116381172', time_str, sender_id, text)
                meta = {
                    'text': display, 'sender_name': sender_name, 'sender_id': sender_id,
                    'timestamp': time_str, 'timestamp_unix': 0.0,
                    'session_id': 'group_116381172', 'type': 'chat_history',
                }
                await self._store_message(meta, doc_id)
                migrated += 1
            _log(f'[silent] migration: {migrated} total msgs migrated to KB')
        except Exception as e:
            _log(f'[silent] migration skip group_116381172: {e}')

    def _run_background(self, coro):
        if len(self._bg_tasks) >= self._MAX_BG_TASKS:
            print('[silent] bg queue full', file=sys.stderr, flush=True)
            return
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        task.add_done_callback(
            lambda t: print(f'[silent] bg error: {t.exception()}', file=sys.stderr, flush=True)
            if t.exception() else None
        )

    def _init_chat_index(self):
        try:
            db = sqlite3.connect(_DB_PATH)
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("""CREATE TABLE IF NOT EXISTS chat_index (
                doc_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp_unix REAL NOT NULL,
                formatted_text TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_time ON chat_index(session_id, timestamp_unix DESC)")
            db.commit()
            db.close()
        except Exception as e:
            print(f'[silent] chat_index init error: {e}', file=sys.stderr, flush=True)


def _build_document_id(session_name, time_str, sender_id, text):
    raw = f"{session_name}|{time_str}|{sender_id}|{text}"
    return f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _build_msg_metadata(session_name, sender_name, sender_id, time_str, text, sender_role, sender_title):
    label = sender_name
    if sender_title:
        label += f'[{sender_title}]'
    if sender_role and sender_role != 'MEMBER':
        label += f'({_ROLE_CN.get(sender_role, sender_role)})'
    return {
        'text': f"[{time_str}] {label}: {text}",
        'sender_name': sender_name,
        'sender_id': sender_id,
        'timestamp': time_str,
        'timestamp_unix': time.time(),
        'session_id': session_name,
        'type': 'chat_history',
    }


def _format_timeline(items):
    lines = []
    for item in items:
        meta = item.get('metadata', {})
        text = meta.get('text', '') or item.get('document', '')
        if not text:
            for ce in item.get('content', []) or []:
                if isinstance(ce, dict) and ce.get('type') == 'text':
                    text = ce.get('text', '')
                    break
        if text:
            lines.append(text)
    return lines


def open_image(bytes_data):
    from PIL import Image
    return Image.open(io.BytesIO(bytes_data))


def _resize_image(bytes_data):
    from PIL import Image
    img = Image.open(io.BytesIO(bytes_data))
    try:
        w, h = img.size
        max_dim = max(w, h)
        if max_dim > 2048:
            ratio = 2048 / max_dim
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img_format = img.format or 'JPEG'
        if img_format == 'PNG' and img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
            img_format = 'JPEG'
        img.save(buf, format=img_format, quality=70)
        return buf.getvalue()
    finally:
        img.close()


def _norm_role(perm) -> str:
    if perm is None:
        return ''
    if hasattr(perm, 'value'):
        return perm.value
    return str(perm)


def _clean_description(text):
    text = (text or '').strip().strip('"').strip("'")
    for prefix in ['这张图片', '图片中', '图中', 'This image', 'The image', 'Image']:
        if text.startswith(prefix):
            text = text[len(prefix):]
            text = text.lstrip('是').lstrip('展示了').lstrip('显示').lstrip()
            break
    if not text or any(kw in text for kw in ['不能描述', '无法识别', 'cannot describe', 'violates']):
        return '[图片]'
    text = text.split('\n')[0][:60]
    return f'[图片: {text}]'
