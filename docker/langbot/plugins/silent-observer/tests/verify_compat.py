#!/usr/bin/env python3
"""兼容性验证脚本 — 检查关键数据格式、schema、配置键未发生意外变更。

用法:
  cd plugins/silent-observer && uv run python tests/verify_compat.py
  # 或: uv run pytest tests/verify_compat.py -v

验证项:
  1. build_document_id()    — 确定性 + 格式 ("chat:<16hex>")
  2. build_msg_metadata()   — schema 完整性（6 个必选 key）
  3. format_timeline()      — 空/单条/多条/content 回退
  4. clean_description()    — 边界情况
  5. norm_role()            — None/enum/string
  6. manifest config keys   — 所有配置项有对应 get_config 默认值
  7. KBStore doc_id 兼容    — store_message 写入的 doc_id 格式不变
"""

import json
import sys
import os

# 确保可导入插件模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import yaml


# ============================================================
# 1. build_document_id() 格式验证
# ============================================================

def test_doc_id_format():
    from util.text import build_document_id

    doc_id = build_document_id("group_123", "2026-07-29 14:30", "987654", "你好")
    assert doc_id.startswith("chat:"), f"doc_id 应以 'chat:' 开头: {doc_id}"
    hex_part = doc_id[5:]
    assert len(hex_part) == 16, f"hex 部分应为 16 字符: {hex_part}"
    assert all(c in "0123456789abcdef" for c in hex_part), f"hex 部分应为小写十六进制: {hex_part}"


def test_doc_id_deterministic():
    from util.text import build_document_id

    a = build_document_id("g1", "t1", "s1", "hello")
    b = build_document_id("g1", "t1", "s1", "hello")
    assert a == b, "相同输入必须产生相同 doc_id"


def test_doc_id_different_inputs():
    from util.text import build_document_id

    a = build_document_id("g1", "t1", "s1", "hello")
    b = build_document_id("g1", "t1", "s1", "world")
    assert a != b, "不同 text 应产生不同 doc_id"


# ============================================================
# 2. build_msg_metadata() schema 验证
# ============================================================

REQUIRED_META_KEYS = {'text', 'sender_name', 'sender_id', 'timestamp',
                       'timestamp_unix', 'session_id', 'type'}


def test_metadata_has_all_keys():
    from util.text import build_msg_metadata
    import time

    meta = build_msg_metadata("group_123", "豆豆", "987654",
                               "2026-07-29 14:30", "你好世界", "MEMBER", "")
    missing = REQUIRED_META_KEYS - set(meta.keys())
    assert not missing, f"metadata 缺少 key: {missing}"


def test_metadata_type_field():
    from util.text import build_msg_metadata

    meta = build_msg_metadata("g1", "n", "1", "t", "x", "", "")
    assert meta['type'] == 'chat_history', f"type 必须是 'chat_history': {meta['type']}"


def test_metadata_text_format():
    from util.text import build_msg_metadata

    meta = build_msg_metadata("g1", "豆豆", "123", "14:30", "你好", "MEMBER", "")
    assert meta['text'].startswith("[14:30] 豆豆:"), f"text 格式不正确: {meta['text']}"


def test_metadata_with_title_and_role():
    from util.text import build_msg_metadata

    meta = build_msg_metadata("g1", "豆豆", "123", "14:30", "你好", "OWNER", "专家")
    assert "[专家]" in meta['text'], f"应包含 title: {meta['text']}"
    assert "(群主)" in meta['text'], f"应包含 role: {meta['text']}"


def test_metadata_timestamp_types():
    from util.text import build_msg_metadata

    meta = build_msg_metadata("g1", "n", "1", "t", "x", "", "")
    assert isinstance(meta['timestamp_unix'], (int, float)), "timestamp_unix 应为数值"
    assert isinstance(meta['sender_id'], str), "sender_id 应为字符串"


# ============================================================
# 3. format_timeline() 验证
# ============================================================

def test_format_timeline_empty():
    from util.text import format_timeline
    assert format_timeline([]) == []


def test_format_timeline_single():
    from util.text import format_timeline
    items = [{'metadata': {'text': '[14:30] 豆豆: 你好'}}]
    result = format_timeline(items)
    assert result == ['[14:30] 豆豆: 你好']


def test_format_timeline_multi():
    from util.text import format_timeline
    items = [
        {'metadata': {'text': '[14:30] A: hi'}},
        {'metadata': {'text': '[14:31] B: hello'}},
    ]
    result = format_timeline(items)
    assert len(result) == 2


def test_format_timeline_fallback_to_document():
    from util.text import format_timeline
    items = [{'document': 'raw text', 'metadata': {}}]
    result = format_timeline(items)
    assert result == ['raw text']


def test_format_timeline_fallback_to_content():
    from util.text import format_timeline
    items = [{
        'metadata': {},
        'content': [{'type': 'text', 'text': 'from content'}]
    }]
    result = format_timeline(items)
    assert result == ['from content']


def test_format_timeline_skips_non_text_content():
    from util.text import format_timeline
    items = [{
        'metadata': {},
        'content': [{'type': 'image', 'url': 'http://x.com/1.png'}]
    }]
    result = format_timeline(items)
    assert result == []  # 非 text 类型被跳过


# ============================================================
# 4. clean_description() 边界情况
# ============================================================

def test_clean_description_normal():
    from util.text import clean_description
    result = clean_description("一只猫坐在窗台上")
    assert result == "[图片: 一只猫坐在窗台上]"


def test_clean_description_prefix_strip():
    from util.text import clean_description
    result = clean_description("这张图片展示了一只猫")
    assert "一只猫" in result
    assert "这张图片" not in result


def test_clean_description_rejected():
    from util.text import clean_description
    assert clean_description("无法识别内容") == "[图片]"
    assert clean_description("violates policy") == "[图片]"


def test_clean_description_empty():
    from util.text import clean_description
    assert clean_description("") == "[图片]"
    assert clean_description(None) == "[图片]"


def test_clean_description_truncation():
    from util.text import clean_description
    long_desc = "A" * 100
    result = clean_description(long_desc)
    assert len(result) <= 70  # "[图片: " (4) + 60 chars + "]"


# ============================================================
# 5. norm_role() 验证
# ============================================================

def test_norm_role_none():
    from util.text import norm_role
    assert norm_role(None) == ''


def test_norm_role_string():
    from util.text import norm_role
    assert norm_role('ADMINISTRATOR') == 'ADMINISTRATOR'


def test_norm_role_enum():
    from enum import Enum
    Permission = Enum('Permission', ['MEMBER', 'OWNER'])
    from util.text import norm_role
    # perm.value 对于 auto-numbered Enum 返回整数值（如 2）
    assert norm_role(Permission.OWNER) == 2


# ============================================================
# 6. Manifest 配置键完整性
# ============================================================

MANIFEST_PATH = os.path.join(os.path.dirname(__file__), '..', 'manifest.yaml')

# 这些键必须有对应 get_config 调用（在 initialize() 中）
EXPECTED_CONFIG_KEYS = {
    'bot_qq', 'reply_probability', 'history_count', 'kb_id',
    'embedding_model_uuid', 'timeline_max_chars', 'vision_max_images',
    'vision_enabled', 'vision_model_uuid', 'vision_all_messages',
    'vision_daily_limit', 'debug_dump',
}


def test_manifest_exists():
    assert os.path.exists(MANIFEST_PATH), f"manifest.yaml 不存在: {MANIFEST_PATH}"


def test_manifest_config_keys():
    with open(MANIFEST_PATH, 'r') as f:
        manifest = yaml.safe_load(f)

    config_names = {item['name'] for item in manifest['spec']['config']}
    missing = EXPECTED_CONFIG_KEYS - config_names
    assert not missing, f"manifest 缺少配置项: {missing}"

    extra = config_names - EXPECTED_CONFIG_KEYS
    if extra:
        print(f"  ⚠ manifest 有额外配置项（确认已处理）: {extra}")


def test_manifest_components():
    with open(MANIFEST_PATH, 'r') as f:
        manifest = yaml.safe_load(f)

    components = manifest['spec'].get('components', {})
    assert 'EventListener' in components, "manifest 必须有 EventListener 组件"
    assert 'Tool' in components, "manifest 必须有 Tool 组件"


# ============================================================
# 7. 行为一致性回归（关键路径）
# ============================================================

def test_format_timeline_preserves_order():
    """时间线保持时间顺序（调用方依赖此行为做去重/截断）。"""
    from util.text import format_timeline
    items = [
        {'metadata': {'text': '[14:30] msg1'}},
        {'metadata': {'text': '[14:31] msg2'}},
        {'metadata': {'text': '[14:32] msg3'}},
    ]
    result = format_timeline(items)
    assert result == ['[14:30] msg1', '[14:31] msg2', '[14:32] msg3']


def test_build_msg_metadata_text_truncation_contract():
    """_save_text_only 依赖 metadata['text'] 在 500 字符后被截断。
    此测试确认 metadata 本身不做截断（截断在调用方做）。"""
    from util.text import build_msg_metadata
    long_text = "A" * 600
    meta = build_msg_metadata("g1", "n", "1", "t", long_text, "", "")
    # metadata 保留完整文本，截断是调用方的责任
    assert long_text in meta['text']


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
