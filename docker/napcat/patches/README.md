# napcat patches

> 最后更新: 2026-07-16

## 补丁清单

| 补丁 | 问题 | 修复方式 |
|------|------|---------|
| forward-timeout | `getMultiMessages` 无超时 → 大转发卡死单群 | Promise.race: getMultiMessages 10s + FetchForwardMsg fallback 5s |

## 前置条件

- napcat 已在 NAS Docker 运行
- `enableLocalFile2Url: true`（防 base64 膨胀）
- 宿主机能 `ssh root@nas`

## 快速部署

```bash
chmod +x apply.sh
./apply.sh
```

## 回滚

```bash
./apply.sh --rollback
```

回滚从 `/tmp/napcat-backups/` 取最新备份，自动恢复 + 重启。

## 部署流程 (apply.sh 内部)

1. 时间戳备份 → 复制到宿主机 `/tmp/napcat-backups/`
2. 检查目标字符串存在（不存在→中止，防版本不匹配）
3. sed 替换（Patch 1a + 1b）
4. 验证新字符串存在（不存在→自动回滚）
5. `node -c` 语法检查（失败→自动回滚）
6. `kill -TERM` 进程级重启 napcat
7. 等待 napcat 恢复（24s 超时）

## cron 巡检（推荐）

```bash
# 每 5 分钟检查补丁存活
*/5 * * * * ssh -oBatchMode=yes root@nas \
  "docker exec napcat grep -q 'Promise.race.*getMultiMessages' /app/napcat/napcat.mjs || \
   echo 'napcat patch lost!' | logger -t napcat-patches"
```

## 手动部署（分步）

```bash
# 1. 备份
ssh root@nas "docker exec napcat cp /app/napcat/napcat.mjs /app/napcat/napcat.mjs.bak.\$(date +%Y%m%d_%H%M%S)"

# 2. Patch 1a: getMultiMessages 10s 超时
ssh root@nas "docker exec napcat sed -i \
  's/let multiMsgs = await this.getMultiMessages(msg, parentMsgPeer);/let multiMsgs = await Promise.race([this.getMultiMessages(msg, parentMsgPeer), new Promise(resolve => setTimeout(() => resolve(null), 10000))]);/' \
  /app/napcat/napcat.mjs"

# 3. Patch 1b: FetchForwardMsg 5s 超时
ssh root@nas "docker exec napcat sed -i \
  's/multiMsgs = await this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId);/multiMsgs = await Promise.race([this.core.apis.PacketApi.pkt.operation.FetchForwardMsg(element.resId), new Promise(resolve => setTimeout(() => resolve(null), 5000))]);/' \
  /app/napcat/napcat.mjs"

# 4. 验证
ssh root@nas "docker exec napcat grep 'Promise.race.*getMultiMessages' /app/napcat/napcat.mjs"
ssh root@nas "docker exec napcat node -c /app/napcat/napcat.mjs"

# 5. 进程级重启
ssh root@nas "docker exec napcat sh -c 'kill -TERM \$(pgrep -f \"node.*napcat\" | head -1)'"

# 6. 恢复确认
ssh root@nas "docker logs napcat --tail 20"
```

## 长期方案

在自定义 napcat Dockerfile 中预打包补丁：

```dockerfile
RUN sed -i 's/.../.../' /app/napcat/napcat.mjs
```

重建容器后自动生效，无需手动 apply。
