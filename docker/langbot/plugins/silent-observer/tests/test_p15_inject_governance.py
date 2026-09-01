"""P1.5 反思注入治理测试——压制条款/头注/祈使句化/distance 门槛/软归档 vectors 修复"""
import os
import sys
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_p1_maturity_integration import TestInjectRerank  # noqa: E402 复用 _ref/_inject_once
from service.reflection import (GENERATE_PROMPT, SELF_SCAN_PROMPT, INJECT_TEMPLATE,  # noqa: E402
                                ReflectionInjector)

_HELPER = TestInjectRerank()


class TestPromptGovernance:
    """用例 1-3：生成端条款与注入头注（unit）"""

    def test_generate_prompt_imperative_rules(self):
        text = GENERATE_PROMPT.format(correction_text='a', bot_reply='b', error_types='c')
        assert '条件状语' in text and '祈使句' in text
        assert '叙述已发生的事件经过' in text

    def test_self_scan_prompt_imperative_rules(self):
        text = SELF_SCAN_PROMPT.format(recent_messages='m', error_types='c')
        assert '条件状语' in text and '祈使句' in text
        assert '叙述已发生的事件经过' in text

    def test_inject_template_header_note(self):
        assert INJECT_TEMPLATE.startswith('[先前经验 · 仅供内部参考')
        ref = {'metadata': {'when': '当用户问X时', 'then': '先确认再答', 'confirm_count': 5}}
        out = ReflectionInjector.build_reflection_prompt([ref])
        assert out.startswith('[先前经验 · 仅供内部参考')


class TestDistanceGate:
    """用例 4-6：distance 门槛（integration，真实 inject handler）"""

    async def test_mixed_distance_only_relevant_injected(self, init_listener):
        refs = [_HELPER._ref(0, distance=0.2), _HELPER._ref(1, distance=1.8)]
        ctx, _ = await _HELPER._inject_once(init_listener, refs, llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：触发0' in joined
        assert '触发条件：触发1' not in joined

    async def test_boundary_distance_injected(self, init_listener):
        """边界锁定：threshold=1.4，d=1.4 注入 / d=1.4001 丢弃（l2²=2-2cos 口径）"""
        from components.event_listener.default import _REF_INJECT_MAX_DISTANCE
        assert _REF_INJECT_MAX_DISTANCE == 1.4
        refs = [_HELPER._ref(0, distance=1.4), _HELPER._ref(1, distance=1.4001)]
        ctx, _ = await _HELPER._inject_once(init_listener, refs, llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：触发0' in joined
        assert '触发条件：触发1' not in joined

    async def test_all_far_no_injection(self, init_listener):
        refs = [_HELPER._ref(i, distance=1.8) for i in range(3)]
        ctx, _ = await _HELPER._inject_once(init_listener, refs, llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：' not in joined

    async def test_missing_or_none_distance_dropped(self, init_listener):
        r_none = _HELPER._ref(0)
        r_none['distance'] = None
        r_missing = _HELPER._ref(1)
        del r_missing['distance']
        ctx, _ = await _HELPER._inject_once(init_listener, [r_none, r_missing], llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：' not in joined

    async def test_gate_blocks_rerank_for_far_candidates(self, init_listener):
        """门槛先于 rerank：全远候选不得触发 rerank LLM 调用"""
        _, plugin, _ = init_listener
        refs = [_HELPER._ref(i, distance=1.8) for i in range(8)]
        ctx, _ = await _HELPER._inject_once(init_listener, refs, llm_resp='1,2,3')
        assert plugin.invoke_llm.await_count == 0


class TestSuppressionClause:
    """用例 7：压制条款无条件注入且位于归档之后"""

    async def test_clause_present_after_timeline(self, init_listener):
        listener, plugin, get_handler = init_listener
        listener.store.get_recent_messages = AsyncMock(return_value=[
            {'id': 'd1', 'metadata': {'text': '[2026-08-27 01:00] 张三: 归档内容甲',
                                      'timestamp_unix': 1787000000}},
        ])
        ctx, _ = await _HELPER._inject_once(init_listener, [], llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '仅供你内部理解' in joined
        assert joined.index('仅供你内部理解') > joined.index('张三: 归档内容甲')
        # 无反思命中时条款依然注入（不依赖 reflection 结果）
        assert '旁白口吻' in joined


class TestUpsertVectorsFix:
    """用例 9：1e 修复——update/archive 的 vector_upsert 必须带 vectors"""

    async def test_update_reflection_passes_vectors(self, reflection_store):
        store, plugin = reflection_store
        await store.update_reflection('ref:x1', {'scenario': 's', 'confirm_count': 2})
        kwargs = plugin.vector_upsert.call_args.kwargs
        assert 'vectors' in kwargs and len(kwargs['vectors']) == len(kwargs['ids']) == 1
        v = kwargs['vectors'][0]
        assert v and abs(sum(x * x for x in v) - 1.0) < 1e-6  # 存储侧归一化（norm 对称修复）

    async def test_archive_reflection_passes_vectors(self, reflection_store):
        store, plugin = reflection_store
        plugin.vector_list = AsyncMock(return_value={'items': [
            {'id': 'ref:x2', 'document': '{"scenario":"s"}',
             'metadata': {'type': 'reflection', 'archived': False, 'scenario': 's'}},
        ]})
        await store.archive_reflection('ref:x2')
        kwargs = plugin.vector_upsert.call_args.kwargs
        assert 'vectors' in kwargs and len(kwargs['vectors']) == 1
        assert kwargs['metadata'][0]['archived'] is True
        # 钉住修复点：embedding 取自原 document 文本（非重新 json.dumps）
        assert plugin.invoke_embedding.await_args.args[1] == ['{"scenario":"s"}']

    async def test_archive_uses_sanitize_before_upsert(self, reflection_store):
        """钉住 list→upsert 往返：list 回传的 JSON-string 字段不得被二次序列化"""
        store, plugin = reflection_store
        plugin.vector_list = AsyncMock(return_value={'items': [
            {'id': 'ref:x3', 'document': '{"scenario":"带列表的"}',
             'metadata': {'type': 'reflection', 'archived': False,
                          'entities': '["e1"]', 'source_msg_ids': '[]'}},
        ]})
        await store.archive_reflection('ref:x3')
        meta = plugin.vector_upsert.call_args.kwargs['metadata'][0]
        assert meta['entities'] == '["e1"]'  # 单重编码，防 json.loads 缺失掩盖的往返破坏
        assert meta['source_msg_ids'] == '[]'

    async def test_archive_reflection_upsert_called(self, reflection_store):
        """回归防呆：vector_list 返回空时不 upsert"""
        store, plugin = reflection_store
        await store.archive_reflection('ref:missing')
        plugin.vector_upsert.assert_not_called()

    async def test_update_failure_degrades(self, reflection_store):
        """embedding 失败时 update 吞异常记日志，不抛穿"""
        store, plugin = reflection_store
        plugin.invoke_embedding = AsyncMock(side_effect=RuntimeError('boom'))
        await store.update_reflection('ref:x4', {'scenario': 's'})
        plugin.vector_upsert.assert_not_called()
