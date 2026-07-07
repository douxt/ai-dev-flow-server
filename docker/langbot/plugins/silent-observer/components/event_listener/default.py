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
        print(f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count}', file=sys.stderr, flush=True)

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            await self._save_message(ctx.event)
            is_at = self._has_at(ctx.event.message_chain)
            if not is_at and random.random() >= self.prob:
                print(f'[silent] gate: prevented (is_at=False)', file=sys.stderr, flush=True)
                ctx.prevent_default()
            else:
                trigger = 'at' if is_at else 'random'
                print(f'[silent] gate: allowed ({trigger})', file=sys.stderr, flush=True)

        @self.handler(events.NormalMessageResponded)
        async def save_reply(ctx: context.EventContext):
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            await self._append_to_buffer(
                key=self._buffer_key(f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'),
                sender_id=str(sender), sender_name='机器豆', text=text,
                sender_title='', sender_role='BOT',
            )
            print(f'[silent] bot reply saved: {text[:30]}', file=sys.stderr, flush=True)

        @self.handler(events.PromptPreProcessing)
        async def inject(ctx: context.EventContext):
            msgs = await self._load_buffer(ctx.event.session_name)
            if not msgs: return
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
            header = f'【群聊最近 {len(msgs)} 条记录\n' + '\n'.join(lines) + '】'
            ctx.event.prompt.insert(0, provider_message.Message(role='system', content=header))
            print(f'[silent] inject: {len(msgs)} messages for {ctx.event.session_name}', file=sys.stderr, flush=True)

    def _has_at(self, message_chain) -> bool:
        for c in message_chain:
            if c.type == 'At' and str(c.target) == self.bot_qq:
                return True
            if c.type == 'Quote' and hasattr(c, 'origin'):
                if self._has_at(c.origin):
                    return True
            if c.type == 'Forward' and hasattr(c, 'node_list'):
                for node in c.node_list:
                    if hasattr(node, 'message_chain') and self._has_at(node.message_chain):
                        return True
        return False
        return f'buffer:{session_name}'

    async def _save_message(self, event):
        key = self._buffer_key(f'{event.launcher_type}_{event.launcher_id}')
        text = getattr(event, 'text_message', '') or str(event.message_chain)
        sender = getattr(event.message_event, 'sender', None)
        if sender:
            sender_name = getattr(sender, 'member_name', '') or str(event.sender_id)
            sender_title = getattr(sender, 'special_title', '') or ''
            sender_role = str(getattr(sender, 'permission', '')) if hasattr(sender, 'permission') else ''
        else:
            sender_name = str(event.sender_id)
            sender_title = ''
            sender_role = ''
        await self._append_to_buffer(
            key=key, sender_id=str(event.sender_id),
            sender_name=sender_name, text=text,
            sender_title=sender_title, sender_role=sender_role,
        )

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

    async def _load_buffer(self, session_name: str) -> list:
        key = self._buffer_key(session_name)
        try:
            raw = await self.plugin.get_plugin_storage(key)
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = json.loads(raw.decode('utf-8'))
            return data.get('messages', [])[-self.history_count:]
        except Exception:
            return []