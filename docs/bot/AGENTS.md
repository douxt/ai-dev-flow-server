# AI 会话入口 — Silent Observer 插件

> 新会话看完此文件即可理解全貌，知道去哪找所有资料。

## 项目是什么

LangBot 插件，运行在 NAS Docker 上。功能：QQ 群聊归档 → 向量知识库，@/随机触发 LLM 回复，图片识别。

## 环境

| 组件 | 说明 |
|------|------|
| NAS | `ssh root@nas`, Synology DSM |
| langbot | 主进程, 端口 5300/2280 |
| langbot-plugin | 插件运行时（我们的代码） |
| napcat | QQ 协议, WS 连 langbot:2280 |

Docker 路径：`/volume1/@appstore/ContainerManager/usr/bin/docker`

## 核心代码（最重要）

| 文件 | 说明 |
|------|------|
| [default.py](../../docker/langbot/plugins/silent-observer/components/event_listener/default.py) | **全部逻辑**：gate/inject/save/vision, ~1220行 |
| [main.py](../../docker/langbot/plugins/silent-observer/main.py) | 插件入口, dispose 清理 |

## 文档索引（看完代码后按需读）

| 优先级 | 文档 | 内容 |
|--------|------|------|
| ⭐ | [nas-access-best-practices.md](nas-access-best-practices.md) | 代码地图、部署命令、SSH/Docker 技巧 |
| ⭐ | [silent-observer-dev-journal.md](silent-observer-dev-journal.md) | 开发日志 18 章，架构演进 + 踩坑全记录 |
| ⭐ | [../../.claude/gate-checklists/bot-plugin-review.md](../../.claude/gate-checklists/bot-plugin-review.md) | 改动前审查清单（9 维度 + 17 踩坑） |
| | [automated-testing-guide.md](automated-testing-guide.md) | 测试体系：单元/冒烟/E2E/压力 |

## 测试脚本

| 脚本 | 容器 | 用途 |
|------|------|------|
| `tests/test_smoke.py` | napcat | 冒烟（连通性） |
| `tests/test_e2e_sync.py` | langbot-plugin | E2E 回归 |
| `tests/test_bg_stress.py` | langbot-plugin | 20 并发压力 |
| `tests/test_quote_e2e.py` | langbot-plugin | 引用自动化（不依赖 QQ） |

## 关键 UUID / 配置

- 测试群：`group_1104330614`
- HTTP Bot：`dcbe70d9-af11-4624-908a-9928e4a08bdb`
- 秘密：`udimc123`
- Vision LLM：`61a105e9-6180-45ee-a6f6-a7ec9d713265`（qwen3.6-flash）
- 主 LLM：`b36247de-cea2-4cb4-9557-183f53f4d62b`（deepseek-v4-flash）
- 主 Pipeline：`dc0ff402-edc3-4dab-8054-d2a855241dea`

## 架构速览

```
QQ ←→ napcat ←WS→ langbot ←WS→ langbot-plugin (我们)
                      ↕
                   LLM API
                      ↕
              HTTP Bot (测试入口)
```

gRPC emit_event 不能阻塞。gate handler 秒回，重活走 Queue(10)+3 worker。

## 开发铁律

1. **必须 worktree**：`wt create <任务>`，禁止主仓库直接编辑
2. **改 default.py 先过清单**：`.claude/gate-checklists/bot-plugin-review.md`
3. **部署**：scp → NAS 卷 → 清 `__pycache__` → 重启先 plugin 后 langbot
4. **提交**：每改完一个逻辑点立即 commit，不攒批
5. **清理 pending 不要关 session**：`DELETE` 只删消息，不动 `monitoring_sessions.is_active`

## 已知问题

- 流式去重不完善（1s cooldown 不够）
- LTM 插件缺失（框架层，非致命）
- health-check cron 每 5 分钟触发 LLM pipeline
