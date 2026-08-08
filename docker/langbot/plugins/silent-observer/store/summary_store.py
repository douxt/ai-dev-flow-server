"""SummaryStore — 结构化摘要 SQLite 持久化，一行 UPDATE，inject 只读."""
import sqlite3
import sys
import time
from dataclasses import dataclass, fields


@dataclass
class SummaryDocument:
    """结构化摘要文档，每 session 一行，增量更新."""
    topics: str = ""
    facts: str = ""
    decisions: str = ""
    refs: str = ""
    covered_until_ts: float = 0.0
    message_count: int = 0
    updated_at: float = 0.0
    cooldown_until: float = 0.0

    @classmethod
    def from_row(cls, row: tuple | None) -> "SummaryDocument":
        if row is None:
            return cls()
        # session_name, topics, facts, decisions, refs,
        # covered_until_ts, message_count, updated_at, cooldown_until
        return cls(
            topics=row[1] or "",
            facts=row[2] or "",
            decisions=row[3] or "",
            refs=row[4] or "",
            covered_until_ts=row[5] or 0.0,
            message_count=row[6] or 0,
            updated_at=row[7] or 0.0,
            cooldown_until=row[8] or 0.0,
        )


class SummaryStore:
    """摘要持久化：读（inject）/ 写（压缩 worker），同 chat_index.db."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _get_db(self):
        db = sqlite3.connect(self._db_path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    # ── 建表（在 init_chat_index 中调用）────────────────────────

    @staticmethod
    def create_table(db: sqlite3.Connection):
        db.execute("""CREATE TABLE IF NOT EXISTS summary (
            session_name TEXT PRIMARY KEY,
            topics TEXT DEFAULT '',
            facts TEXT DEFAULT '',
            decisions TEXT DEFAULT '',
            refs TEXT DEFAULT '',
            covered_until_ts REAL DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            updated_at REAL DEFAULT 0,
            cooldown_until REAL DEFAULT 0
        )""")

    # ── inject 只读 ─────────────────────────────────────────────

    def load(self, session_name: str) -> SummaryDocument | None:
        """返回 None 表示该 session 从未有过摘要."""
        try:
            db = self._get_db()
            row = db.execute(
                "SELECT * FROM summary WHERE session_name = ?",
                (session_name,),
            ).fetchone()
            db.close()
            return SummaryDocument.from_row(row) if row else None
        except Exception as e:
            print(f"[summary] load error: {e}", file=sys.stderr, flush=True)
            return None

    def load_or_default(self, session_name: str) -> SummaryDocument:
        """永不为 None——不存在时返回空 doc（covered_until_ts=0）."""
        doc = self.load(session_name)
        return doc if doc is not None else SummaryDocument()

    # ── 压缩 worker 写 ──────────────────────────────────────────

    def upsert(self, session_name: str, doc: SummaryDocument):
        """原子 UPSERT，压缩完成调用."""
        try:
            doc.updated_at = time.time()
            db = self._get_db()
            db.execute(
                """INSERT INTO summary (session_name, topics, facts, decisions, refs,
                   covered_until_ts, message_count, updated_at, cooldown_until)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_name) DO UPDATE SET
                   topics=excluded.topics, facts=excluded.facts,
                   decisions=excluded.decisions, refs=excluded.refs,
                   covered_until_ts=excluded.covered_until_ts,
                   message_count=excluded.message_count,
                   updated_at=excluded.updated_at,
                   cooldown_until=excluded.cooldown_until""",
                (
                    session_name,
                    doc.topics, doc.facts, doc.decisions, doc.refs,
                    doc.covered_until_ts, doc.message_count,
                    doc.updated_at, doc.cooldown_until,
                ),
            )
            db.commit()
            db.close()
        except Exception as e:
            print(f"[summary] upsert error: {e}", file=sys.stderr, flush=True)


class CompressionLogStore:
    """压缩日志持久化，每次压缩写一行，供 query_compression.py 查询."""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _get_db(self):
        db = sqlite3.connect(self._db_path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        return db

    @staticmethod
    def create_table(db: sqlite3.Connection):
        db.execute("""CREATE TABLE IF NOT EXISTS compression_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_name TEXT NOT NULL,
            started_at REAL NOT NULL,
            duration_ms INTEGER,
            input_chars INTEGER,
            output_chars INTEGER,
            msg_count INTEGER,
            summary_chars_before INTEGER,
            summary_chars_after INTEGER,
            covered_until_ts REAL,
            status TEXT NOT NULL,
            error TEXT DEFAULT '',
            model_uuid TEXT DEFAULT ''
        )""")
        db.execute("""CREATE INDEX IF NOT EXISTS idx_comp_log_session
            ON compression_log(session_name, started_at DESC)""")

    def insert(self, session_name: str, started_at: float, duration_ms: int,
               input_chars: int, output_chars: int, msg_count: int,
               summary_chars_before: int, summary_chars_after: int,
               covered_until_ts: float, status: str, error: str = '',
               model_uuid: str = ''):
        try:
            db = self._get_db()
            db.execute(
                """INSERT INTO compression_log
                   (session_name, started_at, duration_ms, input_chars,
                    output_chars, msg_count, summary_chars_before,
                    summary_chars_after, covered_until_ts, status, error,
                    model_uuid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_name, started_at, duration_ms, input_chars,
                 output_chars, msg_count, summary_chars_before,
                 summary_chars_after, covered_until_ts, status, error,
                 model_uuid),
            )
            db.commit()
            db.close()
        except Exception as e:
            print(f"[compression_log] insert error: {e}", file=sys.stderr, flush=True)
