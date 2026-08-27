"""P1 对话成熟度集成测试 — 全链路 mock LLM + vector API + 真实 handler 闭包"""
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conftest import FakePlain  # noqa: E402


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


VALID_JSON = json.dumps(_valid_reflection(), ensure_ascii=False)


def _ten_msgs():
    return [{'metadata': {'text': f'[2026-08-21 10:{i:02d}] 用户{i}: 你好'}} for i in range(10)]


def _gen_prompt(listener, call_idx):
    """取第 call_idx 次 invoke_llm 的 prompt 文本"""
    return listener.plugin.invoke_llm.call_args_list[call_idx].kwargs['messages'][0].content


class TestCorrectionChain:
    """场景 1-3：纠正全链路（_maybe_generate_reflection）"""

    async def test_full_chain(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, ['补全句：你说错了，应该用DS920+', 'YES', VALID_JSON])
        event = SimpleNamespace(message_chain=None, sender_id='u1')
        await reflection_listener._maybe_generate_reflection(event, 'group_t', user_text='不对，你搞错了', sender_id='u1')
        assert reflection_listener.plugin.invoke_llm.call_count == 3  # rewrite+stage2+generate
        reflection_listener.plugin.vector_upsert.assert_awaited()
        docs = reflection_listener.plugin.vector_upsert.call_args.kwargs['documents'][0]
        assert '"when"' in docs and '"then"' in docs
        assert '补全句：你说错了' in _gen_prompt(reflection_listener, 2)  # generate 用补全句

    async def test_rewrite_exception_fallback(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, [RuntimeError('boom'), 'YES', VALID_JSON])
        event = SimpleNamespace(message_chain=None, sender_id='u1')
        await reflection_listener._maybe_generate_reflection(event, 'group_t', user_text='不对，你搞错了', sender_id='u1')
        reflection_listener.plugin.vector_upsert.assert_awaited()
        assert '不对，你搞错了' in _gen_prompt(reflection_listener, 2)  # 原文进 generate

    async def test_rewrite_rejected_original_retry(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, ['补全句：不对，你搞错了，应该用DS920+', 'NO', 'YES', VALID_JSON])
        event = SimpleNamespace(message_chain=None, sender_id='u1')
        await reflection_listener._maybe_generate_reflection(event, 'group_t', user_text='不对，你搞错了', sender_id='u1')
        assert reflection_listener.plugin.invoke_llm.call_count == 4  # rewrite+stage2×2+generate
        reflection_listener.plugin.vector_upsert.assert_awaited()
        assert '不对，你搞错了' in _gen_prompt(reflection_listener, 3)  # 原文重试通过

    async def test_both_rejected_no_store(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, ['补全句', 'NO', 'NO'])
        event = SimpleNamespace(message_chain=None, sender_id='u1')
        await reflection_listener._maybe_generate_reflection(event, 'group_t', user_text='不对，你搞错了', sender_id='u1')
        reflection_listener.plugin.vector_upsert.assert_not_awaited()


class TestSelfReflect:
    """场景 4-8：_bump_reflection_counter + _maybe_self_reflect"""

    def _trigger(self, listener):
        listener._reflection_round_count = 9
        listener._bump_reflection_counter('group_t')
        return listener._bg_queue.get_nowait()

    async def test_trigger_at_10th_round(self, reflection_listener, scripted_llm):
        reflection_listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())
        scripted_llm(reflection_listener, [VALID_JSON])
        await self._trigger(reflection_listener)
        assert reflection_listener.plugin.invoke_llm.call_count == 1  # 仅 scan
        reflection_listener.plugin.vector_upsert.assert_awaited()

    async def test_scan_none_no_store(self, reflection_listener, scripted_llm):
        reflection_listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())
        scripted_llm(reflection_listener, ['NONE'])
        await self._trigger(reflection_listener)
        reflection_listener.plugin.vector_upsert.assert_not_awaited()

    async def test_dedup_merge(self, reflection_listener, scripted_llm):
        reflection_listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())
        reflection_listener.plugin.vector_search = AsyncMock(return_value=[
            {'id': 'ref:abc', 'metadata': {'confirm_count': 1, 'importance': 'low'}, 'distance': 0.01},
        ])
        scripted_llm(reflection_listener, [VALID_JSON])
        await self._trigger(reflection_listener)
        kwargs = reflection_listener.plugin.vector_upsert.call_args.kwargs
        assert kwargs['ids'] == ['ref:abc']  # update 而非新存
        assert kwargs['metadata'][0]['confirm_count'] == 2
        assert kwargs['metadata'][0]['when']  # when/then backfill

    async def test_rate_limited_no_llm(self, reflection_listener):
        reflection_listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())
        reflection_listener.reflection_store.check_rate_limit = AsyncMock(return_value=False)
        await self._trigger(reflection_listener)
        reflection_listener.plugin.invoke_llm.assert_not_awaited()

    async def test_not_yet_triggered(self, reflection_listener):
        reflection_listener._reflection_round_count = 5
        reflection_listener._bump_reflection_counter('group_t')
        assert reflection_listener._reflection_round_count == 6
        assert reflection_listener._bg_queue.empty()
        reflection_listener.plugin.invoke_llm.assert_not_awaited()


class TestInjectRerank:
    """场景 9-12：inject 路径真实 handler 闭包（完整 initialize）"""

    def _ref(self, i, with_when_then=True, distance=0.1):
        meta = {'confirm_count': 5, 'scenario': f'场景{i}', 'mistake': f'错误{i}',
                'correct_approach': f'做法{i}', 'importance': 'low'}
        if with_when_then:
            meta.update({'when': f'触发{i}', 'then': f'应对{i}'})
        return {'id': f'r{i}', 'document': f'doc{i}', 'metadata': meta, 'distance': distance}

    async def _inject_once(self, init_listener, refs, llm_resp=None, llm_exc=None):
        """设置 last_trigger + search_similar mock，跑一次 inject handler"""
        listener, plugin, get_handler = init_listener
        from langbot_plugin.api.entities import events
        from store.kb_store import canonical_session_name
        listener._last_trigger[canonical_session_name('group_t')] = ('at', 'doc1', [FakePlain(text='电气问题')])
        listener.reflection_store.search_similar = AsyncMock(return_value=refs)
        if llm_exc:
            plugin.invoke_llm = AsyncMock(side_effect=llm_exc)
        else:
            plugin.invoke_llm = AsyncMock(return_value=llm_resp)
        ctx = SimpleNamespace(event=SimpleNamespace(session_name='group_t', prompt=[]), query_id='q1')
        await get_handler(events.PromptPreProcessing)(ctx)
        return ctx, plugin

    async def test_rerank_normal(self, init_listener):
        ctx, plugin = await self._inject_once(init_listener, [self._ref(i) for i in range(8)], llm_resp='3,1,5')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        # rerank "3,1,5" = 候选 1-based 索引 → candidates[2],[0],[4]（when=触发2/0/4）
        idx = [joined.index(f'触发条件：触发{i}') for i in (2, 0, 4)]
        assert idx == sorted(idx)  # 按重排顺序注入
        assert plugin.invoke_llm.call_count == 1  # 仅 rerank 一次
        assert '触发条件：触发5' not in joined  # 未选中的不进

    async def test_rerank_none_no_inject(self, init_listener):
        ctx, _ = await self._inject_once(init_listener, [self._ref(i) for i in range(8)], llm_resp='NONE')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        # P1.5 后"先前经验"字样也出现在压制条款中，断言锚定注入模板特有文本
        assert '触发条件：' not in joined

    async def test_rerank_exception_degrades_to_first5(self, init_listener):
        ctx, _ = await self._inject_once(init_listener, [self._ref(i) for i in range(8)], llm_exc=[RuntimeError('boom')])
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：触发0' in joined  # 原前 5 降级
        assert '触发条件：触发6' not in joined

    async def test_old_data_fallback(self, init_listener):
        # 旧记录：无 when/then → scenario/correct_approach 降级
        ctx, _ = await self._inject_once(
            init_listener, [self._ref(i, with_when_then=False) for i in range(3)], llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：场景0' in joined
        assert '应对方式：做法0' in joined

    async def test_less_than_5_no_rerank(self, init_listener):
        """护栏①：≤5 条直接注入，不调 rerank"""
        listener, plugin, _ = init_listener
        ctx, _ = await self._inject_once(init_listener, [self._ref(i) for i in range(3)], llm_resp='')
        joined = '\n'.join(str(m.content) for m in ctx.event.prompt)
        assert '触发条件：触发0' in joined and '触发条件：触发2' in joined
        assert plugin.invoke_llm.await_count == 0  # 无 rerank 调用

    async def test_search_top10_no_truncation(self, init_listener):
        """场景 12：search_similar 回归（P1.3）——k=10 无硬截断"""
        plugin = init_listener[1]
        entries = []
        for i in range(10):
            entries.append({'id': f'r{i}', 'document': f'doc{i}',
                            'metadata': {'importance': 'low' if i % 2 else 'high',
                                         'entities': json.dumps(['e1']),
                                         'source_msg_ids': json.dumps(['s1']),
                                         'trigger_keywords': json.dumps(['k1']),
                                         'confirm_sources': json.dumps(['c1']),
                                         'linked_entities': json.dumps(['l1']),
                                         'type': 'reflection', 'archived': False},
                            'distance': 0.1})
        plugin.vector_search = AsyncMock(return_value=entries)
        store = init_listener[0].reflection_store
        results = await store.search_similar('电气问题', top_k=10)
        assert len(results) == 10  # 无截断
        assert plugin.vector_search.await_args.kwargs['top_k'] == 10
        # importance 排序：high 在前
        imps = [r['metadata']['importance'] for r in results]
        assert imps[:5] == ['high'] * 5
        # JSON list 字段反序列化
        assert results[0]['metadata']['entities'] == ['e1']
