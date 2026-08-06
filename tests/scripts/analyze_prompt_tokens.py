#!/usr/bin/env python3
"""分析 prompt 各模块 token 占比——从 raw prompt dump 读数。"""
import re

with open('/tmp/silent_gate.log') as f:
    content = f.read()

raw_prompts = content.split('=== LLM RAW PROMPT [')
print(f'Total raw prompts: {len(raw_prompts) - 1}')

# Analyze last 5
for idx, raw in enumerate(raw_prompts[-6:-1], 1):
    if not raw.strip():
        continue

    time_str = raw.split('] ===')[0] if '] ===' in raw else '?'
    body = raw.split('] ===\n', 1)[-1] if '] ===\n' in raw else raw

    sections = []
    for block in body.split('--- ['):
        if not block.strip():
            continue
        try:
            header_end = block.index(']\n') if ']\n' in block else block.index('\n')
            header = block[:header_end]
            msg_body = block[header_end+1:].rstrip('\n')

            role_part = header.split(' role=')[1] if ' role=' in header else '?'
            role = role_part.split(' (')[0] if ' (' in role_part else role_part
            char_count = len(msg_body)

            sections.append({'role': role, 'chars': char_count, 'preview': msg_body[:80]})
        except:
            pass

    total = sum(s['chars'] for s in sections)
    print(f'\n--- Prompt {idx} [{time_str}] total={total}c across {len(sections)} msgs ---')

    cats = {'time': 0, 'reflection': 0, 'summary': 0, 'separator': 0, 'timeline': 0, 'other': 0}
    for s in sections:
        p = s['preview']
        if '当前时间' in p:
            cats['time'] += s['chars']
        elif '场景：' in p or '曾犯错误' in p:
            cats['reflection'] += s['chars']
        elif '群聊背景' in p:
            cats['summary'] += s['chars']
        elif s['chars'] < 20 and s['role'] == 'system':
            cats['separator'] += s['chars']
        elif '2026-' in p or '机器豆' in p or '小通豆' in p or 'hentai3' in p:
            cats['timeline'] += s['chars']
        else:
            cats['other'] += s['chars']
            print(f'  UNKNOWN: [{s["role"]}] {s["chars"]}c: {p[:100]}')

    for k, v in sorted(cats.items(), key=lambda x: -x[1]):
        if v > 0:
            pct = v * 100 // max(total, 1)
            bar = '█' * (pct // 5)
            print(f'  {k:12s}: {v:5d}c ({pct:3d}%) {bar}')
