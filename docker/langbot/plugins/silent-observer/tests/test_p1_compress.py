"""P1 压缩单元测试 — 纯函数测试（不依赖 Docker/LangBot SDK）."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store.summary_store import SummaryDocument, SummaryStore


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
