#!/usr/bin/env python3
"""LangBot 事件循环阻塞防护补丁（process.py + monitoring_helper.py 转制）。

原 patches/process.py / monitoring_helper.py 为整文件替换版，未注册进
entrypoint → 容器重建后丢失（2026-08-28 md5 核实），事件循环保护当前未生效。
本脚本改为其幂等原地 patch 形态，可随 entrypoint 每次启动自动重放。

对象（langbot 容器）：
  /app/src/langbot/pkg/pipeline/process/process.py
  /app/src/langbot/pkg/pipeline/monitoring_helper.py
"""
import shutil
import sys

MARKER = '[EVL-BLOCK-PATCH]'

FILES = {
    '/app/src/langbot/pkg/pipeline/process/process.py': [
        # 块内 logger.info 与 str() 均在 async def process 内，缩进一致（8 空格）
        (
            """        message_text = str(query.message_chain).strip()

        self.ap.logger.info(
            f'Processing request from {query.launcher_type.value}_{query.launcher_id} ({query.query_id}): {message_text}'
        )""",
            """        # [EVL-BLOCK-PATCH] str() of a huge message_chain blocks the event loop
        loop = asyncio.get_running_loop()
        message_text = await loop.run_in_executor(None, lambda: str(query.message_chain).strip())

        self.ap.logger.info(
            f'Processing request from {query.launcher_type.value}_{query.launcher_id} ({query.query_id}): {message_text[:500]}'
        )""",
        ),
        (
            "import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query\n",
            "import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query\nimport asyncio\n",
        ),
    ],
    '/app/src/langbot/pkg/pipeline/monitoring_helper.py': [
        # 同步 dump 点之一；其余三处 resp 序列化在下游 try 内（降级可接受，不过度 patch）
        (
            """            if hasattr(query, 'message_chain') and hasattr(query.message_chain, 'model_dump'):
                message_content = json.dumps(query.message_chain.model_dump(), ensure_ascii=False)""",
            """            if hasattr(query, 'message_chain') and hasattr(query.message_chain, 'model_dump'):
                # [EVL-BLOCK-PATCH] model_dump()+json.dumps() on huge chains blocks the event loop
                loop = asyncio.get_running_loop()
                message_content = await loop.run_in_executor(
                    None, lambda: json.dumps(query.message_chain.model_dump(), ensure_ascii=False)
                )""",
        ),
        (
            "import time\n",
            "import time\nimport asyncio\n",
        ),
    ],
}

# 自测用路径映射：--map <容器路径>=<副本路径>（可多次）
_argmap = dict(a[len('--map='):].split('=', 1) for a in sys.argv[1:] if a.startswith('--map='))
_skip = {a[len('--skip='):] for a in sys.argv[1:] if a.startswith('--skip=')}
if _argmap:
    FILES = {_argmap.get(k, k): v for k, v in FILES.items()}
if _skip:
    FILES = {k: v for k, v in FILES.items() if not k.endswith(tuple(_skip))}

exit_code = 0
for target, hunks in FILES.items():
    with open(target) as f:
        content = f.read()

    if MARKER in content:
        print(f'{target}: {MARKER} already applied, skip')
        continue

    missing = [i for i, (old, _) in enumerate(hunks) if old not in content]
    if missing:
        print(f'{target}: {MARKER} ERROR anchors missing {missing} (上游改版？人工核对)')
        exit_code = 1
        continue

    shutil.copyfile(target, target + '.orig-evl')
    for old, new in hunks:
        content = content.replace(old, new, 1)
    with open(target, 'w') as f:
        f.write(content)
    print(f'{target}: {MARKER} applied (backup: {target}.orig-evl)')

sys.exit(exit_code)
