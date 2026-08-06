"""P1 压缩单元测试 — 纯函数测试（不依赖 Docker/LangBot SDK）."""
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store.summary_store import SummaryDocument, SummaryStore
from service.context_compressor import (
    split_messages,
    build_compression_prompt,
    parse_summary_response,
    should_compress,
    _item_text,
    _list_to_bullets,
)


class TestSummaryDocument:
    """SummaryDocument 序列化/反序列化."""

    def test_defaults(self):
        doc = SummaryDocument()
        assert doc.topics == ""
        assert doc.facts == ""
        assert doc.covered_until_ts == 0.0
        assert doc.message_count == 0

    def test_from_row_none(self):
        doc = SummaryDocument.from_row(None)
        assert doc.covered_until_ts == 0.0

    def test_from_row_full(self):
        row = ("g1", "t1", "f1", "d1", "r1", 100.5, 10, 200.0, 0.0)
        doc = SummaryDocument.from_row(row)
        assert doc.topics == "t1"
        assert doc.facts == "f1"
        assert doc.covered_until_ts == 100.5
        assert doc.message_count == 10

    def test_from_row_nulls(self):
        row = ("g1", None, None, None, None, None, None, None, None)
        doc = SummaryDocument.from_row(row)
        assert doc.topics == ""
        assert doc.covered_until_ts == 0.0


class TestSummaryStore:
    """SummaryStore SQLite 读写（内存数据库）."""

    def test_load_or_default_new_session(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        # 建表
        import sqlite3
        db = sqlite3.connect(db_path)
        SummaryStore.create_table(db)
        db.commit()
        db.close()

        store = SummaryStore(db_path)
        doc = store.load_or_default("group_123")
        assert doc.covered_until_ts == 0.0
        assert doc.message_count == 0
        # load 不存在 → None
        assert store.load("group_123") is None

    def test_upsert_and_load(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        import sqlite3
        db = sqlite3.connect(db_path)
        SummaryStore.create_table(db)
        db.commit()
        db.close()

        store = SummaryStore(db_path)
        doc = SummaryDocument(
            topics="Python性能",
            facts="DS920+ NAS",
            covered_until_ts=1234567890.0,
            message_count=42,
        )
        store.upsert("group_123", doc)

        loaded = store.load("group_123")
        assert loaded is not None
        assert loaded.topics == "Python性能"
        assert loaded.facts == "DS920+ NAS"
        assert loaded.covered_until_ts == 1234567890.0
        assert loaded.message_count == 42
        assert loaded.updated_at > 0

        # load_or_default 也应返回同一份
        doc2 = store.load_or_default("group_123")
        assert doc2.topics == "Python性能"

    def test_upsert_update_existing(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        import sqlite3
        db = sqlite3.connect(db_path)
        SummaryStore.create_table(db)
        db.commit()
        db.close()

        store = SummaryStore(db_path)
        store.upsert("g1", SummaryDocument(facts="v1"))
        store.upsert("g1", SummaryDocument(facts="v2", topics="new"))

        loaded = store.load("g1")
        assert loaded.facts == "v2"
        assert loaded.topics == "new"


# ── ContextCompressor 纯函数测试 ──────────────────────────────


def _make_item(text: str, ts: float = 1000.0) -> dict:
    return {"metadata": {"text": text, "timestamp_unix": ts}}


class TestItemText:
    def test_metadata_text(self):
        assert _item_text(_make_item("hello")) == "hello"

    def test_document_fallback(self):
        assert _item_text({"document": "doc text", "metadata": {}}) == "doc text"

    def test_content_list(self):
        item = {"content": [{"type": "text", "text": "from content"}], "metadata": {}}
        assert _item_text(item) == "from content"

    def test_empty(self):
        assert _item_text({"metadata": {}}) == ""


class TestSplitMessages:
    def test_normal(self):
        items = [_make_item("a" * 100) for _ in range(30)]  # 30 × 100 = 3000 chars
        to_sum, to_keep = split_messages(items, tail_max_chars=1500)
        # tail 1500 ≈ 15 items, to_sum ≈ 15 items
        assert len(to_keep) == 15
        assert len(to_sum) == 15

    def test_all_short(self):
        """全短消息（10字/条），tail 保留全部."""
        items = [_make_item("0123456789") for _ in range(20)]
        to_sum, to_keep = split_messages(items, tail_max_chars=1500)
        assert len(to_keep) == 20
        assert len(to_sum) == 0

    def test_all_long(self):
        """全长消息（400字/条），to_sum 截断到 6000 字符."""
        items = [_make_item("x" * 400) for _ in range(30)]
        to_sum, to_keep = split_messages(items, tail_max_chars=1500)
        # tail 1500 / 400 ≈ 3-4 items
        assert len(to_keep) <= 4
        # to_sum 截断到 6000 chars, 6000/400=15 items max
        assert len(to_sum) <= 15
        # 验证截断：to_sum 总字符 ≤ 6000 + 单条上限
        total = sum(len(_item_text(i)) for i in to_sum)
        assert total <= 6400  # 6000 + 400 margin

    def test_empty(self):
        to_sum, to_keep = split_messages([], tail_max_chars=1500)
        assert to_sum == []
        assert to_keep == []


class TestParseSummaryResponse:
    def test_valid_json(self):
        doc = parse_summary_response(
            '{"topics": "t1", "facts": "f1", "decisions": "d1", "refs": "r1"}'
        )
        assert doc is not None
        assert doc.topics == "t1"
        assert doc.facts == "f1"

    def test_fenced_json(self):
        raw = '```json\n{"topics": "t", "facts": "f", "decisions": "", "refs": ""}\n```'
        doc = parse_summary_response(raw)
        assert doc is not None
        assert doc.topics == "t"

    def test_trailing_text(self):
        raw = 'Prefix text {"topics": "t", "facts": "f", "decisions": "", "refs": ""} suffix'
        doc = parse_summary_response(raw)
        assert doc is not None
        assert doc.topics == "t"

    def test_malformed_json(self):
        assert parse_summary_response("not json at all") is None

    def test_empty_string(self):
        assert parse_summary_response("") is None

    def test_missing_field(self):
        raw = '{"topics": "t"}'  # 缺 facts/decisions/refs
        doc = parse_summary_response(raw)
        assert doc is not None
        assert doc.topics == "t"
        assert doc.facts == ""

    def test_all_empty_fields(self):
        raw = '{"topics": "", "facts": "", "decisions": "", "refs": ""}'
        doc = parse_summary_response(raw)
        assert doc is None  # 全空不覆盖旧摘要

    def test_dict_input(self):
        doc = parse_summary_response({"topics": "t", "facts": "f"})
        assert doc is not None
        assert doc.topics == "t"

    def test_null_values(self):
        raw = '{"topics": null, "facts": null, "decisions": null, "refs": null}'
        doc = parse_summary_response(raw)
        assert doc is None  # null → 空串 → 全空不覆盖


class TestShouldCompress:
    def test_yes_new_messages(self):
        # 30 条各 100 字符 → tail 1500 chars ≈ 15 items
        items = [_make_item("x" * 100, ts=1000 + i * 10) for i in range(30)]
        # items[0-14] 在 tail 外，ts > 1000 → 应该压缩
        assert should_compress(1000.0, items)

    def test_no_cooldown(self):
        items = [_make_item("x" * 100) for i in range(30)]
        future = time.time() + 3600
        assert not should_compress(0.0, items, cooldown_until=future)

    def test_no_new(self):
        # 5 条全在 tail 内，covered 比所有 ts 都大
        items = [_make_item("x" * 50, ts=1000 + i * 10) for i in range(5)]
        last_ts = items[-1]["metadata"]["timestamp_unix"]
        assert not should_compress(last_ts + 1, items)

    def test_first_compress(self):
        """covered_until_ts=0，tail 外有消息 → 应触发."""
        items = [_make_item("x" * 100, ts=1000 + i * 10) for i in range(30)]
        assert should_compress(0.0, items, cooldown_until=0.0)


class TestBuildCompressionPrompt:
    def test_contains_fields(self):
        doc = SummaryDocument(topics="t", facts="f")
        to_sum = [_make_item("hello world")]
        prompt = build_compression_prompt(doc, to_sum)
        assert "EXISTING SUMMARY" in prompt
        assert "NEW MESSAGES" in prompt
        assert "hello world" in prompt
        assert '"topics": "t"' in prompt


class TestListToBullets:
    def test_list_input(self):
        assert _list_to_bullets(["a", "b"]) == "- a\n- b"

    def test_json_array_string(self):
        assert _list_to_bullets('["a", "b"]') == "- a\n- b"

    def test_python_repr_string(self):
        assert _list_to_bullets("['a', 'b']") == "- a\n- b"

    def test_plain_string(self):
        assert _list_to_bullets("plain text") == "plain text"

    def test_empty_list(self):
        assert _list_to_bullets([]) == ""

    def test_none(self):
        assert _list_to_bullets(None) == ""
