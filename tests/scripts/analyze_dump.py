#!/usr/bin/env python3
"""Analyze /tmp/llm_full_request.json — full token breakdown by module."""
import json

with open('/tmp/llm_full_request.json') as f:
    data = json.load(f)

total = 0
cats = {}
for i, m in enumerate(data['messages']):
    c = m['content']
    if isinstance(c, list):
        c = ' '.join([str(x.get('text', x)) for x in c])
    cl = len(c)
    total += cl

    if i == 0:
        label = 'System Prompt (人物+指令)'
    elif 'Long-term Memory' in c or 'Current Speaker' in c:
        label = 'LTM 画像'
    elif c.startswith('当前时间'):
        label = '当前时间'
    elif '先前经验' in c or '曾犯错误' in c:
        label = 'Reflection 反思'
    elif '群聊背景' in c:
        label = 'Summary 摘要'
    elif len(c) < 20:
        label = '模式指令'
    elif c.startswith('【') and '】' in c[-50:]:
        label = 'Timeline 历史'
    elif 'Relevant Memories' in c or 'memory-records' in c:
        label = 'LTM RAG检索'
    else:
        label = '用户消息/其他'

    cats[label] = cats.get(label, 0) + cl
    preview = c[:100].replace('\n', ' ')
    print(f'[{i}] {cl:5d}c  {label}')
    print(f'     {preview}...')

print(f'\n{"="*60}')
print(f'Messages 总计: {total} chars (~{total} tokens)')
print()

for k, v in sorted(cats.items(), key=lambda x: -x[1]):
    pct = v * 100 // total
    bar = '█' * (pct // 3)
    print(f'  {k:25s} {v:5d}c  {pct:3d}%  {bar}')

tools_json = json.dumps(data['tools'], ensure_ascii=False)
print(f'\nTools: {data["n_tools"]} 个, 总计 {len(tools_json)} chars (~{len(tools_json)} tokens)')
for t in data['tools']:
    fn = t.get('function', t)
    name = fn.get('name', '?')
    desc = (fn.get('description', '') or '')[:60]
    tc = len(json.dumps(t, ensure_ascii=False))
    print(f'  {name:30s} ~{tc:4d}c  | {desc}')

grand = total + len(tools_json)
print(f'\n╔══════════════════════════════════════╗')
print(f'║  GRAND TOTAL: {grand:5d} chars (~{grand} tok)  ║')
print(f'║  实际 input_tokens: 7287              ║')
print(f'║  覆盖率: {grand*100//7287}%                         ║')
print(f'╚══════════════════════════════════════╝')
