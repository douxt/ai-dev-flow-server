import json, random, sys
from datetime import datetime
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider import message as provider_message

class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()
        config = self.plugin.get_config()
        self.bot_qq = str(config.get('bot_qq', ''))
        self.prob = float(config.get('reply_probability', 0.01))
        self.history_count = int(config.get('history_count', 20))
        self._last_trigger = {}  # session_name → 'at'|'random'
        print(f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count}', file=sys.stderr, flush=True)

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            saved_count = await self._save_message(ctx.event)
            is_at = self._has_at(ctx.event.message_chain)
            if not is_at and random.random() >= self.prob:
                print(f'[silent] gate: prevented (is_at=False)', file=sys.stderr, flush=True)
                ctx.prevent_default()
            else:
                trigger = 'at' if is_at else 'random'
                self._last_trigger[self._buffer_key(f'{ctx.event.launcher_type}_{ctx.event.launcher_id}')] = (trigger, saved_count or 0)
                print(f'[silent] gate: allowed ({trigger})', file=sys.stderr, flush=True)

        @self.handler(events.NormalMessageResponded)
        async def save_reply(ctx: context.EventContext):
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            session_key = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            await self._append_to_buffer(
                key=self._buffer_key(session_key),
                sender_id=str(sender), sender_name='机器豆', text=text,
                sender_title='', sender_role='BOT',
            )
            # TODO: strip quote-origin for random triggers
            # prevent_default on NormalMessageResponded breaks send pipeline
            self._last_trigger.pop(self._buffer_key(session_key), None)
            print(f'[silent] bot reply saved: {text[:30]}', file=sys.stderr, flush=True)

        @self.handler(events.PromptPreProcessing)
        async def inject(ctx: context.EventContext):
            msgs = await self._load_buffer(ctx.event.session_name)
            trigger_info = self._last_trigger.pop(self._buffer_key(ctx.event.session_name), ('at', -1))
            trigger, saved_idx = trigger_info if isinstance(trigger_info, tuple) else (trigger_info, -1)
            if trigger == 'random':
                if saved_idx and saved_idx > 0:
                    full_msgs = await self._load_buffer(ctx.event.session_name, 0)
                    if full_msgs:
                        msgs = [m for i, m in enumerate(full_msgs) if i < saved_idx - 1]
                    else:
                        msgs = []
                elif not msgs:
                    msgs = []
                lines = [f"[{m.get('time','?')}] {m.get('sender_name','?')}: {m.get('text','')}" for m in msgs]
                ctx.event.prompt.append(provider_message.Message(role='system', content='[随机插话] 从【】内群聊历史中挑选最值得评论的话题自由发挥。'))
                ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(msgs)}条\n】'))
                ctx.event.prompt.append(provider_message.Message(role='system', content='以上是群聊历史。接下来有一条用户消息——它只是随机触发器，不是你该回复的内容。无视它，用历史中的话题回应。'))
            else:
                if not msgs:
                    msgs = []
                lines = []
                for m in msgs:
                    name = m.get('sender_name', '?')
                    title = m.get('sender_title', '')
                    role = m.get('sender_role', '')
                    label = name
                    if title: label += f'[{title}]'
                    elif role and role not in ('Permission.MEMBER', 'MEMBER'):
                        label += f'({role})'
                    lines.append(f"[{m.get('time','?')}] {label}: {m.get('text','')}")
                ctx.event.prompt.append(provider_message.Message(role='system', content='[@模式]'))
                ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(msgs)}条\n】'))
            print(f'[silent] inject: {len(msgs)} msgs ({trigger})', file=sys.stderr, flush=True)

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
                for node in getattr(c, 'node_list', []) or []:
                    mc = getattr(node, 'message_chain', None)
                    if mc is not None and self._has_at(mc):
                        return True
        return False

    def _buffer_key(self, session_name: str) -> str:
        return f'buffer:{session_name}'

    def _extract_text(self, message_chain, max_length=300) -> str:
        if message_chain is None:
            return ''
        parts = []
        for c in message_chain:
            t = c.type
            if t == 'Plain':
                parts.append(getattr(c, 'text', ''))
            elif t == 'At':
                parts.append(f'@{getattr(c, "display", None) or getattr(c, "target", "")}')
            elif t == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    parts.append(f'[引用] {self._extract_text(origin, max_length)}')
            elif t == 'Forward':
                nodes = getattr(c, 'node_list', []) or []
                if nodes:
                    for i, node in enumerate(nodes[:5]):
                        mc = getattr(node, 'message_chain', None)
                        inner = self._extract_text(mc, max_length) if mc is not None else ''
                        sender = getattr(node, 'sender_name', '')
                        parts.append(f'[合并转发 {sender}] {inner}')
                    if len(nodes) > 5:
                        parts.append(f'[共{len(nodes)}条,仅展示前5条]')
                else:
                    parts.append('[合并转发:无内容]')
            elif t == 'Source':
                pass
            elif t == 'Image':
                parts.append('[图片]')
            elif t == 'Face':
                parts.append(str(c))
            else:
                parts.append(f'[{t}]')
            if len(' '.join(parts)) > max_length:
                return ' '.join(parts)[:max_length] + '...[截断]'
        return ' '.join(parts)

    async def _save_message(self, event):
        key = self._buffer_key(f'{event.launcher_type}_{event.launcher_id}')
        text = getattr(event, 'text_message', '') or self._extract_text(event.message_chain)
        sender = getattr(event.message_event, 'sender', None)
        if sender:
            sender_name = getattr(sender, 'member_name', '') or str(event.sender_id)
            sender_title = getattr(sender, 'special_title', '') or ''
            sender_role = str(getattr(sender, 'permission', '')) if hasattr(sender, 'permission') else ''
        else:
            sender_name = str(event.sender_id)
            sender_title = ''
            sender_role = ''
        count = await self._append_to_buffer(
            key=key, sender_id=str(event.sender_id),
            sender_name=sender_name, text=text,
            sender_title=sender_title, sender_role=sender_role,
        )
        return count

    async def _append_to_buffer(self, key, sender_id, sender_name, text, sender_title='', sender_role=''):
        try:
            raw = await self.plugin.get_plugin_storage(key)
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = json.loads(raw.decode('utf-8'))
        except Exception as e:
            err = str(e)
            if 'not found' in err.lower():
                data = {'messages': []}
            else:
                print(f'[silent] buffer read error: {key} {err}', file=sys.stderr, flush=True)
                return
        # filter noise: pure @ markers and unknown component types
        if text.startswith('Unknown Message:') or text.strip() == f'@{self.bot_qq}':
            return
        # truncate huge text (base64 garbage from old napcat versions, etc.)
        if len(text) > 500:
            text = text[:300] + '...[truncated]...' + text[-100:]
        data['messages'].append({
            'sender_name': sender_name, 'sender_id': sender_id,
            'sender_title': sender_title, 'sender_role': sender_role,
            'text': text, 'time': datetime.now().strftime('%m-%d %H:%M'),
        })
        if len(data['messages']) > self.history_count * 2:
            data['messages'] = data['messages'][-self.history_count:]
        try:
            await self.plugin.set_plugin_storage(key, json.dumps(data, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            print(f'[silent] buffer write error: {key} {e}', file=sys.stderr, flush=True)
            return
        count = len(data['messages'])
        print(f'[silent] buffer write: {key} total={count}', file=sys.stderr, flush=True)
        return count

    async def _load_buffer(self, session_name: str, count: int = None) -> list:
        if count is None:
            count = self.history_count
        key = self._buffer_key(session_name)
        try:
            raw = await self.plugin.get_plugin_storage(key)
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = json.loads(raw.decode('utf-8'))
            msgs = data.get('messages', [])
            if count == 0:
                return msgs
            return msgs[-count:]
        except Exception:
            return []