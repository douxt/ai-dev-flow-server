---
name: nas-deploy-and-smoke-test
description: NAS Docker 部署流程 + 烟雾测试踩坑——Docker 二进制路径、容器隔离、启动等待、DB 跨容器不可达
metadata: 
  node_type: memory
  created: 2026-07-25
  source: stop-hook
  origin_session: d45c2e4d-a6ae-493e-8747-87a3f477d892
  type: feedback
  originSessionId: d45c2e4d-a6ae-493e-8747-87a3f477d892
---

# NAS Docker 部署 + 烟雾测试踩坑

## 根因

1. NAS 的 Docker 二进制不在标准 PATH，`$DOCKER` 变量在远程 shell 中不展开
2. napcat 容器无法访问 langbot-plugin 的 SQLite DB
3. 容器重启后需要 2+ 分钟预热（LangBot 初始化、插件加载、LLM 连接）
4. 部署脚本中的 `$DOCKER` 转义问题：`\$DOCKER` 在本地 shell 正确，但远程 ash shell 不认

## 解决

### 1. Docker 路径问题

```bash
# ❌ 错误：转义变量在远程不生效
ssh root@nas "\$DOCKER exec langbot ..."  # $DOCKER 在远端为空

# ✅ 正确：直接使用完整路径
D="/volume1/@appstore/ContainerManager/usr/bin/docker"
ssh root@nas "$D exec langbot-plugin ..."
# 但更可靠的是直接在命令中写完整路径：
ssh root@nas "/volume1/@appstore/ContainerManager/usr/bin/docker restart langbot-plugin"
```

### 2. 烟雾测试 DB 访问

napcat 和 langbot-plugin 是独立容器，napcat 无法访问 langbot-plugin 的 SQLite。
烟雾测试的 DB 检查改为 HTTP 验证（多轮对话验证 chat_index 时间线正常工作）。

### 3. 容器启动等待

```bash
# 重启后必须等待足够时间
# 实测：8 秒等待有时不够，第一次烟雾测试失败（响应超时）
# 安全值：10-15 秒，或主动检查 init.log
sleep 10
ssh root@nas "$D exec langbot-plugin cat /tmp/silent_init.log"
```

### 4. 部署流程最佳顺序

```
1. scp 代码到 NAS 卷路径（比 docker cp 可靠）
2. 清除 __pycache__（必须先删，否则旧字节码仍运行）
3. 先重启 langbot-plugin，sleep 2，再重启 langbot
4. 等待 10s → 检查 /tmp/silent_init.log
5. 跑烟雾测试（scp 测试文件 → docker cp 到 napcat → docker exec 执行）
```

## 预防

1. deploy.sh 中不要用 `$DOCKER` 变量，直接用完整路径
2. 烟雾测试中的 DB 查询只适用于 langbot-plugin 容器，napcat 容器只能用 HTTP 验证
3. 部署脚本执行前先验证容器可达：
   ```bash
   ssh root@nas "/volume1/@appstore/ContainerManager/usr/bin/docker ps --format '{{.Names}}' | grep -E 'langbot|napcat'"
   ```
4. 烟雾测试失败不要立即认定代码有问题——先检查容器启动时间

**How to apply:**
- 部署：`cd docker/langbot/plugins/silent-observer && ./deploy.sh`
- 仅烟雾测试：`bash tests/run_smoke.sh`
- 验证部署版本：`ssh root@nas "docker exec langbot-plugin grep -c '特征关键词' /app/data/plugins/.../default.py"`
