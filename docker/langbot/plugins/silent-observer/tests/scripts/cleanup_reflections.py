"""P1.5 反思库清理——chroma 直连软归档冒烟测试污染条目.

在 langbot 容器内运行。⚠️ apply 前必须 docker stop langbot：PersistentClient 双开属
chroma 未定义行为，且 langbot 进程内存 metadata 缓存可能在后续 flush 时把 archived=True
回写覆盖（本库首跑时 langbot 在跑，归档后须重启 langbot 并复查 archived 未被冲掉）：
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
    cols = list(client.list_collections())
    exact = [c for c in cols if getattr(c, 'name', str(c)) == COLLECTION_HINT]
    if len(exact) == 1:
        return exact[0]
    subs = [c for c in cols if COLLECTION_HINT in getattr(c, 'name', str(c))]
    if len(subs) == 1:
        print(f'NOTE: 子串匹配 collection {subs[0].name}（非精确名）')
        return subs[0]
    names = [getattr(c, 'name', str(c)) for c in cols]
    print(f'FATAL: {COLLECTION_HINT} 精确命中 {len(exact)}、子串命中 {len(subs)}（多义拒绝）; 全部: {names}', file=sys.stderr)
    sys.exit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--path', default=None, help='chroma PersistentClient path')
    ap.add_argument('--apply', action='store_true', help='实际归档（默认 dry-run）')
    ap.add_argument('--include-pattern', action='store_true',
                    help='将正则命中但不在白名单的条目一并归档（需人工先行裁决）')
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
    skipped_archived = 0
    for vid, meta, doc in zip(ids, metas, docs):
        if meta.get('archived'):
            skipped_archived += 1
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
          f'{skipped_archived} already-archived, '
          f'{len(ids) - len(targets) - len(flag_only) - skipped_archived} untouched')

    if not args.apply:
        print('DRY-RUN（未修改）。确认清单后加 --apply（正则条目需 --include-pattern）')
        return

    if args.include_pattern:
        targets += flag_only
        flag_only = []
        print(f'--include-pattern: 合并后待归档 {len(targets)} 条')

    if not targets:
        print('nothing to archive')
        return

    from datetime import datetime, timezone, timedelta
    now_iso = datetime.now(timezone(timedelta(hours=8))).isoformat()
    before = col.get(where={'$and': [{'type': 'reflection'}, {'archived': True}]})
    n_before = len(before.get('ids', []))
    new_ids = [t[0] for t in targets]
    new_metas = [{**t[1], 'archived': True, 'archived_at': now_iso} for t in targets]
    col.update(ids=new_ids, metadatas=new_metas)
    print(f'ARCHIVED {len(new_ids)} reflections')

    # 复核（delta 口径）
    check = col.get(where={'$and': [{'type': 'reflection'}, {'archived': True}]})
    print(f'verify: archived delta = {len(check.get("ids", [])) - n_before} (本次应 = {len(new_ids)})')
    print('NOTE: 若 langbot 未停跑，apply 后必须重启 langbot 防止内存缓存回写冲掉 archived 标记')


if __name__ == '__main__':
    main()
