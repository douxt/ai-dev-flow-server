"""P1 对话成熟度 Store 层测试 — 真实 ReflectionStore + mock plugin"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _valid_reflection(**overrides):
    d = {
        "when": "用户问电气相关技术问题时",
        "then": "先确认电压等级和用电场景，再给方案",
        "scenario": "群聊中用户问电气选型问题",
        "error_type": "事实错误",
        "mistake": "直接给出了错误型号",
        "correct_approach": "先确认电压等级和用电场景（工业380V或民用220V），再根据功率计算选择合适的型号",
        "how_to_avoid": "遇到电气问题先确认前提条件",
        "verifiable_test": "下次先询问电压和场景再回答",
        "domain": "electrical",
        "entities": ["电气"],
        "trigger_keywords": ["电气"],
    }
    d.update(overrides)
    return d


def _entry(rid, distance, **meta_overrides):
    meta = {'type': 'reflection', 'archived': False, 'importance': 'low', **meta_overrides}
    return {'id': rid, 'document': 'doc', 'metadata': meta, 'distance': distance}


class TestSearchSimilar:
    async def test_topk_passthrough_no_truncation(self, reflection_store):
        store, plugin = reflection_store
        entries = [_entry(f'r{i}', 0.1) for i in range(12)]
        plugin.vector_search = AsyncMock(return_value=entries)
        results = await store.search_similar('q', top_k=10)
        assert len(results) == 12  # 无 [:3] 硬截断
        assert plugin.vector_search.await_args.kwargs['top_k'] == 10

    async def test_importance_sort(self, reflection_store):
        store, plugin = reflection_store
        entries = [
            _entry('low', 0.1, importance='low'),
            _entry('high', 0.5, importance='high'),
            _entry('med', 0.3, importance='medium'),
        ]
        plugin.vector_search = AsyncMock(return_value=entries)
        results = await store.search_similar('q', top_k=10)
        assert [r['id'] for r in results] == ['high', 'med', 'low']

    async def test_list_fields_deserialized(self, reflection_store):
        store, plugin = reflection_store
        entries = [_entry('r1', 0.1, entities=json.dumps(['电气']),
                          source_msg_ids=json.dumps(['s1']),
                          trigger_keywords=json.dumps(['k1']),
                          confirm_sources=json.dumps(['c1']),
                          linked_entities=json.dumps(['l1']))]
        plugin.vector_search = AsyncMock(return_value=entries)
        results = await store.search_similar('q', top_k=10)
        assert results[0]['metadata']['entities'] == ['电气']
        assert results[0]['metadata']['source_msg_ids'] == ['s1']

    async def test_domain_filter(self, reflection_store):
        store, plugin = reflection_store
        await store.search_similar('q', top_k=5, domain='electrical')
        filters = plugin.vector_search.await_args.kwargs['filters']
        assert {'domain': 'electrical'} in filters['$and']

    async def test_exception_returns_empty(self, reflection_store):
        store, plugin = reflection_store
        plugin.vector_search = AsyncMock(side_effect=RuntimeError('boom'))
        assert await store.search_similar('q', top_k=5) == []


class TestFindDuplicate:
    async def _dup(self, reflection_store, entries, entities=None):
        store, plugin = reflection_store
        plugin.vector_search = AsyncMock(return_value=entries)
        return await store.find_duplicate('场景', '错误', entities or ['电气'])

    async def test_direct(self, reflection_store):
        doc_id, meta, level = await self._dup(reflection_store, [_entry('ref:x', 0.05)])
        assert level == 'direct' and doc_id == 'ref:x'  # cosine 0.95

    async def test_candidate(self, reflection_store):
        doc_id, _, level = await self._dup(reflection_store, [_entry('ref:x', 0.2)])
        assert level == 'candidate'  # cosine 0.8

    async def test_entity_link(self, reflection_store):
        doc_id, meta, level = await self._dup(
            reflection_store, [_entry('ref:x', 0.99, entities=['电气'])])
        assert level == 'entity_link' and meta['linked_entities'] == ['电气']

    async def test_none(self, reflection_store):
        doc_id, _, level = await self._dup(
            reflection_store, [_entry('ref:x', 0.99, entities=['其他'])], entities=['电气'])
        assert level == 'none' and doc_id is None

    async def test_no_results_none(self, reflection_store):
        doc_id, _, level = await self._dup(reflection_store, [])
        assert level == 'none'

    async def test_error(self, reflection_store):
        store, plugin = reflection_store
        plugin.vector_search = AsyncMock(side_effect=RuntimeError('boom'))
        _, _, level = await store.find_duplicate('场景', '错误', ['电气'])
        assert level == 'error'


class TestStoreReflection:
    async def test_write_params(self, reflection_store):
        store, plugin = reflection_store
        doc_id = await store.store_reflection(_valid_reflection())
        assert doc_id.startswith('ref:')
        plugin.vector_upsert.assert_awaited()
        kwargs = plugin.vector_upsert.call_args.kwargs
        assert kwargs['ids'] == [doc_id]
        assert kwargs['metadata'][0]['type'] == 'reflection'
        assert '"when"' in kwargs['documents'][0]
        assert '"then"' in kwargs['documents'][0]

    async def test_write_error_returns_empty(self, reflection_store):
        store, plugin = reflection_store
        plugin.vector_upsert = AsyncMock(side_effect=RuntimeError('boom'))
        assert await store.store_reflection(_valid_reflection()) == ''
