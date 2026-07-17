"""P0: 纯函数测试 — module-level 函数直接导入"""
import pytest
from datetime import timedelta


@pytest.fixture
def mod():
    """导入被测试模块，返回 module + listener"""
    from components.event_listener import default as mod
    return mod


class TestIsFaceComponent:
    def test_face_type_returns_true(self, listener):
        c = type('F', (), {'type': 'Face', 'face_id': 14})()
        assert listener._is_face_component(c) is True

    def test_unknown_with_face_id_returns_true(self, listener):
        c = type('F', (), {'type': 'Unknown', 'face_id': 178})()
        assert listener._is_face_component(c) is True

    def test_plain_returns_false(self, listener):
        c = type('F', (), {'type': 'Plain', 'text': 'hello'})()
        assert listener._is_face_component(c) is False

    def test_other_type_returns_false(self, listener):
        c = type('F', (), {'type': 'Other'})()
        assert listener._is_face_component(c) is False


class TestFaceToText:
    def test_known_face_id(self, listener):
        c = type('F', (), {'face_id': 14, 'face_name': ''})()
        assert listener._face_to_text(c) == '[QQ表情:惊讶]'

    def test_face_name_priority(self, listener):
        c = type('F', (), {'face_id': 14, 'face_name': '白眼'})()
        assert listener._face_to_text(c) == '[QQ表情:白眼]'

    def test_unknown_face_id(self, listener):
        c = type('F', (), {'face_id': 99999, 'face_name': ''})()
        assert 'QQ表情:99999' in listener._face_to_text(c)


class TestBuildDocumentId:
    def test_deterministic(self, mod):
        a = mod._build_document_id('g1', '2024-01-01', 'u1', 'hello')
        b = mod._build_document_id('g1', '2024-01-01', 'u1', 'hello')
        assert a == b

    def test_different_inputs(self, mod):
        a = mod._build_document_id('g1', '2024-01-01', 'u1', 'hello')
        b = mod._build_document_id('g2', '2024-01-01', 'u1', 'hello')
        assert a != b

    def test_prefix_format(self, mod):
        doc_id = mod._build_document_id('s', 't', 'u', 'txt')
        assert doc_id.startswith('chat:')


class TestCleanDescription:
    def test_strip_chinese_prefix(self, mod):
        result = mod._clean_description('这张图片展示了一只猫')
        assert '猫' in result
        assert result.startswith('[图片:')

    def test_reject_pattern(self, mod):
        assert mod._clean_description('cannot describe this') == '[图片]'
        assert mod._clean_description('无法识别') == '[图片]'

    def test_truncate_60_chars(self, mod):
        long_text = 'x' * 200
        result = mod._clean_description(long_text)
        inner = result.replace('[图片: ', '').rstrip(']')
        assert len(inner) <= 60

    def test_empty_returns_placeholder(self, mod):
        assert mod._clean_description('') == '[图片]'


class TestNormRole:
    def test_none_returns_empty(self, mod):
        assert mod._norm_role(None) == ''

    def test_plain_string(self, mod):
        assert mod._norm_role('ADMINISTRATOR') == 'ADMINISTRATOR'

    def test_object_with_value_attr(self, mod):
        obj = type('R', (), {'value': 'OWNER'})()
        assert mod._norm_role(obj) == 'OWNER'


class TestNow:
    def test_timezone_aware(self, mod):
        t = mod._now()
        assert t.tzinfo is not None
        assert t.utcoffset() == timedelta(hours=8)

    def test_is_beijing_time(self, mod):
        from datetime import datetime
        t = mod._now()
        assert 8 <= t.hour <= 23 or 0 <= t.hour <= 3  # rough BJT check


class TestFormatTimeline:
    def test_empty(self, mod):
        assert mod._format_timeline([]) == []

    def test_single_item(self, mod):
        items = [{'metadata': {'sender_name': '张三', 'timestamp_unix': 1000000,
                               'text': '你好', 'sender_role': '', 'sender_title': ''}}]
        result = mod._format_timeline(items)
        assert '你好' in result[0]

    def test_missing_metadata_skipped(self, mod):
        items = [{'no_metadata': True}]
        assert mod._format_timeline(items) == []

    def test_document_fallback(self, mod):
        items = [{'metadata': {}, 'document': 'fallback text'}]
        result = mod._format_timeline(items)
        assert 'fallback text' in result[0]


class TestExtractLlmText:
    def test_none(self, listener):
        assert listener._extract_llm_text(None) == ''

    def test_plain_string(self, listener):
        assert listener._extract_llm_text('hello world') == 'hello world'

    def test_object_with_content_str(self, listener):
        obj = type('R', (), {'content': 'response text'})()
        assert listener._extract_llm_text(obj) == 'response text'

    def test_content_list_with_text_attrs(self, listener):
        items = [type('C', (), {'text': 'hello'})(),
                 type('C', (), {'text': 'world'})()]
        result = listener._extract_llm_text(type('R', (), {'content': items})())
        assert 'hello' in result
        assert 'world' in result
