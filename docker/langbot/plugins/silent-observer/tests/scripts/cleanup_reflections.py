"""P1.5 反思库清理——chroma 直连软归档冒烟测试污染条目.

在 langbot 容器内运行（需 langbot 已停止以释放 chroma 锁）：
    docker exec langbot python3 /tmp/cleanup_reflections.py --apply
默认 dry-run 只打印清单。id 白名单为主，正则命中但未列白名单者仅提示。
"""
import argparse
import json
import re
import sys

COLLECTION_HINT = 'silent_reflections'

# 8/21 冒烟(/sync) + 容器 pytest 直写生产库的实锤条目（reflection.log）
ID_WHITELIST = {
    'ref:8ac6132cecd91aa6', 'ref:87b8a783630ba25a', 'ref:392b6017ca3eec53',
    'ref:bb26f64be3d005a4', 'ref:cd0f9b58fb27ff77', 'ref:541b378bca129c7f',
    'ref:4b4286a9646c4b2f', 'ref:8d4129ac3d515e91', 'ref:dcd262217cedf034',
}
PATTERN = re.compile(r'380V|断路器|DS920|冒烟|电气|男女冲突')


def find_collection(client):
    for col in client.list_collections():
        name = col.name if hasattr(col, 'name') else str(col)
        if COLLECTION_HINT in name:
            return col
    names = [c.name if hasattr(c, 'name') else str(c) for c in client.list_collections()]
    print(f'FATAL: no collection matching {COLLECTION_HINT!r}; available: {names}', file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', default=None, help='chroma PersistentClient path')
    ap.add_argument('--apply', action='store_true', help='实际归档（默认 dry-run）')
    args = ap.parse_args()

    import chromadb
    path = args.path
    if not path:
        import os
        for cand in ('/app/data/chroma', '/data/chroma'):
            if os.path.isdir(cand):
                path = cand
                break
    print(f'chroma path: {path}')
    client = chromadb.PersistentClient(path=path)
    col = find_collection(client)

    res = col.get(where={'type': 'reflection'}, include=['metadatas', 'documents'])
    ids = res.get('ids', [])
    metas = res.get('metadatas', []) or [{}] * len(ids)
    docs = res.get('documents', []) or [None] * len(ids)
    print(f'total reflections: {len(ids)}')

    targets, flag_only = [], []
    for vid, meta, doc in zip(ids, metas, docs):
        if meta.get('archived'):
            continue
        text = doc or json.dumps(meta, ensure_ascii=False)
        in_white = vid in ID_WHITELIST
        pat_hit = bool(PATTERN.search(text))
        if in_white:
            targets.append((vid, meta, 'whitelist' + ('+pattern' if pat_hit else '')))
        elif pat_hit:
            flag_only.append((vid, meta, 'pattern-only'))

    print('\n--- 待归档（id 白名单命中） ---')
    for vid, meta, why in targets:
        print(f'  {vid}  [{why}]  {str(meta.get("scenario", ""))[:60]}')
    print('--- 正则命中但不在白名单（不自动归档，人工裁决） ---')
    for vid, meta, why in flag_only:
        print(f'  {vid}  [{why}]  {str(meta.get("scenario", ""))[:60]}')
    print(f'\nsummary: {len(targets)} to-archive, {len(flag_only)} flag-only, '
          f'{len(ids) - len(targets) - len(flag_only)} untouched')

    if not args.apply:
        print('DRY-RUN（未修改）。确认清单后加 --apply')
        return

    from datetime import datetime, timezone, timedelta
    now_iso = datetime.now(timezone(timedelta(hours=8))).isoformat()
    new_ids = [t[0] for t in targets]
    new_metas = [{**t[1], 'archived': True, 'archived_at': now_iso} for t in targets]
    col.update(ids=new_ids, metadatas=new_metas)
    print(f'ARCHIVED {len(new_ids)} reflections')

    # 复核
    check = col.get(where={'$and': [{'type': 'reflection'}, {'archived': True}]})
    print(f'verify: archived now = {len(check.get("ids", []))}')


if __name__ == '__main__':
    main()
