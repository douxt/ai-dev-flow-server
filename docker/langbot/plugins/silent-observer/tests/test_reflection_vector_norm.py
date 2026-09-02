"""向量归一化对称 + l2² cosine 换算测试（reflect-dist-norm-fix）

背景实证：chroma 集合默认 l2² 空间；修复前存储 norm=1.86 vs 查询 norm=1.0
→ 同句距离下限 (1.86-1)²=0.74，旧门槛 0.45 数学不可达；find_duplicate
误用 cosine 空间公式 1-d。本文件锁定三处修复。
"""
import math
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


class TestNormVec:
    def test_normalizes_to_unit(self, reflection_store):
        store, _ = reflection_store
        v = store._norm_vec([0.1] * 384)
        assert abs(_norm(v) - 1.0) < 1e-9

    def test_inflated_norm_1_86_case(self, reflection_store):
        """实测 seekdb-local 输出 norm≈1.86 的等价构造"""
        store, _ = reflection_store
        raw = [x * 1.86 for x in [1 / math.sqrt(384)] * 384]
        v = store._norm_vec(raw)
        assert abs(_norm(v) - 1.0) < 1e-9

    def test_zero_vector_passthrough(self, reflection_store):
        store, _ = reflection_store
        assert store._norm_vec([0.0] * 4) == [0.0] * 4


class TestWriteSideNormalized:
    async def test_store_reflection_upserts_unit_vector(self, reflection_store):
        store, plugin = reflection_store
        # conftest mock: invoke_embedding → [[0.1]*384]（norm≈1.96，即生产症状）
        await store.store_reflection({'when': 'w', 'then': 't', 'scenario': 's'})
        kwargs = plugin.vector_upsert.call_args.kwargs
        assert abs(_norm(kwargs['vectors'][0]) - 1.0) < 1e-6

    async def test_embed_normalizes_update_path(self, reflection_store):
        store, plugin = reflection_store
        await store.update_reflection('ref:x', {'when': 'w', 'then': 't', 'confirm_count': 2})
        kwargs = plugin.vector_upsert.call_args.kwargs
        assert abs(_norm(kwargs['vectors'][0]) - 1.0) < 1e-6

    async def test_embed_result_unit(self, reflection_store):
        store, _ = reflection_store
        out = await store._embed('some text')
        assert abs(_norm(out[0]) - 1.0) < 1e-9


class TestFindDuplicateL2Formula:
    """对称归一化后 cosine = 1 - d/2；direct>0.85 / candidate(0.70,0.85]"""

    async def _dup(self, store, distance):
        entries = [{'id': 'ref:x', 'document': 'doc',
                    'metadata': {'type': 'reflection', 'archived': False},
                    'distance': distance}]
        store._plugin.vector_search = AsyncMock(return_value=entries)
        return await store.find_duplicate('场景', '错误', entities=[])

    async def test_direct(self, reflection_store):
        store, _ = reflection_store
        doc_id, _, level = await self._dup(store, 0.1)   # cos=0.95
        assert level == 'direct' and doc_id == 'ref:x'

    async def test_candidate(self, reflection_store):
        store, _ = reflection_store
        _, _, level = await self._dup(store, 0.45)       # cos=0.775
        assert level == 'candidate'

    async def test_none_far(self, reflection_store):
        store, _ = reflection_store
        _, _, level = await self._dup(store, 1.0)        # cos=0.5
        assert level == 'none'

    async def test_clamp_beyond_2(self, reflection_store):
        store, _ = reflection_store
        _, _, level = await self._dup(store, 2.5)        # 1-1.25<0 → clamp 0
        assert level == 'none'

    async def test_old_formula_would_misjudge(self, reflection_store):
        """d=0.2 旧公式判 direct(cos=0.8? no, 1-0.2=0.8→candidate)，新公式 cos=0.9→direct
        ——用方向性断言锁住两公式分歧点"""
        store, _ = reflection_store
        _, _, level = await self._dup(store, 0.2)        # 新 cos=0.9 → direct
        assert level == 'direct'


class TestStartupMigration:
    """vnorm 戳 + 启动自愈：旧格式（无戳）重算归一写回，带戳跳过（幂等）"""

    async def test_store_reflection_stamps_vnorm(self, reflection_store):
        store, plugin = reflection_store
        await store.store_reflection({'when': 'w', 'then': 't', 'scenario': 's'})
        assert plugin.vector_upsert.call_args.kwargs['metadata'][0]['vnorm'] == 'unit'

    async def test_migrate_only_legacy_and_normalizes(self, reflection_store):
        store, plugin = reflection_store
        plugin.vector_list = AsyncMock(return_value={'items': [
            {'id': 'ref:legacy', 'document': '{"scenario":"s"}',
             'metadata': {'type': 'reflection', 'archived': False, 'scenario': 's'}},
            {'id': 'ref:tagged', 'document': '{"scenario":"t"}',
             'metadata': {'type': 'reflection', 'archived': False, 'vnorm': 'unit'}},
        ]})
        n = await store.migrate_unit_vectors()
        assert n == 1
        kwargs = plugin.vector_upsert.call_args.kwargs
        assert kwargs['ids'] == ['ref:legacy']
        assert abs(sum(x * x for x in kwargs['vectors'][0]) - 1.0) < 1e-6
        assert kwargs['metadata'][0]['vnorm'] == 'unit'
        # document 原文不重造、list 回传的 JSON-string 字段不二次序列化
        assert kwargs['documents'] == ['{"scenario":"s"}']

    async def test_migrate_idempotent_second_run(self, reflection_store):
        store, plugin = reflection_store
        plugin.vector_list = AsyncMock(return_value={'items': [
            {'id': 'ref:tagged', 'document': 'd',
             'metadata': {'type': 'reflection', 'archived': False, 'vnorm': 'unit'}},
        ]})
        assert await store.migrate_unit_vectors() == 0
        plugin.vector_upsert.assert_not_called()


class TestInjectThresholdSemantics:
    def test_threshold_constant(self):
        from components.event_listener.default import _REF_INJECT_MAX_DISTANCE
        assert _REF_INJECT_MAX_DISTANCE == 1.4

    def test_empirical_anchor_passes(self):
        """实证锚点：强相关样本 cos≈0.39 → 对称后 d=2-2*0.39=1.22 < 1.4 放行"""
        from components.event_listener.default import _REF_INJECT_MAX_DISTANCE
        d = 2 - 2 * 0.39
        assert d <= _REF_INJECT_MAX_DISTANCE
        # 不相关文本典型 cos 0.1-0.2 → d 1.6-1.8 挡外
        assert (2 - 2 * 0.2) > _REF_INJECT_MAX_DISTANCE
