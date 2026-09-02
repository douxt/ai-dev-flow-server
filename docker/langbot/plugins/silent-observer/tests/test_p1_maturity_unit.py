"""P1 对话成熟度单元测试 — precheck/rerank/validate_schema/INJECT 降级矩阵"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

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


# ── B 线：实时层 precheck（零 LLM 标记器）─────────────────

@pytest.fixture
def detector():
    from service.correction import CorrectionDetector
    return CorrectionDetector(None, bot_qq='', llm_model_uuid='')


class TestPrecheck:
    @pytest.mark.parametrize('text', ['不对，你搞错了', '你说错了', '错了吧这', '请纠正一下',
                                      '这个不准确', '没有的事，其实是X', '你再想想'])
    def test_hit(self, detector, text):
        matched, conf = detector.precheck(text)
        assert matched and conf > 0

    @pytest.mark.parametrize('text', ['今天天气不错', '乌龙茶记一下', '', '我7月20号领养的是什么？'])
    def test_miss(self, detector, text):
        matched, _ = detector.precheck(text)
        assert not matched

    def test_no_llm_surface_left(self, detector):
        # 标记器不得残留 LLM 能力面
        assert not any(hasattr(detector, m) for m in
                       ('_rewrite_utterance', '_stage2_confirm', 'detect', '_dynamic_window'))


# ── P1.3 rerank ────────────────────────────────────────────

def _cands(n, doc_len=40):
    return [{'id': f'i{i}', 'document': f'doc{i} ' + 'x' * doc_len,
             'metadata': {'scenario': f's{i}', 'confirm_count': 5}} for i in range(n)]


class TestParseRerank:
    @pytest.mark.parametrize('resp,expected', [
        ('3,1,5', [2, 0, 4]),
        (' 3 1 5 ', [2, 0, 4]),
        ('3，1，5', [2, 0, 4]),
        ('3,1,1,5', [2, 0, 4]),
        ('3,99,5', [2, 4]),
        ('1,2,3,4,5,6,7', [0, 1, 2, 3, 4]),
        ('3,1', [2, 0]),
        ('```text\n3,1,5\n```', [2, 0, 4]),
    ])
    def test_parse(self, resp, expected):
        from service.reflection import ReflectionGenerator
        cands = _cands(8)
        got = ReflectionGenerator._parse_rerank(resp, cands)
        assert [cands.index(c) for c in got] == expected

    @pytest.mark.parametrize('resp', ['NONE', 'none', '', '不知道', 'ab cd ef'])
    def test_parse_empty(self, resp):
        from service.reflection import ReflectionGenerator
        assert ReflectionGenerator._parse_rerank(resp, _cands(8)) == []


class TestRerank:
    @pytest.fixture
    def generator(self):
        plugin = MagicMock()
        plugin.invoke_llm = AsyncMock(return_value='3,1,5')
        from service.reflection import ReflectionGenerator
        return ReflectionGenerator(plugin, 'uuid'), plugin

    async def test_normal(self, generator):
        gen, plugin = generator
        cands = _cands(8)
        got = await gen.rerank('电气问题', cands)
        assert [cands.index(c) for c in got] == [2, 0, 4]
        prompt = plugin.invoke_llm.await_args.kwargs['messages'][0].content
        assert '1. ' in prompt and '8. ' in prompt

    async def test_candidate_truncation(self, generator):
        gen, plugin = generator
        cands = [{'id': f'i{i}', 'document': 'y' * 500,
                  'metadata': {'scenario': f's{i}', 'confirm_count': 5}} for i in range(6)]
        await gen.rerank('问题', cands)
        prompt = plugin.invoke_llm.await_args.kwargs['messages'][0].content
        assert 'y' * 301 not in prompt  # 截断到 300

    async def test_timeout_degrades_to_first5(self, generator):
        gen, plugin = generator

        async def _raise(*a, **k):
            raise asyncio.TimeoutError()
        plugin.invoke_llm = AsyncMock(side_effect=_raise)
        got = await gen.rerank('问题', _cands(8))
        assert len(got) == 5

    async def test_exception_degrades_to_first5(self, generator):
        gen, plugin = generator
        plugin.invoke_llm = AsyncMock(side_effect=RuntimeError('boom'))
        got = await gen.rerank('问题', _cands(8))
        assert len(got) == 5

    async def test_empty_candidates(self, generator):
        gen, _ = generator
        assert await gen.rerank('问题', []) == []


# ── P1.4 validate_schema / INJECT / CONSOLIDATE_PROMPT ────

class TestValidateSchema:
    @pytest.fixture
    def generator(self):
        plugin = MagicMock()
        from service.reflection import ReflectionGenerator
        return ReflectionGenerator(plugin, 'uuid')

    def test_with_when_then(self, generator):
        assert generator.validate_schema(_valid_reflection())

    def test_without_when_then_tolerated(self, generator):
        d = _valid_reflection()
        del d['when']
        del d['then']
        assert generator.validate_schema(d)

    def test_missing_scenario_rejected(self, generator):
        d = _valid_reflection()
        del d['scenario']
        assert not generator.validate_schema(d)

    def test_short_correct_approach_rejected(self, generator):
        assert not generator.validate_schema(_valid_reflection(correct_approach='太短'))

    def test_bad_error_type_rejected(self, generator):
        assert not generator.validate_schema(_valid_reflection(error_type='随便'))

    def test_missing_verifiable_test_rejected(self, generator):
        d = _valid_reflection()
        del d['verifiable_test']
        assert not generator.validate_schema(d)


class TestInjectTemplate:
    def _prompt(self, meta):
        from service.reflection import ReflectionInjector
        return ReflectionInjector.build_reflection_prompt([{'metadata': meta}])

    def test_full_when_then(self):
        prompt = self._prompt({'when': 'W', 'then': 'T', 'confirm_count': 5})
        assert '触发条件：W' in prompt and '应对方式：T' in prompt
        assert '尚未充分确认' not in prompt

    def test_when_fallback_scenario(self):
        prompt = self._prompt({'scenario': 'S', 'then': 'T', 'confirm_count': 5})
        assert '触发条件：S' in prompt and '应对方式：T' in prompt

    def test_then_fallback_correct_approach(self):
        prompt = self._prompt({'when': 'W', 'correct_approach': 'CA', 'confirm_count': 5})
        assert '触发条件：W' in prompt and '应对方式：CA' in prompt

    def test_both_missing(self):
        prompt = self._prompt({'confirm_count': 5})
        assert '触发条件：未知场景' in prompt

    def test_confidence_note_low_confirm(self):
        prompt = self._prompt({'when': 'W', 'then': 'T', 'confirm_count': 1})
        assert '(此经验尚未充分确认，仅供参考)' in prompt

    def test_empty(self):
        from service.reflection import ReflectionInjector
        assert ReflectionInjector.build_reflection_prompt([]) is None

    def test_evidence_check_tail_line(self):
        # Q1 反谄媚：链尾证据校验行在位（recency 对 recency），首行锚不破
        for cc in (1, 5):
            prompt = self._prompt({'when': 'W', 'then': 'T', 'confirm_count': cc})
            assert prompt.startswith('[先前经验')
            assert '证据校验：本条与当前检索/记忆证据冲突时，以当前证据为准' in prompt
            lines = prompt.splitlines()
            assert lines[-1].startswith('证据校验：')


class TestConsolidatePrompt:
    def test_has_when_then_fields(self):
        from service.consolidator import CONSOLIDATE_PROMPT
        prompt = CONSOLIDATE_PROMPT.format(candidates='c', conversation='b',
                                           active='a', error_types='事实错误')
        assert '"when"' in prompt and '"then"' in prompt
