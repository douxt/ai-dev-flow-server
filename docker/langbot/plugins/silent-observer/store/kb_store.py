"""KB 存储层 — ChromaDB vector_* + SQLite chat_index 双写."""
import asyncio
import json
import math
import re
import sqlite3
import sys
import time
from datetime import datetime

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
            from store.summary_store import SummaryStore, CompressionLogStore
            SummaryStore.create_table(db)
            CompressionLogStore.create_table(db)
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

    def _session_ids_for_search(self, session_name: str) -> list[str]:
        """双前缀：LangBot session_id 格式迁移遗留兼容。

        chat_index 中同一 QQ 群存在两种格式：
        - group_116381172（新格式）
        - group_group_116381172（旧格式）
        """
        if not session_name:
            return ['']
        ids = [session_name]
        if session_name.startswith('group_group_'):
            ids.append(session_name[len('group_'):])
        elif session_name.startswith('group_'):
            ids.append(f'group_{session_name}')
        return ids

    @staticmethod
    def _escape_like(s: str) -> str:
        """转义 SQL LIKE 通配符 % _ 及 ESCAPE 字符 \\（顺序关键：\\ 先转义）."""
        return re.sub(r'([\\%_])', r'\\\1', s)

    def _keyword_search_sqlite(self, query: str, session_name: str,
                                top_k: int, sender_name: str, days: int,
                                rrf_scores: dict, doc_map: dict, K: int = 60):
        """SQLite LIKE 关键词搜索 → 写入 RRF scores/dict.

        查询安全：query 截断 ≤300 字符，分词 ≤8 个。
        异常静默降级：保留 rrf_scores/doc_map 中 vector 通道已有结果。
        """
        if not query or not query.strip():
            return
        query = query.strip()[:300]

        words = list(dict.fromkeys(
            w for w in re.split(r'[\s,，]+', query) if len(w) >= 2
        ))
        if len(words) > 8:
            words = words[:8]
        if not words:
            words = [query]

        session_ids = self._session_ids_for_search(session_name)

        db = self._get_db()
        try:
            for word in words:
                sw = self._escape_like(word)
                wp = f'%{sw}%'
                kw_rank = 0
                for sid in session_ids:
                    # 动态 SQL：sender_name / days 按需拼接
                    where = "session_id = ? AND formatted_text LIKE ? ESCAPE '\\'"
                    params = [sid, wp]
                    if days and days > 0:
                        cutoff = time.time() - days * 86400
                        where += " AND timestamp_unix >= ?"
                        params.append(cutoff)
                    if sender_name:
                        where += " AND formatted_text LIKE ? ESCAPE '\\'"
                        params.append(f'%] {self._escape_like(sender_name)}:%')

                    rows = db.execute(
                        f"SELECT doc_id, formatted_text, timestamp_unix FROM chat_index"
                        f" WHERE {where} ORDER BY timestamp_unix DESC LIMIT ?",
                        (*params, top_k * 2)
                    ).fetchall()
                    for r in rows:
                        doc_id = r[0]
                        score = 1.0 / (K + kw_rank + 1)
                        if score > rrf_scores.get(doc_id, 0):
                            rrf_scores[doc_id] = score
                        if doc_id not in doc_map:
                            doc_map[doc_id] = {
                                'id': doc_id, 'document': r[1],
                                'metadata': {'text': r[1], 'timestamp_unix': r[2]},
                                'distance': 0.0,
                            }
                        kw_rank += 1
        except Exception as e:
            safe_log('search', f'keyword sqlite error (fallback to semantic-only): {e}')
        finally:
            db.close()

    async def search_history(self, queries: list[str], session_name: str = '',
                             top_k: int = 10, sender_name: str = '', days: int = 0) -> list[dict]:
        """RRF 混合搜索：Vector 语义 + SQLite LIKE 关键词."""
        safe_log('search', f'ENTER: {len(queries)} queries sender={sender_name} days={days}')
        if not queries:
            return []
        valid_queries = [q for q in queries if q and q.strip()]
        if not valid_queries:
            return []

        q = valid_queries[0]
        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, dict] = {}
        K = 60
        session_ids = self._session_ids_for_search(session_name)
        vec_raw: list = []  # 默认值，vector 通道失败时使用

        # === Vector 通道 ===
        try:
            vectors = await asyncio.wait_for(
                self._plugin.invoke_embedding(self.embedding_model_uuid, [q]),
                timeout=_API_TIMEOUT,
            )
            qv = vectors[0]
            if self._embedding_dim is None:
                self._embedding_dim = len(qv)
                safe_log('store', f'embedding dim detected: {self._embedding_dim}')
            norm = math.sqrt(sum(v * v for v in qv))
            if norm > 0:
                qv = [v / norm for v in qv]
            vec_filters: dict = {"type": "chat_history"}
            if session_name:
                if len(session_ids) > 1:
                    vec_filters = {"$and": [{"type": "chat_history"}, {"session_id": {"$in": session_ids}}]}
                else:
                    vec_filters = {"$and": [{"type": "chat_history"}, {"session_id": session_name}]}
            if sender_name:
                if "$and" in vec_filters:
                    vec_filters["$and"].append({"sender_name": sender_name})
                else:
                    vec_filters = {"$and": [{"type": "chat_history"}, {"sender_name": sender_name}]}
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

        # === Keyword 通道：SQLite LIKE ===
        self._keyword_search_sqlite(
            q, session_name, top_k, sender_name, days,
            rrf_scores, doc_map, K,
        )

        # RRF 排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = [doc_map[did] for did in sorted_ids if did in doc_map]

        # 统计 keyword-only 命中数（证明 keyword 通道在工作）
        vec_ids = {e.get('id', '') for e in (vec_raw or []) if isinstance(e, dict)}
        kw_only = sum(1 for did in rrf_scores if did in doc_map and did not in vec_ids)
        safe_log('search', f'vector: {len(vec_ids)} / keyword: {len(rrf_scores) - len(vec_ids)} / keyword-only: {kw_only}')

        return results[:top_k]

    async def backfill_chat_index(self):
        """从 ChromaDB 回填 chat_index 缺失的消息（幂等，启动时 create_task 调用）.

        已回填则跳过（__backfill_done__ 持久化标记）。
        timestamp_unix=0 的历史消息从 formatted_text 时间前缀解析重算。
        """
        db = self._get_db()
        try:
            done = db.execute(
                "SELECT 1 FROM chat_index WHERE doc_id = '__backfill_done__'"
            ).fetchone()
            if done:
                db.close()
                safe_log('backfill', 'already completed, skip')
                return
        except Exception:
            pass
        db.close()

        filled = 0
        async with self._api_sem:
            db = self._get_db()
            try:
                offset = 0
                while True:
                    try:
                        result = await asyncio.wait_for(
                            self._plugin.vector_list(
                                self.kb_id,
                                filters={"type": "chat_history"},
                                limit=500, offset=offset,
                            ),
                            timeout=30,
                        )
                    except Exception as e:
                        safe_log('backfill', f'vector_list error at offset {offset}: {e}')
                        break
                    items = result.get('items', []) if isinstance(result, dict) else []
                    if not items:
                        break
                    for item in items:
                        meta = item.get('metadata', {})
                        doc_id = item.get('id')
                        text = meta.get('text', '') or item.get('document', '')
                        session_id = meta.get('session_id', '')
                        ts = meta.get('timestamp_unix', 0)
                        # 修复 timestamp_unix=0 的历史数据
                        if ts <= 0 and text.startswith('['):
                            m = re.match(r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})', text)
                            if m:
                                try:
                                    dt = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M')
                                    ts = dt.timestamp()
                                except ValueError:
                                    pass
                        try:
                            db.execute(
                                "INSERT OR IGNORE INTO chat_index (doc_id, session_id, timestamp_unix, formatted_text) VALUES (?, ?, ?, ?)",
                                (doc_id, session_id, ts, text)
                            )
                            filled += 1
                        except Exception:
                            pass
                    db.commit()
                    offset += 500
                db.execute(
                    "INSERT OR IGNORE INTO chat_index (doc_id, session_id, timestamp_unix, formatted_text) VALUES ('__backfill_done__', '', 0, '')"
                )
                db.commit()
            finally:
                db.close()
        safe_log('backfill', f'done: {filled} new rows inserted')

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
