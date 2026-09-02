"""反思存储层 — 独立 ChromaDB collection + 三级去重 + 衰减归档.

2026-09-02 B 线批量化：四层 rate limit 整体拆除（位置错位缺陷：检测前消耗配额），
节奏控制移至 service/consolidator.py 的触发阈值+最小间隔+日 cap。"""
import asyncio
import hashlib
import json
import math
import sys
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

    @staticmethod
    def _norm_vec(v: list[float]) -> list[float]:
        """L2 归一化。集合无 space 配置=chroma 默认 l2²，查询/存储必须对称归一，
        否则距离被模长差撑爆（实测 norm 1 vs 1.86 → 同句距离下限 0.74，门槛永不可达）。"""
        norm = math.sqrt(sum(x * x for x in v))
        return [x / norm for x in v] if norm > 0 else v

    # ── 向量检索 ────────────────────────────────────────────

    async def search_similar(self, query: str, top_k: int = 5, domain: str | None = None) -> list[dict]:
        """语义搜索反思 collection，可选 domain 过滤."""
        try:
            vectors = await asyncio.wait_for(
                self._plugin.invoke_embedding(self.embedding_model_uuid, [query]),
                timeout=_API_TIMEOUT,
            )
            qv = self._norm_vec(vectors[0])
            if self._embedding_dim is None:
                self._embedding_dim = len(qv)

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
        """ChromaDB metadata 不支持 list/dict 嵌套，序列化为 JSON string.
        统一盖 vnorm 戳：声明本条目的存储向量已归一化（norm=1），
        启动迁移据此识别旧格式条目（list_by_filter 不回传向量，无法直接实测 norm）."""
        clean = {}
        for k, v in meta.items():
            if isinstance(v, (list, dict)):
                clean[k] = json.dumps(v, ensure_ascii=False)
            else:
                clean[k] = v
        clean['vnorm'] = 'unit'
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
                vectors = [self._norm_vec(vectors[0])]
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
        """重算单条文本 embedding（upsert 必填 vectors，list_by_filter 不回传向量）.
        返回已归一化向量——update/archive 调用点全部继承，与查询侧对称."""
        vectors = await asyncio.wait_for(
            self._plugin.invoke_embedding(self.embedding_model_uuid, [text]),
            timeout=_API_TIMEOUT,
        )
        return [self._norm_vec(vectors[0])]

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
            qv = self._norm_vec(vectors[0])

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

            # 对称归一化下 l2² = 2-2cos → cosine = 1 - d/2（旧公式 1-d 是 cosine 空间口径，
            # 集合实为 chroma 默认 l2²，2026-08-31 探针实锤后纠正）
            def _cos(entry: dict) -> float:
                d = entry.get('distance', 99)
                return max(0.0, min(1.0, 1.0 - d / 2.0))

            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                existing = entry.get('metadata', {})

                if _cos(entry) > 0.85:
                    return entry.get('id', ''), existing, 'direct'

            # 二级：0.70-0.85 候选
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                if 0.70 < _cos(entry) <= 0.85:
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

    async def migrate_unit_vectors(self) -> int:
        """启动自愈：旧格式（norm≠1，无 vnorm 戳）条目重算归一化向量写回。
        幂等：新写入均带 vnorm 戳，迁移过的下次启动跳过。返回迁移条数."""
        try:
            items = await self.list_all()
        except Exception as e:
            safe_log('reflection', f'vector-migrate list error: {e}')
            return 0
        migrated = 0
        for it in items:
            if not isinstance(it, dict):
                continue
            meta = it.get('metadata') or {}
            if meta.get('vnorm') == 'unit':
                continue
            doc_id = it.get('id', '')
            text = it.get('document') or json.dumps(meta, ensure_ascii=False)
            try:
                async with self._api_sem:
                    vectors = await self._embed(text)
                    await asyncio.wait_for(
                        self._plugin.vector_upsert(
                            collection_id=REFLECTION_COLLECTION,
                            vectors=vectors,
                            ids=[doc_id],
                            metadata=[self._sanitize_metadata({**meta, 'type': 'reflection'})],
                            documents=[text],
                        ),
                        timeout=_API_TIMEOUT,
                    )
                migrated += 1
            except Exception as e:
                safe_log('reflection', f'vector-migrate error {doc_id}: {e}')
        if migrated:
            safe_log('reflection', f'vector-migrate: normalized {migrated} legacy entries')
        return migrated

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
            meta = dict(items[0].get('metadata', {}))  # 副本，避免污染调用方数据
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
