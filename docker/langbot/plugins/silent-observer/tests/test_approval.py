"""Approval 回归测试 — 锁定 gate/inject/KB 行为基线。

步骤 0 录制基线后，每个后续步骤跑此测试验证行为未变。
由于依赖真实 NAS 生产数据，本地跑需要先导出数据到 fixtures/。
"""
import json
import os
from pathlib import Path

import pytest

APPROVAL_DIR = Path(__file__).parent / 'approval'


def read_baseline(name):
    """读取基线文件，跳过注释行"""
    path = APPROVAL_DIR / name
    if not path.exists():
        pytest.skip(f'基线文件不存在: {path}')
    lines = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            lines.append(stripped)
    return '\n'.join(lines)


class TestGateBaseline:
    """验证 gate 决策格式和关键行为"""

    def test_doc_id_format(self):
        """doc_id 必须保持 chat:<sha256_hex_16> 格式"""
        import re
        baseline = read_baseline('gate_baseline.txt')
        doc_ids = re.findall(r'doc_id=chat:([a-f0-9]{16})', baseline)
        assert len(doc_ids) >= 3, f'至少需要3个 doc_id 样例，实际: {len(doc_ids)}'

    def test_event_fields(self):
        """event log 必须包含必要字段"""
        baseline = read_baseline('gate_baseline.txt')
        required = ['trigger=', 'locked=', 'doc_id=']
        hit_lines = [l for l in baseline.splitlines() if ' hit ' in l]
        assert len(hit_lines) >= 3, f'至少需要3条 hit 记录，实际: {len(hit_lines)}'
        for line in hit_lines:
            for field in required:
                assert field in line, f'hit 记录缺少字段 {field}: {line[:80]}'

    def test_miss_format(self):
        """miss 记录格式验证"""
        baseline = read_baseline('gate_baseline.txt')
        miss_lines = [l for l in baseline.splitlines() if ' miss' in l]
        assert len(miss_lines) >= 1, '至少需要1条 miss 记录'
        for line in miss_lines:
            assert 'trigger=' not in line, f'miss 记录不应有 trigger: {line[:80]}'
            assert 'doc_id=' not in line, f'miss 记录不应有 doc_id: {line[:80]}'


class TestInjectBaseline:
    """验证 inject prompt 格式"""

    def test_timezone_format(self):
        """时区注入格式检查"""
        baseline = read_baseline('inject_baseline.txt')
        assert '北京时间' in baseline, '缺少北京时间标记'
        assert 'UTC' in baseline, '缺少 UTC 标记'
        assert '禁止转换为UTC' in baseline, '缺少时区禁止转换指令'

    def test_trigger_modes(self):
        """所有触发模式必须存在"""
        baseline = read_baseline('inject_baseline.txt')
        assert '[@模式]' in baseline, '缺少 @模式标记'
        assert '[空@模式]' in baseline, '缺少 空@模式标记'
        assert '[随机插话]' in baseline, '缺少 随机插话标记'

    def test_face_injection_format(self):
        """表情注入格式检查"""
        baseline = read_baseline('inject_baseline.txt')
        assert '[QQ表情:' in baseline or '[表情]' in baseline, '缺少表情注入格式'

    def test_image_markers(self):
        """图片识别标记完整性"""
        baseline = read_baseline('inject_baseline.txt')
        assert 'AI识图' in baseline, '缺少 AI识图 标记'
        assert 'AI识图中' in baseline, '缺少 AI识图中 标记'
        assert 'AI识图失败' in baseline, '缺少 AI识图失败 标记'


class TestKBMetadataSchema:
    """验证 KB 元数据 schema"""

    def test_required_fields(self):
        """metadata 必须包含所有必要字段"""
        baseline = read_baseline('kb_metadata_schema.txt')
        required_fields = ['text', 'sender_name', 'sender_id', 'timestamp',
                           'timestamp_unix', 'session_id', 'type']
        for field in required_fields:
            assert field in baseline, f'metadata schema 缺少字段: {field}'

    def test_type_is_chat_history(self):
        """type 字段必须固定为 chat_history"""
        baseline = read_baseline('kb_metadata_schema.txt')
        assert '"type": "chat_history"' in baseline or "type': 'chat_history'" in baseline or 'chat_history' in baseline

    def test_doc_id_pattern(self):
        """doc_id 格式验证"""
        baseline = read_baseline('kb_metadata_schema.txt')
        assert 'chat:<sha256_hex_16>' in baseline or 'chat:sha256' in baseline.lower(), 'doc_id 格式描述缺失'

    def test_chat_index_schema(self):
        """chat_index SQLite 表结构验证"""
        baseline = read_baseline('kb_metadata_schema.txt')
        assert 'chat_index' in baseline, '缺少 chat_index 表定义'
        assert 'doc_id TEXT PRIMARY KEY' in baseline, 'doc_id 主键定义缺失'
        assert 'session_id TEXT' in baseline, 'session_id 字段定义缺失'
        assert 'timestamp_unix REAL' in baseline, 'timestamp_unix 字段定义缺失'
        assert 'idx_chat_session_time' in baseline, '缺少复合索引定义'
