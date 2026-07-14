# 2026-07-13 Docker 僵尸会话事故报告

> 初步诊断 | 待补充恢复后验证结果

## 一、事件概述

更换 vision 模型后按标准流程重启容器，`docker exec` / `restart` / `kill` 全部超时，langbot 容器假死，napcat 持续 ECONNREFUSED。最终 `synopkg restart ContainerManager` 恢复。

## 二、时间线

| 时间 | 操作 | 结果 |
|------|------|------|
| 11:19 | `docker restart langbot-plugin langbot` | plugin 重启成功，langbot 卡住 |
| 11:20 | `docker exec langbot ...` 查端口 | 超时 |
| 11:21 | `timeout 15 docker restart langbot` | 超时（exit 124） |
| 11:22 | `docker restart napcat` | 成功，但连不上 langbot:2280 |
| 11:23-11:25 | napcat 每 30s 重试 | 全部 ECONNREFUSED |
| 11:25 | `docker kill langbot` | 超时 |
| 11:26 | `docker stop -t 5 langbot` | 超时 |
| 11:27 | 僵尸清理脚本 | 跑通但无效（只清了 exec 会话，没动僵尸日志进程） |
| 11:28 | `ps aux` 查进程 | 发现 **15 个 `docker logs langbot` 僵尸**，最早从 7月12日挂到现在 |
| 11:29 | `kill -9` 杀僵尸进程 | 成功，但 docker restart 仍卡 |
| 11:30 | `synopkg restart ContainerManager` | Docker 守护进程恢复 |

## 三、根本原因

### 直接原因：Docker 守护进程被 15+ 僵尸子进程耗尽

```
root 1766  Jul12  docker logs langbot
root 2022  Jul12  ash -c docker logs langbot | tail -30
root 2023  Jul12  docker logs langbot
...（共 15 个，最早 7月12日 11:00，最新 7月13日 11:24）
```

这些进程由 `ssh root@nas 'docker logs langbot | tail -N'` 触发。管道模式 `docker exec ... | tail` 在 SSH 断开后，docker logs 进程没有正确回收，残留在 Docker 守护进程的子进程树上。

### 触发链路

```
SSH 断开 → ash 会话不回收 → docker logs 子进程僵死 → Docker daemon 的 exec/logs/restart 资源耗尽 → 新操作全部卡死
```

### 为什么现有文档没防住？

[container-restart-best-practices.md](container-restart-best-practices.md) 第六节已记录了僵尸问题，但存在三个盲区：

1. **只管 `docker exec`，没管 `docker logs`**：日志命令同样在容器上创建会话，SSH 管道断开同样残留
2. **`timeout` 没全覆盖**：日常查询命令（`docker exec ... cat log | tail`）没加 `timeout`
3. **清理脚本 Docker 路径错误**：文档写 `/usr/local/bin/docker`，实际是 `/volume1/@appstore/ContainerManager/usr/bin/docker`

## 四、已暴露的问题

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | `docker logs` 管道路径与 `docker exec` 同样产生僵尸 | 高 |
| 2 | 僵尸累积超过 24 小时未被发现（从 7/12 到 7/13） | 高 |
| 3 | `docker restart/kill/stop` 在内核层卡死，timeout 无效 | 高 |
| 4 | 清理脚本只清理 exec 会话，不杀残留日志进程 | 中 |
| 5 | 无僵尸进程数量监控/告警 | 中 |
| 6 | `synopkg` 路径不在标准 PATH，紧急情况下找不到命令 | 低 |

## 五、改进措施

### 立即执行

1. **更新文档** `container-restart-best-practices.md`：
   - `docker logs` 也加 `timeout`
   - 清理脚本加上杀残留 `docker logs` 进程
   - 修正 Docker 路径

2. **标准化 SSH 命令模板** — 所有远程 docker 命令必须：
   ```bash
   # ✅ 正确
   ssh root@nas 'timeout 10 docker exec ...'
   # ❌ 禁止
   ssh root@nas 'docker exec ... | tail'
   ```
   管道操作改用单次 exec + sh -c 内完成。

3. **NAS 添加 cron 巡检**（每 6 小时）：
   ```sh
   #!/bin/sh
   COUNT=$(ps aux | grep -c 'docker (logs|exec)')
   if [ "$COUNT" -gt 5 ]; then
     for cid in $(/volume1/@appstore/ContainerManager/usr/bin/docker ps -q); do
       timeout 3 /volume1/@appstore/ContainerManager/usr/bin/docker exec -d "$cid" true 2>/dev/null
     done
   fi
   ```

### 后续改进

4. 评估是否可以从 Claude Code 侧限制 SSH 调用频率/并发数
5. 考虑用 MCP server 替代 SSH 直连 NAS Docker（如 Portainer API）

## 六、解决结果

- [x] `synopkg restart ContainerManager` 恢复 Docker 守护进程
- [x] langbot、langbot-plugin compose 加 `init: true`（tini 回收僵尸）
- [x] langbot 加 healthcheck（端口 2280 TCP 监听检测）
- [x] `restart: on-failure` → `restart: unless-stopped`
- [x] NAS `/etc/crontab` 加每 30 分钟健康巡检
- [x] 视觉识别模型已切换到 qwen3.7-plus
- [x] `container-restart-best-practices.md` 更新：timeout 规范 + 管道规则 + 三层防御
- [x] napcat WS 连接正常，无 ECONNREFUSED
- [x] 插件初始化正常：`kb_enabled=True vision_enabled=True`
