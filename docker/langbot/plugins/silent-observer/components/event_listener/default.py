import asyncio, hashlib, json, random, sys, time
from datetime import datetime, timezone, timedelta
BJT = timezone(timedelta(hours=8))

def _now():
    return datetime.now(BJT)
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
        # 迁移已完成，禁用避免重复
        # if self.kb_enabled:
        #     asyncio.create_task(self._migrate_buffer_if_needed())
        init_msg = f'[silent] init: bot_qq={self.bot_qq} prob={self.prob} history={self.history_count} kb_enabled={self.kb_enabled}'
        print(init_msg, file=sys.stderr, flush=True)
        try:
            with open('/tmp/silent_init.log', 'w') as f:
                f.write(init_msg + '\n')
        except:
            pass

        @self.handler(events.GroupMessageReceived)
        async def gate(ctx: context.EventContext):
            session_name = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            is_at = self._has_at(ctx.event.message_chain)
            is_trigger = is_at or random.random() < self.prob
            if is_trigger and self.kb_enabled:
                doc_id = await self._save_message(ctx.event)
                trigger = 'at' if is_at else 'random'
                self._last_trigger[session_name] = (trigger, doc_id)
                gate_msg = f'[silent] gate: allowed ({trigger}) doc_id={doc_id}'
                print(gate_msg, file=sys.stderr, flush=True)
                try:
                    with open('/tmp/silent_gate.log', 'a') as f:
                        f.write(gate_msg + '\n')
                except:
                    pass
            elif is_trigger:
                doc_id = await self._save_message(ctx.event)
                trigger = 'at' if is_at else 'random'
                self._last_trigger[session_name] = (trigger, doc_id)
                gate_msg = f'[silent] gate: allowed ({trigger}) [no kb]'
                print(gate_msg, file=sys.stderr, flush=True)
                try:
                    with open('/tmp/silent_gate.log', 'a') as f:
                        f.write(gate_msg + '\n')
                except:
                    pass
            else:
                if self.kb_enabled:
                    self._run_background(self._save_and_store(ctx.event))
                print(f'[silent] gate: prevented (is_at=False)', file=sys.stderr, flush=True)
                ctx.prevent_default()

        @self.handler(events.NormalMessageResponded)
        async def save_reply(ctx: context.EventContext):
            session_name = f'{ctx.event.launcher_type}_{ctx.event.launcher_id}'
            sender = getattr(ctx.event, 'sender_id', 'unknown')
            text = getattr(ctx.event, 'response_text', '') or str(getattr(ctx.event, 'reply_message_chain', ''))
            if self.kb_enabled:
                time_str = _now().strftime('%m-%d %H:%M')
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
            search_count = 0
            trigger = 'at'
            try:
                session_name = ctx.event.session_name
                trigger_info = self._last_trigger.pop(session_name, ('at', None))
                if isinstance(trigger_info, tuple):
                    trigger, trigger_doc_id = trigger_info
                else:
                    trigger, trigger_doc_id = trigger_info, None

                if not self.kb_enabled or not self.kb_id:
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
                        query_vars = await api.get_query_vars()
                        at_text = str(query_vars.get('user_message_text', '') or '')
                        sender_name = str(query_vars.get('sender_name', '') or '')
                        if at_text.strip():
                            # @模式：消息文本 + 发言人，精准匹配该用户历史
                            if sender_name:
                                queries = [at_text.strip(), f'{at_text.strip()} {sender_name}']
                            else:
                                queries = [at_text.strip()]
                        else:
                            queries = []
                        try:
                            with open('/tmp/silent_gate.log', 'a') as f:
                                f.write('[silent] at_text="%s" sender=%s\n' % (at_text[:80], sender_name))
                        except:
                            pass
                    if queries:
                        with open('/tmp/silent_gate.log', 'a') as f:
                            f.write('[silent] search: %d queries\n' % len(queries))
                        kb_results = await asyncio.wait_for(self._search_history(api, queries), timeout=3.0)
                        if kb_results:
                            # 排除时间线已有的近期消息
                            timeline_ids = {i.get('id') for i in items}
                            kb_results = [r for r in kb_results if r.get('id') not in timeline_ids]
                        if kb_results:
                            with open('/tmp/silent_gate.log', 'a') as f:
                                f.write('[silent] search: %d results (after dedup), top dist=%.4f\n' % (len(kb_results), kb_results[0].get('distance', 99)))
                                for r in kb_results[:5]:
                                    f.write('  [%.4f] %s\n' % (r.get('distance', 99), r.get('document', '')[:80]))
                            search_count = len(kb_results)
                            search_lines = []
                            for r in kb_results:
                                meta = r.get('metadata', {})
                                ts = meta.get('timestamp', '?')
                                sn = meta.get('sender_name', '?')
                                doc = r.get('document', '')
                                search_lines.append(f'- [{ts}] {sn}: {doc}')
                            ctx.event.prompt.append(provider_message.Message(role='system', content='[群聊历史检索] 以下是从全部群聊记录中检索到的早期内容：\n' + '\n'.join(search_lines)))
                            with open('/tmp/silent_gate.log', 'a') as f:
                                f.write('[silent] INJECTED %d search lines, prompt_msgs=%d\n' % (len(search_lines), len(ctx.event.prompt)))
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    with open('/tmp/silent_gate.log', 'a') as f:
                        f.write('[silent] search error: %s\n' % e)
            except Exception as e:
                import traceback
                with open('/tmp/silent_gate.log', 'a') as f:
                    f.write('[silent] inject ERROR: %s\n%s\n' % (e, traceback.format_exc()))
            print(f'[silent] inject: timeline={len(items)} search={search_count} ({trigger})', file=sys.stderr, flush=True)

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
        session_name = f'{event.launcher_type}_{event.launcher_id}'
        time_str = _now().strftime('%m-%d %H:%M')
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
        session_name = f'{event.launcher_type}_{event.launcher_id}'
        time_str = _now().strftime('%m-%d %H:%M')
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
            result = await self.plugin.vector_list(
                self.kb_id,
                filters={"$and": [{"session_id": session_name}, {"type": "chat_history"}]},
                limit=limit,
                offset=0,
            )
            return result.get('items', []) if isinstance(result, dict) else []
        except Exception as e:
            print(f'[silent] vector_list error: {e}', file=sys.stderr, flush=True)
            return []

    async def _search_history(self, api, queries, top_k=10):
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
        # 取第一个有效 query 做搜索
        q = valid_queries[0]
        # RRF 分数表：doc_id → rrf_score
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
            vec_raw = await self.plugin.vector_search(
                collection_id=self.kb_id,
                query_vector=qv,
                top_k=top_k,
                filters={"type": "chat_history"},
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
            # 过滤停用词
            stopwords = {'之前', '有没有', '没有人', '有人', '聊过', '吗', '什么', '怎么', '为什么', '可以', '这个', '那个', '一下', '在吗', '能不能', '是否', '还有', '以及', '或者', '不过', '但是', '因为', '所以', '如果', '虽然', '而且', '然后', '的话', '吧', '呢', '啊', '哈', '哦', '嗯', '一个', '哪些', '哪个', '那种', '什么样', '真是', '就是', '不是'}
            words = [w for w in words if w not in stopwords]
            words = list(set(words))
            kw_rank = 0
            for kw in words:
                try:
                    kw_raw = await self.plugin.vector_search(
                        collection_id=self.kb_id,
                        query_vector=[0.0] * 384,
                        top_k=5,
                        filters={"type": "chat_history"},
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
