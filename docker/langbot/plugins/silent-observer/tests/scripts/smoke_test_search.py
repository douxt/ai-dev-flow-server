#!/usr/bin/env python3
"""烟雾测试：直接查生产 chat_index 验证混合搜索。

用法：ssh root@nas python3 < smoke_test_search.py
    或 scp 到 NAS: python3 /tmp/smoke_test_search.py

不需要 pytest、不需要 mock、直连真实 SQLite。
"""
import sqlite3
import sys

DB_PATH = '/volume1/docker/langbot/data/plugins/dou__langbot-silent-observer/chat_index.db'

TESTS = [
    # (query, session_id, min_expected)
    ('三牲', 'group_116381172', 1),
    ('硬盘涨价', 'group_116381172', 1),
    ('SE2', 'group_116381172', 0),       # 可能存在
    ('滑动变阻器', 'group_116381172', 1),
]

def run():
    db = sqlite3.connect(DB_PATH)
    passed = 0
    failed = 0

    for query, session, min_expected in TESTS:
        rows = db.execute(
            "SELECT COUNT(*) FROM chat_index WHERE session_id = ? AND formatted_text LIKE ?",
            (session, f'%{query}%')
        ).fetchone()[0]
        ok = rows >= min_expected
        status = '✅' if ok else '❌'
        print(f'{status} LIKE "%{query}%" in {session}: {rows} rows (need ≥{min_expected})')
        if ok:
            passed += 1
        else:
            failed += 1

    # 验证双前缀：两种格式的数据都存在
    g = db.execute(
        "SELECT COUNT(*) FROM chat_index WHERE session_id = 'group_116381172'"
    ).fetchone()[0]
    gg = db.execute(
        "SELECT COUNT(*) FROM chat_index WHERE session_id = 'group_group_116381172'"
    ).fetchone()[0]
    print(f'\n📊 group_116381172: {g} rows')
    print(f'📊 group_group_116381172: {gg} rows')

    # Backfill 标记
    done = db.execute(
        "SELECT 1 FROM chat_index WHERE doc_id = '__backfill_done__'"
    ).fetchone()
    print(f'📊 backfill marker: {"present ✅" if done else "MISSING ❌"}')

    total = db.execute("SELECT COUNT(*) FROM chat_index").fetchone()[0]
    print(f'📊 total chat_index rows: {total}')

    db.close()
    print(f'\n{passed} passed, {failed} failed')
    return failed == 0

if __name__ == '__main__':
    sys.exit(0 if run() else 1)
