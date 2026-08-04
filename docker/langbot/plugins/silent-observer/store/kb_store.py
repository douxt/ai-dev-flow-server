"""KB 存储层 — ChromaDB vector_* + SQLite chat_index 双写."""
import asyncio
import json
import math
import sqlite3
import sys
import time

from util.logs import safe_log
from util.text import build_document_id, ROLE_CN

_API_TIMEOUT = 30  # 所有 API 调用超时秒数


class KBStore:
    """KB 读写封装：向量存储 + SQLite 索引 + 维度探测 + 超时保护."""

    def __init__(self, plugin, kb_id: str, embedding_model_uuid: str, db_path: str):
        self._plugin = plugin
        self.kb_id = kb_id
        self.embedding_model_uuid = embedding_model_uuid
        self._db_path = db_path
        self._embedding_dim: int | None = None  # lazy detect
        self._api_sem = asyncio.Semaphore(3)

    # ── SQLite helpers ──────────────────────────────────────

    def _get_db(self):
        db = sqlite3.connect(self._db_path, timeout=10)
        db.execute('PRAGMA journal_mode=WAL')
        return db

    def init_chat_index(self):
        try:
            db = self._get_db()
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=NORMAL")
            db.execute("""CREATE TABLE IF NOT EXISTS chat_index (
                doc_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                timestamp_unix REAL NOT NULL,
                formatted_text TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_chat_session_time ON chat_index(session_id, timestamp_unix DESC)")
            from store.summary_store import SummaryStore
            SummaryStore.create_table(db)
            db.commit()
            db.close()
        except Exception as e:
            print(f'[silent] chat_index init error: {e}', file=sys.stderr, flush=True)

    # ── 维度探测 ────────────────────────────────────────────

    async def _detect_embedding_dim(self) -> int:
        """启动时探测真实嵌入维度，替换硬编码 384."""
        if self._embedding_dim is not None:
            return self._embedding_dim
        try:
            vectors = await asyncio.wait_for(
                self._plugin.invoke_embedding(self.embedding_model_uuid, ['dimension probe']),
                timeout=_API_TIMEOUT,
            )
            dim = len(vectors[0]) if vectors else 0
            if dim > 0:
                self._embedding_dim = dim
                safe_log('store', f'embedding dim detected: {dim}')
                return dim
        except Exception as e:
            safe_log('store', f'dimension probe failed: {e}')
        self._embedding_dim = 384  # fallback
        return 384

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            return 384  # fallback before async detect
        return self._embedding_dim

    # ── 核心操作 ────────────────────────────────────────────

    async def store_message(self, metadata: dict, doc_id: str):
        """双写：vector_upsert + SQLite chat_index."""
        try:
            async with self._api_sem:
                vectors = await asyncio.wait_for(
                    self._plugin.invoke_embedding(self.embedding_model_uuid, [metadata['text']]),
                    timeout=_API_TIMEOUT,
                )
                await asyncio.wait_for(
                    self._plugin.vector_upsert(
                        collection_id=self.kb_id,
                        vectors=vectors,
                        ids=[doc_id],
                        metadata=[metadata],
                        documents=[metadata['text']],
                    ),
                    timeout=_API_TIMEOUT,
                )
        except Exception as e:
            print(f'[silent] store error: {e}', file=sys.stderr, flush=True)
        try:
            db = self._get_db()
            db.execute(
                "INSERT OR REPLACE INTO chat_index (doc_id, session_id, timestamp_unix, formatted_text) VALUES (?, ?, ?, ?)",
                (doc_id, metadata['session_id'], metadata['timestamp_unix'], metadata['text'])
            )
            db.commit()
            db.close()
        except Exception as e:
            print(f'[silent] chat_index write error: {e}', file=sys.stderr, flush=True)

    async def get_recent_messages(self, session_name: str, limit: int) -> list[dict]:
        """SQLite 时间线查询（最近N条消息）."""
        try:
            db = self._get_db()
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

    async def search_history(self, queries: list[str], session_name: str = '', top_k: int = 10) -> list[dict]:
        """RRF 混合搜索：Vector + Keyword（jieba 分词）."""
        safe_log('search', f'ENTER: {len(queries)} queries')
        if not queries:
            return []
        valid_queries = [q for q in queries if q and q.strip()]
        if not valid_queries:
            return []

        q = valid_queries[0]
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, dict] = {}
        K = 60

        # === Vector 通道 ===
        try:
            vectors = await asyncio.wait_for(
                self._plugin.invoke_embedding(self.embedding_model_uuid, [q]),
                timeout=_API_TIMEOUT,
            )
            qv = vectors[0]
            # 维度探测（首次成功后缓存）
            if self._embedding_dim is None:
                self._embedding_dim = len(qv)
                safe_log('store', f'embedding dim detected: {self._embedding_dim}')
            norm = math.sqrt(sum(v * v for v in qv))
            if norm > 0:
                qv = [v / norm for v in qv]
            vec_filters: dict = {"type": "chat_history"}
            if session_name:
                vec_filters = {"$and": [{"type": "chat_history"}, {"session_id": session_name}]}
            vec_raw = await asyncio.wait_for(
                self._plugin.vector_search(
                    collection_id=self.kb_id,
                    query_vector=qv,
                    top_k=top_k,
                    filters=vec_filters,
                ),
                timeout=_API_TIMEOUT,
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
            safe_log('search', f'vector: {len(vec_raw or [])} results')
        except Exception as e:
            safe_log('search', f'vector error: {e}')

        # === Keyword 通道：jieba 分词 + BM25 全文搜索 ===
        try:
            import jieba
            words = [w for w in jieba.cut(q) if len(w) >= 2]
            stopwords = {'之前', '有没有', '没有人', '有人', '聊过', '吗', '什么', '怎么', '为什么', '可以', '这个', '那个', '一下', '在吗', '能不能', '是否', '还有', '以及', '或者', '不过', '但是', '因为', '所以', '如果', '虽然', '而且', '然后', '的话', '吧', '呢', '啊', '哈', '哦', '嗯', '一个', '哪些', '哪个', '那种', '什么样', '真是', '就是', '不是'}
            words = [w for w in words if w not in stopwords]
            words = list(set(words))
            kw_rank = 0
            zero_vec = [0.0] * self.embedding_dim
            for kw in words:
                try:
                    kw_filters: dict = {"type": "chat_history"}
                    if session_name:
                        kw_filters = {"$and": [{"type": "chat_history"}, {"session_id": session_name}]}
                    kw_raw = await asyncio.wait_for(
                        self._plugin.vector_search(
                            collection_id=self.kb_id,
                            query_vector=zero_vec,
                            top_k=5,
                            filters=kw_filters,
                            search_type='full_text',
                            query_text=kw,
                        ),
                        timeout=_API_TIMEOUT,
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
                except Exception:
                    pass
            kw_count = sum(1 for did in rrf_scores if did in doc_map and doc_map[did].get('distance', 99) < 0.01)
            safe_log('search', f'keyword: {kw_count} docs from {len(words)} words')
        except Exception as e:
            safe_log('search', f'keyword error: {e}')

        # RRF 排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = [doc_map[did] for did in sorted_ids if did in doc_map]
        return results[:5]

    async def backfill_sender(self, sender_id: str, new_name: str, title: str, role: str):
        """回填历史消息中 sender 的群名片/头衔."""
        label = new_name
        if title:
            label += f'[{title}]'
        if role and role != 'MEMBER':
            label += f'({ROLE_CN.get(role, role)})'
        try:
            raw = await asyncio.wait_for(
                self._plugin.vector_list(
                    self.kb_id,
                    filters={"$and": [{"sender_id": sender_id}, {"type": "chat_history"}]},
                    limit=200, offset=0,
                ),
                timeout=_API_TIMEOUT,
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
                await asyncio.wait_for(
                    self._plugin.vector_upsert(
                        collection_id=self.kb_id,
                        ids=ids_to_update,
                        metadata=metas_to_update,
                        documents=[m['text'] for m in metas_to_update],
                    ),
                    timeout=_API_TIMEOUT,
                )
                print(f'[silent] backfill: {sender_id} → {label} ({len(ids_to_update)} 条)', file=sys.stderr, flush=True)
            except Exception as e:
                print(f'[silent] backfill update error: {e}', file=sys.stderr, flush=True)

    async def migrate_buffer_if_needed(self):
        """一次性迁移：buffer → KB（仅在 KB 为空时执行）"""

        def _log(msg):
            print(msg, file=sys.stderr, flush=True)
            safe_log('init', msg)

        try:
            result = await asyncio.wait_for(
                self._plugin.vector_list(self.kb_id, filters={"type": "chat_history"}, limit=1, offset=0),
                timeout=_API_TIMEOUT,
            )
            total = result.get('total', -1) if isinstance(result, dict) else -1
            if total > 0:
                _log(f'[silent] migration: KB already has {total} docs, skip')
                return
        except Exception as e:
            _log(f'[silent] migration: vector_list check failed: {e}')

        migrated = 0
        for group_id in ['group_1104330614', 'group_116381172']:
            try:
                raw = await self._plugin.get_plugin_storage(f'buffer:{group_id}')
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
                    doc_id = build_document_id(group_id, time_str, sender_id, text)
                    meta = {
                        'text': display, 'sender_name': sender_name, 'sender_id': sender_id,
                        'timestamp': time_str, 'timestamp_unix': 0.0,
                        'session_id': group_id, 'type': 'chat_history',
                    }
                    await self.store_message(meta, doc_id)
                    migrated += 1
                _log(f'[silent] migration: {migrated} msgs from {group_id}')
            except Exception as e:
                _log(f'[silent] migration skip {group_id}: {e}')
        _log(f'[silent] migration: {migrated} total msgs migrated to KB')
