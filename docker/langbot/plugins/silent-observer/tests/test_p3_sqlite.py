"""P3: SQLite chat_index 操作测试"""
import sqlite3, os, tempfile
import pytest


@pytest.fixture
def temp_db():
    """创建临时 SQLite 文件路径"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    try: os.unlink(path)
    except: pass


class TestGetDb:
    def test_creates_connection(self, monkeypatch, temp_db):
        from components.event_listener.default import _get_db, _DB_PATH
        monkeypatch.setattr('components.event_listener.default._DB_PATH', temp_db)
        db = _get_db()
        assert isinstance(db, sqlite3.Connection)
        db.close()

    def test_wal_mode(self, monkeypatch, temp_db):
        from components.event_listener.default import _get_db
        monkeypatch.setattr('components.event_listener.default._DB_PATH', temp_db)
        db = _get_db()
        mode = db.execute('PRAGMA journal_mode').fetchone()[0]
        assert mode.lower() == 'wal'
        db.close()


class TestInitChatIndex:
    def test_creates_table(self, listener, monkeypatch, temp_db):
        monkeypatch.setattr('components.event_listener.default._DB_PATH', temp_db)
        listener._init_chat_index()
        db = sqlite3.connect(temp_db)
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")]
        assert 'chat_index' in tables
        db.close()

    def test_idempotent(self, listener, monkeypatch, temp_db):
        monkeypatch.setattr('components.event_listener.default._DB_PATH', temp_db)
        listener._init_chat_index()
        listener._init_chat_index()  # 不抛异常
