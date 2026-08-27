"""反思存储层 — 独立 ChromaDB collection + 三级去重 + 四层 rate limit + 衰减归档."""
import asyncio
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone, timedelta

from util.logs import safe_log

_API_TIMEOUT = 30
REFLECTION_COLLECTION = "silent_reflections"
BJT = timezone(timedelta(hours=8))


class ReflectionStore:
    """反思 CRUD：自动创建 collection、向量检索、三级去重、衰减归档、rate limit."""

    def __init__(self, plugin, embedding_model_uuid: str):
        self._plugin = plugin
        self.embedding_model_uuid = embedding_model_uuid
        self._embedding_dim: int | None = None
        self._api_sem = asyncio.Semaphore(3)

    # ── 维度探测 ────────────────────────────────────────────

    async def _detect_dim(self) -> int:
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
                return dim
        except Exception as e:
            safe_log('reflection', f'dimension probe failed: {e}')
        self._embedding_dim = 384
        return 384

    @property
    def embedding_dim(self) -> int:
        return self._embedding_dim or 384

    # ── 向量检索 ────────────────────────────────────────────

    async def search_similar(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict]:
        """语义搜索反思 collection，可选 domain 过滤."""
        try:
            vectors = await asyncio.wait_for(
                self._plugin.invoke_embedding(self.embedding_model_uuid, [query]),
                timeout=_API_TIMEOUT,
            )
            qv = vectors[0]
            dim = len(qv)
            if self._embedding_dim is None:
                self._embedding_dim = dim
            norm = math.sqrt(sum(v * v for v in qv))
            if norm > 0:
                qv = [v / norm for v in qv]

            filters: dict = {"$and": [{"type": "reflection"}, {"archived": False}]}
            if domain:
                filters = {"$and": [{"type": "reflection"}, {"archived": False}, {"domain": domain}]}

            raw = await asyncio.wait_for(
                self._plugin.vector_search(
                    collection_id=REFLECTION_COLLECTION,
                    query_vector=qv,
                    top_k=top_k,
                    filters=filters,
                ),
                timeout=_API_TIMEOUT,
            )
            results = []
            for entry in (raw or []):
                if not isinstance(entry, dict):
                    continue
                meta = entry.get('metadata', {}) or {}
                # 反序列化 JSON string → list（entities, source_msg_ids 等）
                for list_field in ('entities', 'source_msg_ids', 'linked_entities',
                                   'confirm_sources', 'trigger_keywords'):
                    if isinstance(meta.get(list_field), str):
                        try:
                            meta[list_field] = json.loads(meta[list_field])
                        except (json.JSONDecodeError, TypeError):
                            pass
                results.append({
                    'id': entry.get('id', ''),
                    'document': entry.get('document', ''),
                    'metadata': meta,
                    'distance': entry.get('distance', 99),
                })
            # 按 importance 排序：high > medium > low
            # ⚠️ 不再硬截断 top-3——P1.3 返回完整 top_k 交 LLM rerank 精选
            imp_order = {'high': 0, 'medium': 1, 'low': 2}
            results.sort(key=lambda x: imp_order.get(x.get('metadata', {}).get('importance', 'low'), 2))
            return results
        except Exception as e:
            safe_log('reflection', f'search error: {e}')
            return []

    # ── 写入 ────────────────────────────────────────────────

    @staticmethod
    def _sanitize_metadata(meta: dict) -> dict:
        """ChromaDB metadata 不支持 list/dict 嵌套，序列化为 JSON string."""
        clean = {}
        for k, v in meta.items():
            if isinstance(v, (list, dict)):
                clean[k] = json.dumps(v, ensure_ascii=False)
            else:
                clean[k] = v
        return clean

    async def store_reflection(self, reflection: dict) -> str:
        """存储新反思，返回 doc_id."""
        text = json.dumps(reflection, ensure_ascii=False)
        doc_id = f"ref:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
        metadata = self._sanitize_metadata({**reflection, "type": "reflection"})
        try:
            async with self._api_sem:
                vectors = await asyncio.wait_for(
                    self._plugin.invoke_embedding(self.embedding_model_uuid, [text]),
                    timeout=_API_TIMEOUT,
                )
                await asyncio.wait_for(
                    self._plugin.vector_upsert(
                        collection_id=REFLECTION_COLLECTION,
                        vectors=vectors,
                        ids=[doc_id],
                        metadata=[metadata],
                        documents=[text],
                    ),
                    timeout=_API_TIMEOUT,
                )
            safe_log('reflection', f'stored: {doc_id} scenario={reflection.get("scenario", "")[:40]}')
            return doc_id
        except Exception as e:
            safe_log('reflection', f'store error: {e}')
            return ""

    async def _embed(self, text: str) -> list[list[float]]:
        """重算单条文本 embedding（upsert 必填 vectors，list_by_filter 不回传向量）."""
        return await asyncio.wait_for(
            self._plugin.invoke_embedding(self.embedding_model_uuid, [text]),
            timeout=_API_TIMEOUT,
        )

    async def update_reflection(self, doc_id: str, reflection: dict):
        """更新已有反思（confirm_count 递增等）."""
        text = json.dumps(reflection, ensure_ascii=False)
        metadata = self._sanitize_metadata({**reflection, "type": "reflection"})
        try:
            async with self._api_sem:
                vectors = await self._embed(text)
                await asyncio.wait_for(
                    self._plugin.vector_upsert(
                        collection_id=REFLECTION_COLLECTION,
                        vectors=vectors,
                        ids=[doc_id],
                        metadata=[metadata],
                        documents=[text],
                    ),
                    timeout=_API_TIMEOUT,
                )
            safe_log('reflection', f'updated: {doc_id} confirm={reflection.get("confirm_count", 0)}')
        except Exception as e:
            safe_log('reflection', f'update error: {e}')

    # ── 三级去重 ────────────────────────────────────────────

    async def find_duplicate(self, scenario: str, mistake: str, entities: list[str]) -> tuple[str | None, dict | None, str]:
        """
        三级去重：
        1. cosine > 0.85 → 直接合并 (level='direct')
        2. cosine 0.70-0.85 → 返回候选让调用方 LLM 判断 (level='candidate')
        3. 实体重叠 → 软链接 (level='entity_link')
        返回 (doc_id, existing_metadata, level)
        """
        query = f"{scenario} {mistake}"
        try:
            vectors = await asyncio.wait_for(
                self._plugin.invoke_embedding(self.embedding_model_uuid, [query]),
                timeout=_API_TIMEOUT,
            )
            qv = vectors[0]
            norm = math.sqrt(sum(v * v for v in qv))
            if norm > 0:
                qv = [v / norm for v in qv]

            raw = await asyncio.wait_for(
                self._plugin.vector_search(
                    collection_id=REFLECTION_COLLECTION,
                    query_vector=qv,
                    top_k=5,
                    filters={"type": "reflection"},
                ),
                timeout=_API_TIMEOUT,
            )
            if not raw:
                return None, None, 'none'

            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                distance = entry.get('distance', 99)
                cosine = 1.0 - distance if distance < 2 else 0.0
                existing = entry.get('metadata', {})

                if cosine > 0.85:
                    return entry.get('id', ''), existing, 'direct'

            # 二级：0.70-0.85 候选
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                distance = entry.get('distance', 99)
                cosine = 1.0 - distance if distance < 2 else 0.0
                if 0.70 < cosine <= 0.85:
                    return entry.get('id', ''), entry.get('metadata', {}), 'candidate'

            # 三级：实体重叠
            if entities:
                existing_entities = set()
                for entry in raw:
                    if not isinstance(entry, dict):
                        continue
                    meta = entry.get('metadata', {})
                    existing_entities.update(meta.get('entities', []))
                overlap = set(entities) & existing_entities
                if overlap:
                    return None, {'linked_entities': list(overlap)}, 'entity_link'

            return None, None, 'none'
        except Exception as e:
            safe_log('reflection', f'find_duplicate error: {e}')
            return None, None, 'error'

    # ── 衰减与归档 ──────────────────────────────────────────

    async def list_all(self, limit: int = 200, offset: int = 0) -> list[dict]:
        """列出所有反思（衰减扫描用）."""
        try:
            raw = await asyncio.wait_for(
                self._plugin.vector_list(
                    REFLECTION_COLLECTION,
                    filters={"type": "reflection"},
                    limit=limit, offset=offset,
                ),
                timeout=_API_TIMEOUT,
            )
            return raw.get('items', []) if isinstance(raw, dict) else []
        except Exception as e:
            safe_log('reflection', f'list_all error: {e}')
            return []

    async def archive_reflection(self, doc_id: str):
        """归档反思（设置 archived=True，保留在 collection 但不参与检索）."""
        safe_log('reflection', f'archive: {doc_id}')
        try:
            # 先读取当前 metadata
            raw = await asyncio.wait_for(
                self._plugin.vector_list(
                    REFLECTION_COLLECTION,
                    filters={"$and": [{"type": "reflection"}, {"id": doc_id}]},
                    limit=1, offset=0,
                ),
                timeout=_API_TIMEOUT,
            )
            items = raw.get('items', []) if isinstance(raw, dict) else []
            if not items:
                return
            meta = items[0].get('metadata', {})
            meta['archived'] = True
            meta['archived_at'] = datetime.now(BJT).isoformat()
            text = items[0].get('document') or json.dumps(meta, ensure_ascii=False)
            vectors = await self._embed(text)
            await asyncio.wait_for(
                self._plugin.vector_upsert(
                    collection_id=REFLECTION_COLLECTION,
                    vectors=vectors,
                    ids=[doc_id],
                    metadata=[self._sanitize_metadata({**meta, "type": "reflection"})],
                    documents=[text],
                ),
                timeout=_API_TIMEOUT,
            )
        except Exception as e:
            safe_log('reflection', f'archive error: {e}')

    def should_decay(self, reflection_meta: dict) -> str | None:
        """
        判断是否需要衰减。返回:
        - 'archive': 90天未命中 → 归档
        - 'downgrade': 30天未命中 → 降权
        - None: 不需要操作
        """
        last_hit = reflection_meta.get('last_hit')
        if not last_hit:
            return None  # 刚创建，未到首次衰减检查
        try:
            last = datetime.fromisoformat(last_hit)
            now = datetime.now(BJT)
            days = (now - last).days
            if days >= 90:
                return 'archive'
            if days >= 30 and reflection_meta.get('importance', 'low') != 'low':
                return 'downgrade'
        except Exception:
            pass
        return None

    # ── Rate Limit ──────────────────────────────────────────

    async def check_rate_limit(self, session_name: str, sender_id: str) -> bool:
        """
        四层限流检查。返回 True 允许生成，False 拒绝。
        计数器存储在 plugin_storage，key='reflection_rate_state'.
        """
        try:
            raw = await self._plugin.get_plugin_storage('reflection_rate_state')
            state = json.loads(raw if isinstance(raw, str) else raw.decode('utf-8')) if raw else {}
        except Exception:
            state = {}

        now = time.time()
        today = datetime.now(BJT).strftime('%Y-%m-%d')
        hour = datetime.now(BJT).strftime('%Y-%m-%dT%H')

        # 重置过期计数器
        if state.get('day') != today:
            state = {'day': today, 'day_count': 0, 'hour': hour, 'hour_count': 0,
                     'session_windows': {}, 'sender_windows': {}}
        if state.get('hour') != hour:
            state['hour'] = hour
            state['hour_count'] = 0

        # 每日上限（默认 20）
        daily_limit = 20
        if state.get('day_count', 0) >= daily_limit:
            safe_log('reflection', f'rate_limit: daily cap ({daily_limit})')
            return False

        # 每小时上限（默认 5）
        hourly_limit = 5
        if state.get('hour_count', 0) >= hourly_limit:
            safe_log('reflection', f'rate_limit: hourly cap ({hourly_limit})')
            return False

        # 同 session 冷却：5 分钟内最多 2 条
        session_windows = state.get('session_windows', {})
        session_times = session_windows.get(session_name, [])
        session_times = [t for t in session_times if now - t < 300]
        if len(session_times) >= 2:
            safe_log('reflection', f'rate_limit: session cooldown ({session_name})')
            return False

        # 同 sender 冷却：10 分钟内最多 1 条
        sender_windows = state.get('sender_windows', {})
        sender_last = sender_windows.get(sender_id, 0)
        if now - sender_last < 600:
            safe_log('reflection', f'rate_limit: sender cooldown ({sender_id})')
            return False

        # 更新计数器
        state['day_count'] = state.get('day_count', 0) + 1
        state['hour_count'] = state.get('hour_count', 0) + 1
        session_times.append(now)
        session_windows[session_name] = session_times
        sender_windows[sender_id] = now
        state['session_windows'] = session_windows
        state['sender_windows'] = sender_windows

        try:
            await self._plugin.set_plugin_storage('reflection_rate_state', json.dumps(state).encode('utf-8'))
        except Exception:
            pass

        return True
