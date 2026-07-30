---
name: docker-entrypoint-patching
description: 不改 Dockerfile 给上游容器加代码——entrypoint injection 模式
created: 2026-07-20
source: offline-scan
origin_session: d45c2e4d-a6ae-493e-8747-87a3f477d892
---

**根因**：需要改上游容器的 Python 代码（如加 MCP timeout），但不想 fork 镜像或等 PR 合入。原容器无 entrypoint，command 为 `uv run --no-sync main.py`。

**解决**：三步法——① 编写补丁脚本（如 `patch_mcp_timeout.py`，用 `replace()` 精确替换 + MARKER 注释做幂等检测，找不到目标行时报错防静默失败）；② 编写 `entrypoint.sh`（打补丁后 `exec "$@"` 透传原 command）；③ compose.yaml 同时 volumes 挂载两个文件 + `entrypoint: ["/entrypoint.sh"]`。无需 `command` 覆盖，entrypoint 内 `exec "$@"` 自然继承 compose 的 command。

**预防**：① 补丁必须幂等（已应用则跳过不重复打）；② 插桩点如果用多行匹配则避开跨板本行为差异；③ 找不到目标行时报错退出，不静默失败；④ entrypoint.sh 末尾必须 `exec "$@"` 保持信号透传，否则容器无响应；⑤ compose 的 command 继承自镜像或显式写，entrypoint 覆盖后需确认 `exec "$@" 拿到了正确参数。

