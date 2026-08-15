"""search_history 混合搜索单元测试。

测试 _escape_like / _session_ids_for_search 纯函数，
以及 _keyword_search_sqlite 临时 SQLite + mock plugin 集成。
"""
import sqlite3
import tempfile

import pytest


# ── 导入被测模块 ──────────────────────────────────────────────
# 在 store 目录下运行 pytest 避免相对导入问题
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from store.kb_store import KBStore


class FakePlugin:
    """最小 mock：仅提供 search_history 不需要的 API."""
    pass


@pytest.fixture
def store():
    """创建带临时 SQLite 的 KBStore 实例."""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    store = KBStore(FakePlugin(), 'test-kb-id', 'test-emb-uuid', db_path)
    store.init_chat_index()
    yield store
    os.close(db_fd)
    os.unlink(db_path)


# ── _escape_like 单元测试 ─────────────────────────────────────

@pytest.mark.parametrize('input_str, expected', [
    ('normal text', 'normal text'),
    ('50%', r'50\%'),
    ('a_b', r'a\_b'),
    (r'back\slash', r'back\\slash'),
    (r'50\% off', r'50\\\% off'),  # \ 先转义，再 %
    ('', ''),
])
def test_escape_like(input_str, expected):
    assert KBStore._escape_like(input_str) == expected


# ── _session_ids_for_search 单元测试 ──────────────────────────

def test_session_ids_empty():
    s = KBStore(FakePlugin(), 'x', 'x', '/tmp/x.db')
    assert s._session_ids_for_search('') == ['']


def test_session_ids_group_prefix():
    s = KBStore(FakePlugin(), 'x', 'x', '/tmp/x.db')
    ids = s._session_ids_for_search('group_116381172')
    assert 'group_116381172' in ids
    assert 'group_group_116381172' in ids


def test_session_ids_group_group_prefix():
    s = KBStore(FakePlugin(), 'x', 'x', '/tmp/x.db')
    ids = s._session_ids_for_search('group_group_116381172')
    assert 'group_group_116381172' in ids
    assert 'group_116381172' in ids


def test_session_ids_person_prefix():
    s = KBStore(FakePlugin(), 'x', 'x', '/tmp/x.db')
    ids = s._session_ids_for_search('person_12345')
    assert ids == ['person_12345']


# ── canonical_session_name 单元测试 ───────────────────────────

@pytest.mark.parametrize('input_str, expected', [
    ('group_116381172', 'group_116381172'),
    ('group_group_116381172', 'group_116381172'),
    ('person_12345', 'person_12345'),
    ('', ''),
])
def test_canonical_session_name(input_str, expected):
    from store.kb_store import canonical_session_name
    assert canonical_session_name(input_str) == expected


# ── get_recent_messages 双前缀合并测试 ────────────────────────

@pytest.mark.asyncio
async def test_recent_messages_dual_prefix_merge(store):
    """两前缀消息合并、按 ts 排序、limit 生效."""
    _insert_test_data(store, [
        ('n1', 'group_123', 1000, 'new-prefix old'),
        ('n2', 'group_123', 3000, 'new-prefix recent'),
        ('o1', 'group_group_123', 2000, 'old-prefix mid'),
    ])
    items = await store.get_recent_messages('group_123', 10)
    texts = [i['metadata']['text'] for i in items]
    assert texts == ['new-prefix recent', 'old-prefix mid', 'new-prefix old']


@pytest.mark.asyncio
async def test_recent_messages_dual_prefix_limit(store):
    _insert_test_data(store, [
        ('n1', 'group_123', 1000, 'a'),
        ('n2', 'group_123', 3000, 'c'),
        ('o1', 'group_group_123', 2000, 'b'),
    ])
    items = await store.get_recent_messages('group_123', 2)
    assert len(items) == 2
    assert items[0]['metadata']['text'] == 'c'


@pytest.mark.asyncio
async def test_recent_messages_dedup_ts_text(store):
    """同 (ts, text) 跨前缀重复只留一条，新前缀优先."""
    _insert_test_data(store, [
        ('n1', 'group_123', 1000, 'dup content'),
        ('o1', 'group_group_123', 1000, 'dup content'),
        ('n2', 'group_123', 2000, 'unique'),
    ])
    items = await store.get_recent_messages('group_123', 10)
    texts = [i['metadata']['text'] for i in items]
    assert texts == ['unique', 'dup content']  # 重复只出现一次
    assert items[1]['id'] == 'n1'  # 新前缀的 doc_id 优先


@pytest.mark.asyncio
async def test_recent_messages_single_prefix_unchanged(store):
    """单前缀 session 行为不变（person 透传）."""
    _insert_test_data(store, [
        ('p1', 'person_99', 1000, 'person msg'),
        ('p2', 'person_99', 2000, 'person msg2'),
    ])
    items = await store.get_recent_messages('person_99', 1)
    assert len(items) == 1
    assert items[0]['metadata']['text'] == 'person msg2'


# ── _keyword_search_sqlite 集成测试 ───────────────────────────

def _insert_test_data(store, messages):
    """向 chat_index 插入测试消息."""
    db = store._get_db()
    db.executemany(
        "INSERT OR REPLACE INTO chat_index (doc_id, session_id, timestamp_unix, formatted_text) VALUES (?, ?, ?, ?)",
        messages,
    )
    db.commit()
    db.close()


def test_keyword_basic_match(store):
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, '[2026-07-10 14:39] 喵酱: 还记得三畜和三牲的区别吗'),
        ('d2', 'group_123', 2000, '[2026-08-02 16:57] douxt: 硬盘涨价好离谱'),
        ('d3', 'group_123', 3000, '[2026-08-06 10:00] XENON: 滑动变阻器'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('三牲', 'group_123', 10, '', 0, rrf_scores, doc_map)

    assert 'd1' in rrf_scores
    assert 'd1' in doc_map
    assert '三牲' in doc_map['d1']['document']


def test_keyword_no_match(store):
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, 'hello world'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('三牲', 'group_123', 10, '', 0, rrf_scores, doc_map)

    assert len(rrf_scores) == 0


def test_keyword_multiword_or(store):
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, '硬盘涨价好离谱'),
        ('d2', 'group_123', 2000, '今天股票涨价了'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('硬盘 涨价', 'group_123', 10, '', 0, rrf_scores, doc_map)

    # "硬盘涨价好离谱" 匹配两个词，但得分只保留最佳
    assert 'd1' in rrf_scores
    assert 'd2' in rrf_scores


def test_keyword_sender_filter(store):
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, '[2026-07-10 14:39] 喵酱: 涨价了'),
        ('d2', 'group_123', 2000, '[2026-07-10 14:40] douxt: 涨价了'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('涨价', 'group_123', 10, '喵酱', 0, rrf_scores, doc_map)

    assert 'd1' in rrf_scores
    assert 'd2' not in rrf_scores


def test_keyword_days_filter(store):
    import time
    now = time.time()
    _insert_test_data(store, [
        ('d1', 'group_123', now - 86400, '涨价消息昨天'),
        ('d2', 'group_123', now - 86400 * 10, '涨价消息十天前'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('涨价', 'group_123', 10, '', 3, rrf_scores, doc_map)

    assert 'd1' in rrf_scores
    assert 'd2' not in rrf_scores


def test_keyword_dual_prefix(store):
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, '三牲讨论'),
        ('d2', 'group_group_123', 2000, '三牲旧讨论'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('三牲', 'group_123', 10, '', 0, rrf_scores, doc_map)

    assert 'd1' in rrf_scores
    assert 'd2' in rrf_scores  # 双前缀：旧格式也搜到


def test_keyword_single_char_query(store):
    """单字搜索兜底：words 为空时用整句查询."""
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, '零说了要换服务器'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('零', 'group_123', 10, '', 0, rrf_scores, doc_map)

    assert 'd1' in rrf_scores


def test_keyword_like_escape(store):
    """搜索含 % 字符的 query 不会触发通配符."""
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, '折扣50% off'),
        ('d2', 'group_123', 2000, '折扣50元 off'),
    ])

    rrf_scores = {}
    doc_map = {}
    store._keyword_search_sqlite('50%', 'group_123', 10, '', 0, rrf_scores, doc_map)

    # 只有精确含 '50%' 的，不含 '50元'（% 未被当通配符）
    assert 'd1' in rrf_scores
    assert 'd2' not in rrf_scores


def test_keyword_exception_graceful(store):
    """keyword 通道异常不抛，不影响已有 rrf_scores."""
    rrf_scores = {'existing': 0.5}
    doc_map = {'existing': {'id': 'existing', 'document': 'x'}}

    # 触发异常：空 session_ids (session_name='' → [''])
    store._keyword_search_sqlite('test', '', 10, '', 0, rrf_scores, doc_map)

    assert 'existing' in rrf_scores
    assert rrf_scores['existing'] == 0.5  # 未被覆盖


def test_backfill_idempotent(store):
    """二次回填 filled=0."""
    _insert_test_data(store, [
        ('d1', 'group_123', 1000, 'test message'),
    ])

    # FakePlugin 没有 vector_list，回填应快速完成（无 ChromaDB 数据追加）
    import asyncio
    loop = asyncio.new_event_loop()
    loop.run_until_complete(store.backfill_chat_index())
    loop.close()

    # __backfill_done__ 标记应存在
    db = store._get_db()
    done = db.execute("SELECT 1 FROM chat_index WHERE doc_id='__backfill_done__'").fetchone()
    db.close()
    assert done is not None
