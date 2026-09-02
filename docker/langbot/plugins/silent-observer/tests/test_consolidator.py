"""B 线批量整合层单测：触发数学/裁决解析/水位幂等/候选回投"""
import json
import os
import sys
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service.consolidator import (  # noqa: E402
    BJT, CONSOLIDATE_PROMPT, MAX_LESSONS, ReflectionConsolidator,
)


def _lesson(**overrides):
    d = {
        "when": "用户断言与归档记录冲突时",
        "then": "先核对归档原文并索要可指认证据，无新证据不改既有结论",
        "scenario": "群聊中用户无证据断言领养对象是阿黄",
        "error_type": "事实错误",
        "mistake": "曾把用户口头断言当事实归档",
        "correct_approach": "冲突断言必须先检索既有归档比对，要求给出可指认的原文或出处再更新",
        "how_to_avoid": "区分明示偏好与事实断言两类纠正",
        "verifiable_test": "再次收到无证据冲突断言时不改口",
        "domain": "general",
        "entities": ["阿黄"],
        "trigger_keywords": ["不对"],
    }
    d.update(overrides)
    return d


def _msgs(n, start_ts=1000.0, step=10.0):
    return [{'id': f'd{i}', 'document': f'[t{i}] u{i}: m{i}',
             'metadata': {'text': f'[t{i}] u{i}: m{i}', 'timestamp_unix': start_ts + i * step}}
            for i in range(n)]


@pytest.fixture
def deps(tmp_path, monkeypatch):
    # 日志隔离：safe_log 不得写生产 /tmp/silent_reflection.log（测试污染基线教训）
    import util.logs
    monkeypatch.setattr(util.logs, '_log_dir', str(tmp_path))
    plugin = MagicMock()
    plugin.invoke_llm = AsyncMock(return_value='NONE|无佐证断言')
    plugin.get_plugin_storage = AsyncMock(return_value=None)
    plugin.set_plugin_storage = AsyncMock()
    from service.reflection import ReflectionGenerator
    gen = ReflectionGenerator(plugin, 'ref1')
    rstore = MagicMock()
    rstore.list_all = AsyncMock(return_value=[])
    tstore = MagicMock()
    tstore.get_recent_messages = AsyncMock(return_value=_msgs(8))
    c = ReflectionConsolidator(plugin, 'ref1', gen, rstore, tstore)
    c._llm_timeout = 5
    return c, plugin, tstore


class TestTriggerMath:
    def test_mark_accumulates_and_fires(self, deps):
        c, _, _ = deps
        assert c.mark('g', '不对，是阿黄') is False
        assert c.mark('g', '你说错了') is True  # 50+50 >= 100

    def test_fired_once_then_interval_blocks(self, deps):
        c, _, _ = deps
        c.mark('g', 'a 不对')
        c.mark('g', 'b 错了')  # fired
        c._last_run['g'] = time.time()
        c._scores['g'] = 0
        assert c.mark('g', 'c 又错了') is False  # SCORE 达标但 600s 防抖
        assert c._candidates['g'][-1]['text'] == 'c 又错了'  # 候选不丢

    def test_duplicate_text_not_double_queued(self, deps):
        c, _, _ = deps
        c.mark('g', '不对，是阿黄')
        c.mark('g', '不对，是阿黄')
        assert len(c._candidates['g']) == 1
        assert c._scores['g'] == 2 * 50  # 分照加

    def test_daily_cap(self, deps):
        c, _, _ = deps
        c._day = datetime.now(BJT).strftime('%Y-%m-%d')
        c._day_batches = 10
        assert c.mark_round('g') is False

    def test_mark_round(self, deps):
        c, _, _ = deps
        assert c.mark_round('g') is True


class TestConsolidateFlow:
    async def test_none_advances_watermark(self, deps):
        c, plugin, _ = deps
        c.mark('g', '不对，是阿黄', 'm1')
        c.mark('g', '错了', 'm2')
        out = await c.consolidate('g')
        assert out == []
        plugin.set_plugin_storage.assert_awaited()  # 水位已推进
        assert c._candidates.get('g', []) == []

    async def test_lessons_enriched_with_source_ids(self, deps):
        c, plugin, _ = deps
        plugin.invoke_llm = AsyncMock(return_value=json.dumps([_lesson()], ensure_ascii=False))
        c.mark('g', '不对，是阿黄', 'm1')
        out = await c.consolidate('g')
        assert len(out) == 1
        r = out[0]
        assert r['confirm_count'] == 1 and r['archived'] is False
        assert r['source_msg_ids'] == ['m1']
        assert r['when'] and r['then']

    async def test_more_than_two_truncated(self, deps):
        c, plugin, _ = deps
        c._last_run.pop('g', None)
        plugin.invoke_llm = AsyncMock(return_value=json.dumps([_lesson(), _lesson(scenario='s2'), _lesson(scenario='s3')], ensure_ascii=False))
        out = await c.consolidate('g')
        assert len(out) == MAX_LESSONS

    async def test_schema_invalid_items_filtered(self, deps):
        c, plugin, _ = deps
        c._last_run.pop('g', None)
        plugin.invoke_llm = AsyncMock(return_value=json.dumps([_lesson(correct_approach='太短')], ensure_ascii=False))
        out = await c.consolidate('g')
        assert out == []
        # 批次本身成功（裁决给了但不合格）→ 水位仍推进
        plugin.set_plugin_storage.assert_awaited()

    async def test_parse_failure_holds_watermark_and_requeues(self, deps):
        c, plugin, _ = deps
        plugin.invoke_llm = AsyncMock(return_value='说了很多但没有任何 JSON')
        c.mark('g', '不对，是阿黄', 'm1')
        out = await c.consolidate('g')
        assert out == []
        plugin.set_plugin_storage.assert_not_awaited()  # 水位不推进
        assert c._candidates['g'][0]['text'] == '不对，是阿黄'  # 候选回投

    async def test_llm_exception_holds_watermark(self, deps):
        c, plugin, _ = deps
        plugin.invoke_llm = AsyncMock(side_effect=RuntimeError('boom'))
        c.mark('g', '不对', 'm1')
        out = await c.consolidate('g')
        assert out == []
        plugin.set_plugin_storage.assert_not_awaited()
        assert c._candidates['g']

    async def test_no_increment_skips_llm(self, deps):
        c, plugin, tstore = deps
        c._state.load = AsyncMock(return_value={'g': 9999.0})
        tstore.get_recent_messages = AsyncMock(return_value=_msgs(3))
        out = await c.consolidate('g')
        assert out == []
        plugin.invoke_llm.assert_not_awaited()

    async def test_prompt_contains_event_arc_inputs(self, deps):
        c, plugin, _ = deps
        c.mark('g', '不对，是阿黄')
        await c.consolidate('g')
        prompt = plugin.invoke_llm.await_args.kwargs['messages'][0].content
        assert '不对，是阿黄' in prompt          # 候选句
        assert '[t0] u0: m0' in prompt          # 对话增量
        assert '宁缺勿伪' in prompt and 'NONE|' in prompt  # 裁决锚


class TestWatermarkSemantics:
    async def test_same_watermark_rerun_idempotent(self, deps):
        c, plugin, _ = deps
        c._last_run.pop('g', None)
        plugin.invoke_llm = AsyncMock(return_value=json.dumps([_lesson()], ensure_ascii=False))
        out1 = await c.consolidate('g')
        assert len(out1) == 1
        wm_ts = json.loads(plugin.set_plugin_storage.await_args.args[1].decode())['g']
        c._state.load = AsyncMock(return_value={'g': wm_ts})
        plugin.invoke_llm.reset_mock()
        out2 = await c.consolidate('g')
        assert out2 == []                        # V6 幂等：同水位重跑零产出
        plugin.invoke_llm.assert_not_awaited()

    async def test_window_keeps_overlap(self, deps):
        c, _, _ = deps
        msgs = _msgs(30)
        w = c._window_after(msgs, msgs[20]['metadata']['timestamp_unix'])
        # 水位后 9 条 + 重叠 10 条
        assert len(w) == 9 + min(10, 20)
        assert w[-1] is msgs[-1]


class TestParseLessons:
    @pytest.mark.parametrize('raw', [
        json.dumps([_lesson()], ensure_ascii=False),
        f'```json\n{json.dumps([_lesson()], ensure_ascii=False)}\n```',
        f'结论如下：\n{json.dumps([_lesson()], ensure_ascii=False)}\n完毕',
        json.dumps(_lesson(), ensure_ascii=False),  # 单对象兜底
    ])
    def test_variants(self, raw):
        got = ReflectionConsolidator._parse_lessons(raw)
        assert got and got[0]['scenario']

    def test_garbage_none(self):
        assert ReflectionConsolidator._parse_lessons('纯文本没有大括号') is None

    def test_empty_array(self):
        assert ReflectionConsolidator._parse_lessons('[]') == []


class TestPromptDiscipline:
    def test_four_anchors_absent(self):
        # 教训 #23：新 prompt 文本禁含测试断言锚
        for a in ('触发条件：', '先前经验', '仅供你内部理解', '旁白口吻'):
            assert a not in CONSOLIDATE_PROMPT, a

    def test_verdict_rules_present(self):
        for anchor in ('可学', '不学', '独立证据', '宁缺勿伪', '不构成证据'):
            assert anchor in CONSOLIDATE_PROMPT
