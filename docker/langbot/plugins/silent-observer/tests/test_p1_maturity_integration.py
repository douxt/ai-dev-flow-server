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
    return [{'metadata': {'text': f'[2026-08-21 10:{i:02d}] 用户{i}: 你好', 'timestamp_unix': float(i)}} for i in range(10)]


def _gen_prompt(listener, call_idx):
    """取第 call_idx 次 invoke_llm 的 prompt 文本"""
    return listener.plugin.invoke_llm.call_args_list[call_idx].kwargs['messages'][0].content


class TestConsolidateChain:
    """场景 1-4：批量整合链（mark→触发→consolidate→persist）"""

    def _event(self):
        return SimpleNamespace(message_chain=None, message_event=None, sender_id='u1')

    def _feed(self, listener):
        listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())

    async def test_two_marks_trigger_single_llm(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, [VALID_JSON])
        self._feed(reflection_listener)
        ev = self._event()
        await reflection_listener._mark_correction(ev, 'group_t', user_text='不对，是阿黄。')
        assert reflection_listener.plugin.invoke_llm.call_count == 0  # 第一次标记：零 LLM
        await reflection_listener._mark_correction(ev, 'group_t', user_text='你说错了')
        assert reflection_listener.plugin.invoke_llm.call_count == 1  # 分满触发，恰好一批
        reflection_listener.plugin.vector_upsert.assert_awaited()
        prompt = _gen_prompt(reflection_listener, 0)
        assert '不对，是阿黄。' in prompt and '你说错了' in prompt  # 事件弧输入

    async def test_c_class_none_no_store(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, ['NONE|断言无佐证，后续无人跟进'])
        self._feed(reflection_listener)
        ev = self._event()
        await reflection_listener._mark_correction(ev, 'group_t', user_text='不对，是阿黄。')
        await reflection_listener._mark_correction(ev, 'group_t', user_text='其实是阿黄')
        reflection_listener.plugin.vector_upsert.assert_not_awaited()
        reflection_listener.plugin.set_plugin_storage.assert_awaited()  # 裁决过→水位推进

    async def test_non_correction_no_action(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, [VALID_JSON])
        self._feed(reflection_listener)
        await reflection_listener._mark_correction(self._event(), 'group_t', user_text='乌龙茶记一下')
        reflection_listener.plugin.invoke_llm.assert_not_awaited()
        assert reflection_listener.consolidator._scores.get('group_t', 0) == 0

    async def test_parse_garbage_holds_watermark_keeps_candidates(self, reflection_listener, scripted_llm):
        scripted_llm(reflection_listener, ['絮絮叨叨但没有 JSON'])
        self._feed(reflection_listener)
        ev = self._event()
        await reflection_listener._mark_correction(ev, 'group_t', user_text='不对，是阿黄。')
        await reflection_listener._mark_correction(ev, 'group_t', user_text='你说错了')
        reflection_listener.plugin.vector_upsert.assert_not_awaited()
        reflection_listener.plugin.set_plugin_storage.assert_not_awaited()  # 水位保持
        assert '不对，是阿黄。' in [c['text'] for c in reflection_listener.consolidator._candidates['group_t']]


class TestRoundTick:
    """场景 5-9：每 10 轮周期批（原 self-reflect 入口并入整合层）"""

    def _trigger(self, listener):
        listener._reflection_round_count = 9
        listener._bump_reflection_counter('group_t')
        if listener._bg_queue.empty():
            return None
        return listener._bg_queue.get_nowait()

    async def test_trigger_at_10th_round(self, reflection_listener, scripted_llm):
        reflection_listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())
        scripted_llm(reflection_listener, [VALID_JSON])
        await self._trigger(reflection_listener)
        assert reflection_listener.plugin.invoke_llm.call_count == 1  # 仅批量一次
        reflection_listener.plugin.vector_upsert.assert_awaited()

    async def test_consolidate_none_no_store(self, reflection_listener, scripted_llm):
        reflection_listener.store.get_recent_messages = AsyncMock(return_value=_ten_msgs())
        scripted_llm(reflection_listener, ['NONE|例行回顾无值得固化内容'])
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

    async def test_min_interval_skips_tick(self, reflection_listener):
        import time as _t
        reflection_listener.consolidator._last_run['group_t'] = _t.time()
        assert self._trigger(reflection_listener) is None  # 防抖内不调度
        reflection_listener.plugin.invoke_llm.assert_not_awaited()

    def test_not_yet_triggered(self, reflection_listener):
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
