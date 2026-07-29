# 步骤 6 灰度部署监控清单

## 部署前检查

- [ ] `uv run pytest tests/ -q` 全绿（当前: 112 passed）
- [ ] `uv run python tests/verify_compat.py` 全绿（当前: 27 passed）
- [ ] `bash scripts/rollback.sh --backup` 已创建当前生产版备份
- [ ] manifest.yaml 配置项 ≥ 旧版（bot_qq/prob/history/kb_id/embedding/timeline/vision × 5/debug_dump = 12 项）
- [ ] KB doc_id 格式不变（`chat:<16hex>`，verify_compat 已覆盖）

## 阶段 1: 测试群部署（`group_1104330614`）

**持续至少 2 小时**

### 部署步骤

```bash
# 1. 部署到 NAS
scp -r plugins/silent-observer/* root@nas:/volume1/docker/langbot/plugins/silent-observer/
ssh root@nas "/volume1/@appstore/ContainerManager/usr/bin/docker exec langbot-plugin rm -rf /app/data/plugins/dou__langbot-silent-observer/__pycache__"
ssh root@nas "/volume1/@appstore/ContainerManager/usr/bin/docker restart langbot-plugin"
sleep 15
ssh root@nas "/volume1/@appstore/ContainerManager/usr/bin/docker exec langbot-plugin cat /tmp/silent_init.log"
# 应看到: [restored: gate=... vision=...]  ← 确认持久化恢复成功
```

### 监控指标（每 30 分钟检查一次）

| 指标 | 检查命令 | 正常范围 | 实际 | 状态 |
|------|---------|---------|------|------|
| 容器运行 | `docker ps \| grep langbot-plugin` | Up | | |
| init.log | `cat /tmp/silent_init.log` | 含 `kb_enabled=` | | |
| gate 命中 | `cat /tmp/silent_event.log` | 有 hit 事件 | | |
| inject 触发 | `cat /tmp/silent_gate.log` | 有 inject START | | |
| inject 报错 | `grep 'inject ERROR' /tmp/silent_gate.log` | **0 条** | | |
| vision 成功率 | `grep 'vision: done' /tmp/silent_gate.log` | ok > fail | | |
| KB 写入 | `grep 'KB upserted' /tmp/silent_gate.log` | 有记录 | | |
| 持久化保存 | `grep 'periodic save' /tmp/silent_gate.log` | 无 fail | | |
| QQ 群回复 | 在测试群发消息 | Bot 正常回复 | | |

### 烟雾测试（部署后 5 分钟执行）

```bash
# @Bot 触发测试
# 在测试群发送: @Bot 你好
# 预期: 5 秒内回复

# 随机插话测试
# 在测试群连续发几条消息
# 预期: prob=0.01 下偶尔插话

# 识图测试（如果 vision_enabled）
# 在测试群发带图消息并 @Bot
# 预期: 回复提及图片内容
```

### 阶段 1 放行条件

- [ ] inject ERROR = 0
- [ ] gate 有命中事件
- [ ] @Bot 触发生效
- [ ] KB 有写入记录
- [ ] 无容器重启
- [ ] 持续 2h 无异常

## 阶段 2: 生产群切换（`group_116381172`）

**仅在阶段 1 全部放行后执行**

### 切换步骤

```bash
# 生产群不需要额外部署（测试群和生产群共用同一容器）
# 但需要确认测试群验证无异常后再等待观察

# 在生产群发一条测试消息
# 检查 gate.log 确认生产群的事件也被正确处理
ssh root@nas "/volume1/@appstore/ContainerManager/usr/bin/docker exec langbot-plugin grep 'group_116381172' /tmp/silent_gate.log | tail -5"
```

### 应急回滚阈值

以下任一条件触发**立即回滚**:

| 触发条件 | 检测方式 | 回滚操作 |
|---------|---------|---------|
| inject ERROR > 0 | `grep -c 'inject ERROR' /tmp/silent_gate.log` | `bash scripts/rollback.sh` |
| 容器反复重启 | `docker ps -a \| grep langbot-plugin` | `bash scripts/rollback.sh` |
| @Bot 不回复（>30s） | QQ 群实测 | `bash scripts/rollback.sh` |
| KB 检索返回空（持续） | 检查 event.log | `bash scripts/rollback.sh` |
| 持续 vision 失败 | `grep 'vision: done' /tmp/silent_gate.log` | 先关 vision_enabled，不回滚 |

### 回滚命令

```bash
# 一键回滚到部署前备份
bash scripts/rollback.sh

# 或指定备份标签
bash scripts/rollback.sh 20260729-143000
```

## 阶段 3: 稳定观察

**生产群切换后持续观察 24 小时**

| 时间 | 检查项 | 结果 |
|------|-------|------|
| +1h | gate hit/miss 比率正常 | |
| +2h | inject 无 ERROR | |
| +6h | vision 日限正常 | |
| +12h | 持久化恢复验证（重启一次容器） | |
| +24h | 整体稳定，宣布步骤 6 完成 | |

## 持久化恢复专项验证

```bash
# 1. 记录当前状态
ssh root@nas "... docker exec langbot-plugin cat /tmp/silent_init.log"
# 应看到: [restored: gate=XX/YY vision=Z]

# 2. 重启容器
ssh root@nas "... docker restart langbot-plugin"
sleep 15

# 3. 验证恢复
ssh root@nas "... docker exec langbot-plugin cat /tmp/silent_init.log"
# gate 计数应接近重启前的值（最多差 5 分钟的增量）
# vision_daily_count 应与重启前一致
```
