"""P1 对话成熟度单元测试 — rewrite/scanner/rerank/validate_schema/INJECT 降级矩阵"""
import asyncio
import json
import os
import sys
from types import SimpleNamespace
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


def _recent(n=6):
    return [{'metadata': {'text': f'm{i}'}} for i in range(n)]


# ── P1.1 _rewrite_utterance ────────────────────────────────

@pytest.fixture
def detector():
    plugin = MagicMock()
    plugin.invoke_llm = AsyncMock(return_value='补全句：不对，DS920+才是')
    from service.correction import CorrectionDetector
    return CorrectionDetector(plugin, bot_qq='', llm_model_uuid='uuid')


class TestRewriteUtterance:
    async def test_success(self, detector):
        result = await detector._rewrite_utterance('不对，你搞错了', 'bot回复')
        assert result == '补全句：不对，DS920+才是'
        detector._plugin.invoke_llm.assert_awaited_once()

    async def test_message_object(self, detector):
        detector._plugin.invoke_llm = AsyncMock(return_value=SimpleNamespace(content='补全句：不对，你搞错了，应该是DS920+'))
        assert await detector._rewrite_utterance('不对，你搞错了', 'r') == '补全句：不对，你搞错了，应该是DS920+'

    async def test_shorter_keeps_original(self, detector):
        detector._plugin.invoke_llm = AsyncMock(return_value='不对')
        assert await detector._rewrite_utterance('不对，你搞错了', 'r') == '不对，你搞错了'

    async def test_empty_keeps_original(self, detector):
        detector._plugin.invoke_llm = AsyncMock(return_value='')
        assert await detector._rewrite_utterance('不对，你搞错了', 'r') == '不对，你搞错了'

    async def test_exception_keeps_original(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=RuntimeError('boom'))
        assert await detector._rewrite_utterance('不对，你搞错了', 'r') == '不对，你搞错了'

    async def test_timeout_keeps_original(self, detector, monkeypatch):
        monkeypatch.setattr('service.correction._LLM_CONFIRM_TIMEOUT', 0.01)

        async def _hang(*a, **k):
            await asyncio.sleep(30)
        detector._plugin.invoke_llm = AsyncMock(side_effect=_hang)
        assert await detector._rewrite_utterance('不对，你搞错了', 'r') == '不对，你搞错了'


class TestDetect:
    async def test_stage1_miss_no_llm(self, detector):
        signal = await detector.detect('g', '今天天气不错', 'bot回复', _recent())
        assert signal is None
        detector._plugin.invoke_llm.assert_not_awaited()

    async def test_full_chain_rewritten(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=['补全句：你说错了，应该用DS920+', 'YES'])
        signal = await detector.detect('g', '不对，你搞错了', 'bot回复内容', _recent())
        assert signal is not None
        assert signal.user_text == '补全句：你说错了，应该用DS920+'
        assert signal.raw_user_text == '不对，你搞错了'
        assert signal.confidence == 0.9

    async def test_rewrite_rejected_retry_original(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=['补全句：不对，你搞错了，应该用DS920+', 'NO', 'YES'])
        signal = await detector.detect('g', '不对，你搞错了', 'bot回复内容', _recent())
        assert signal is not None
        assert signal.user_text == '不对，你搞错了'  # 原文重试通过
        assert detector._plugin.invoke_llm.call_count == 3

    async def test_rewrite_no_change_no_retry(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=['不对，你搞错了', 'YES'])
        signal = await detector.detect('g', '不对，你搞错了', 'bot回复内容', _recent())
        assert signal is not None
        assert detector._plugin.invoke_llm.call_count == 2  # 无变化不重试

    async def test_both_rejected(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=['补全句：不对，你搞错了，应该用DS920+', 'NO', 'NO'])
        signal = await detector.detect('g', '不对，你搞错了', 'bot回复内容', _recent())
        assert signal is None
        assert detector._plugin.invoke_llm.call_count == 3

    async def test_rewrite_exception_fallback(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=[RuntimeError('x'), 'YES'])
        signal = await detector.detect('g', '不对，你搞错了', 'bot回复内容', _recent())
        assert signal is not None
        assert signal.user_text == '不对，你搞错了'
        assert signal.raw_user_text == '不对，你搞错了'

    async def test_stage2_exception_high_conf_trust(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=[RuntimeError('x'), RuntimeError('y')])
        signal = await detector.detect('g', '不对，你搞错了', 'bot回复内容', _recent())
        assert signal is not None  # 0.9 直击词，异常降级为信任

    async def test_stage2_exception_low_conf_drop(self, detector):
        detector._plugin.invoke_llm = AsyncMock(side_effect=[RuntimeError('x'), RuntimeError('y')])
        signal = await detector.detect('g', '请纠正一下', 'bot回复内容', _recent())
        assert signal is None  # ACTION 0.7，异常降级为丢弃


# ── P1.2 SelfReflectionScanner ─────────────────────────────

@pytest.fixture
def scanner():
    plugin = MagicMock()
    plugin.invoke_llm = AsyncMock(return_value='NONE')
    from service.reflection import SelfReflectionScanner
    return SelfReflectionScanner(plugin, 'uuid')


class TestSelfReflectionScanner:
    @pytest.mark.parametrize('resp', ['NONE', 'none', 'None', 'NONE。', '```json\nNONE\n```', '', '   '])
    async def test_none_variants(self, scanner, resp):
        scanner._plugin.invoke_llm = AsyncMock(return_value=resp)
        assert await scanner.scan(['m1', 'm2']) is None

    async def test_valid_json(self, scanner):
        scanner._plugin.invoke_llm = AsyncMock(return_value=json.dumps(_valid_reflection(), ensure_ascii=False))
        result = await scanner.scan(['m1'])
        assert result is not None
        assert result['when'] and result['then']
        assert result['confirm_count'] == 1  # _enrich 生效

    async def test_json_in_codeblock(self, scanner):
        raw = f'```json\n{json.dumps(_valid_reflection(), ensure_ascii=False)}\n```'
        scanner._plugin.invoke_llm = AsyncMock(return_value=raw)
        assert await scanner.scan(['m1']) is not None

    async def test_json_with_surrounding_text(self, scanner):
        raw = f'分析如下：\n{json.dumps(_valid_reflection(), ensure_ascii=False)}\n以上。'
        scanner._plugin.invoke_llm = AsyncMock(return_value=raw)
        assert await scanner.scan(['m1']) is not None

    async def test_empty_dict(self, scanner):
        scanner._plugin.invoke_llm = AsyncMock(return_value='{}')
        assert await scanner.scan(['m1']) is None

    async def test_missing_when_tolerated_and_derived(self, scanner):
        bad = _valid_reflection()
        del bad['when']
        del bad['then']
        scanner._plugin.invoke_llm = AsyncMock(return_value=json.dumps(bad, ensure_ascii=False))
        result = await scanner.scan(['m1'])
        assert result is not None  # 缺省容忍
        assert result['when'] == result['scenario']  # _enrich 推导

    async def test_missing_scenario_rejected(self, scanner):
        bad = _valid_reflection()
        del bad['scenario']
        scanner._plugin.invoke_llm = AsyncMock(return_value=json.dumps(bad, ensure_ascii=False))
        assert await scanner.scan(['m1']) is None  # 旧字段仍强制

    async def test_short_correct_approach_rejected(self, scanner):
        scanner._plugin.invoke_llm = AsyncMock(return_value=json.dumps(_valid_reflection(correct_approach='太短')))
        assert await scanner.scan(['m1']) is None

    async def test_non_json(self, scanner):
        scanner._plugin.invoke_llm = AsyncMock(return_value='完全没有JSON内容')
        assert await scanner.scan(['m1']) is None

    async def test_llm_exception(self, scanner):
        scanner._plugin.invoke_llm = AsyncMock(side_effect=RuntimeError('boom'))
        assert await scanner.scan(['m1']) is None

    async def test_timeout(self, scanner, monkeypatch):
        monkeypatch.setattr('service.reflection._LLM_TIMEOUT', 0.01)

        async def _hang(*a, **k):
            await asyncio.sleep(30)
        scanner._plugin.invoke_llm = AsyncMock(side_effect=_hang)
        assert await scanner.scan(['m1']) is None

    async def test_empty_messages_no_llm(self, scanner):
        assert await scanner.scan([]) is None
        scanner._plugin.invoke_llm.assert_not_awaited()


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


# ── P1.4 validate_schema / INJECT / GENERATE_PROMPT ────────

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


class TestGeneratePrompt:
    def test_has_when_then_fields(self):
        from service.reflection import GENERATE_PROMPT
        prompt = GENERATE_PROMPT.format(correction_text='c', bot_reply='b', error_types='事实错误')
        assert '"when"' in prompt and '"then"' in prompt
