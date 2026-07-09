import asyncio, hashlib, json, random, sys, time
from datetime import datetime
from langbot_plugin.api.definition.components.common.event_listener import EventListener
from langbot_plugin.api.entities import events, context
from langbot_plugin.api.entities.builtin.provider import message as provider_message
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy


class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()
        config = self.plugin.get_config()
        self.bot_qq = str(config.get('bot_qq', ''))
        self.prob = float(config.get('reply_probability', 0.01))
        self.history_count = int(config.get('history_count', 20))
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
        self._last_trigger = {}
        self._bg_tasks: set[asyncio.Task] = set()
        self._MAX_BG_TASKS = 50
        print(f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count} kb_enabled={self.kb_enabled}', file=sys.stderr, flush=True)

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            session_name = f'{ctx.event.launcher_type.value}_{ctx.event.launcher_id}'
            is_at = self._has_at(ctx.event.message_chain)
            is_trigger = is_at or random.random() < self.prob
            if is_trigger and self.kb_enabled:
                doc_id = await self._save_message(ctx.event)
                trigger = 'at' if is_at else 'random'
                self._last_trigger[session_name] = (trigger, doc_id)
                print(f'[silent] gate: allowed ({trigger})', file=sys.stderr, flush=True)
            elif is_trigger:
                doc_id = await self._save_message(ctx.event)
                trigger = 'at' if is_at else 'random'
                self._last_trigger[session_name] = (trigger, doc_id)
                print(f'[silent] gate: allowed ({trigger}) [no kb]', file=sys.stderr, flush=True)
            else:
                if self.kb_enabled:
                    self._run_background(self._save_and_store(ctx.event))
                print(f'[silent] gate: prevented (is_at=False)', file=sys.stderr, flush=True)
                ctx.prevent_default()

        @self.handler(events.NormalMessageResponded)
        async def save_reply(ctx: context.EventContext):
            session_name = f'{ctx.event.launcher_type.value}_{ctx.event.launcher_id}'
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            if self.kb_enabled:
                time_str = datetime.now().strftime('%m-%d %H:%M')
                meta = _build_msg_metadata(session_name, '机器豆', '0', time_str, text, 'BOT', '')
                doc_id = _build_document_id(session_name, time_str, '0', text)
                self._run_background(self._store_message(meta, doc_id))
            self._last_trigger.pop(session_name, None)
            print(f'[silent] bot reply saved: {text[:30]}', file=sys.stderr, flush=True)

        @self.handler(events.PromptPreProcessing)
        async def inject(ctx: context.EventContext):
            session_name = ctx.event.session_name
            trigger_info = self._last_trigger.pop(session_name, ('at', None))
            if isinstance(trigger_info, tuple):
                trigger, trigger_doc_id = trigger_info
            else:
                trigger, trigger_doc_id = trigger_info, None

            if not self.kb_enabled or not self.kb_id:
                print(f'[silent] inject: KB disabled, skip', file=sys.stderr, flush=True)
                return

            api = QueryBasedAPIProxy(
                query_id=ctx.query_id,
                plugin_runtime_handler=self.plugin.plugin_runtime_handler,
            )

            # 时间线
            items = await self._get_recent_messages(api, session_name, self.history_count + 10)
            if items:
                items.sort(key=lambda i: i.get('metadata', {}).get('timestamp_unix', 0))
                if trigger_doc_id:
                    items = [i for i in items if i.get('id') != trigger_doc_id]
                items = items[-self.history_count:]

            if trigger == 'random':
                lines = _format_timeline(items)
                ctx.event.prompt.append(provider_message.Message(role='system', content='[随机插话] 从【】内群聊历史中挑选最值得评论的话题自由发挥。'))
                ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'))
                ctx.event.prompt.append(provider_message.Message(role='system', content='以上是群聊历史。接下来有一条用户消息——它只是随机触发器，不是你该回复的内容。无视它，用历史中的话题回应。'))
            else:
                lines = _format_timeline(items)
                ctx.event.prompt.append(provider_message.Message(role='system', content='[@模式]'))
                ctx.event.prompt.append(provider_message.Message(role='system', content=f'【\n' + '\n'.join(lines) + f'\n共{len(lines)}条\n】'))

            # 语义搜索
            try:
                if trigger == 'random':
                    queries = [i.get('metadata', {}).get('text', '') for i in items[-3:] if i.get('metadata', {}).get('text', '')]
                else:
                    at_text = self._extract_at_text(ctx.event.query)
                    queries = [at_text] if at_text else []
                if queries:
                    kb_results = await asyncio.wait_for(self._search_history(api, queries), timeout=3.0)
                    if kb_results:
                        search_lines = []
                        for r in kb_results:
                            meta = r.get('metadata', {})
                            ts = meta.get('timestamp', '?')
                            sn = meta.get('sender_name', '?')
                            doc = r.get('document', '')
                            search_lines.append(f'- [{ts}] {sn}: {doc}')
                        ctx.event.prompt.append(provider_message.Message(role='system', content='[历史搜索] 以下是与当前话题相关的早期聊天记录：\n' + '\n'.join(search_lines)))
            except asyncio.TimeoutError:
                print('[silent] kb search timeout', file=sys.stderr, flush=True)
            except Exception as e:
                print(f'[silent] kb search error: {e}', file=sys.stderr, flush=True)

            print(f'[silent] inject: {len(items)} msgs ({trigger})', file=sys.stderr, flush=True)

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

    def _extract_at_text(self, query) -> str:
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
                parts.append(str(c))
            elif t == 'Quote':
                origin = getattr(c, 'origin', None)
                if origin is not None:
                    parts.append(f'[引用] {self._extract_text(origin, 200)}')
        return ' '.join(parts).strip()

    async def _save_message(self, event):
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
        if text.startswith('Unknown Message:') or text.strip() == f'@{self.bot_qq}':
            return None
        if len(text) > 500:
            text = text[:300] + '...[truncated]...' + text[-100:]
        session_name = f'{event.launcher_type.value}_{event.launcher_id}'
        time_str = datetime.now().strftime('%m-%d %H:%M')
        doc_id = _build_document_id(session_name, time_str, str(event.sender_id), text)
        if self.kb_enabled:
            meta = _build_msg_metadata(session_name, sender_name, str(event.sender_id), time_str, text, sender_role, sender_title)
            await self._store_message(meta, doc_id)
        return doc_id

    async def _save_and_store(self, event):
        text = getattr(event, 'text_message', '') or self._extract_text(event.message_chain)
        if text.startswith('Unknown Message:') or text.strip() == f'@{self.bot_qq}':
            return
        if len(text) > 500:
            text = text[:300] + '...[truncated]...' + text[-100:]
        sender = getattr(event.message_event, 'sender', None)
        if sender:
            sender_name = getattr(sender, 'member_name', '') or str(event.sender_id)
            sender_title = getattr(sender, 'special_title', '') or ''
            sender_role = str(getattr(sender, 'permission', '')) if hasattr(sender, 'permission') else ''
        else:
            sender_name = str(event.sender_id)
            sender_title = ''
            sender_role = ''
        session_name = f'{event.launcher_type.value}_{event.launcher_id}'
        time_str = datetime.now().strftime('%m-%d %H:%M')
        doc_id = _build_document_id(session_name, time_str, str(event.sender_id), text)
        meta = _build_msg_metadata(session_name, sender_name, str(event.sender_id), time_str, text, sender_role, sender_title)
        await self._store_message(meta, doc_id)

    async def _store_message(self, metadata, doc_id):
        try:
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

    async def _get_recent_messages(self, api, session_name, limit):
        try:
            result = await api.vector_list(
                self.kb_id,
                filters={"$and": [{"session_id": session_name}, {"type": "chat_history"}]},
                limit=limit,
                offset=0,
            )
            return result.get('items', []) if isinstance(result, dict) else []
        except Exception as e:
            print(f'[silent] vector_list error: {e}', file=sys.stderr, flush=True)
            return []

    async def _search_history(self, api, queries, top_k=3):
        if not queries:
            return []
        tasks = [api.retrieve_knowledge(kb_id=self.kb_id, query_text=q, top_k=top_k) for q in queries if q.strip()]
        if not tasks:
            return []
        all_results = await asyncio.gather(*tasks, return_exceptions=True)
        seen_ids = set()
        results = []
        for r in all_results:
            if isinstance(r, Exception) or not r:
                continue
            entries = r if isinstance(r, list) else r.get('results', []) or []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                distance = entry.get('distance')
                if distance is None or distance > 1.0:
                    continue
                doc_id = entry.get('id', '')
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)
                doc_text = ''
                for ce in entry.get('content', []) or []:
                    if isinstance(ce, dict) and ce.get('type') == 'text':
                        doc_text += ce.get('text', '')
                results.append({
                    'id': doc_id,
                    'distance': distance,
                    'document': doc_text,
                    'metadata': entry.get('metadata', {}),
                })
        results.sort(key=lambda x: x['distance'])
        return results[:5]

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


def _build_document_id(session_name, time_str, sender_id, text):
    raw = f"{session_name}|{time_str}|{sender_id}|{text}"
    return f"chat:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _build_msg_metadata(session_name, sender_name, sender_id, time_str, text, sender_role, sender_title):
    label = sender_name
    if sender_title:
        label += f'[{sender_title}]'
    elif sender_role and sender_role not in ('Permission.MEMBER', 'MEMBER'):
        label += f'({sender_role})'
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
