# Claude Code 会话唤醒手段调研报告

> 2026-09-15 · gale-research L4（止于 R4，缺口 3/5 闭合、2 条与场景无关）· 场景=VSCode(Win)+WSL2+Claude Code for VSCode 扩展环境下，空闲会话能否被定时/外部事件唤醒执行巡检。排除项：需要人每次在线敲回车；不可行项已如实标注。
> 起因实测：会话内置定时器（CronCreate/`/loop` 同族机制）在**面板扩展会话**中 17 个刻度+每分钟探针均零触发。

## 1. 术语对照
| 中文 | 英文 | 区分 |
|---|---|---|
| 唤醒活会话 | push events / inject into a running session | 区别于"续接上下文开新进程"（resume） |
| 通道 | Channels（MCP 推事件进活会话） | 区别于 MCP 工具（被动调用） |
| 跨会话消息 | cross-session messaging（SendMessage/ListAgents） | 会话↔会话，非进程→会话 |
| 例行任务 | Routines（云端调度） | 区别于 scheduled-tasks（本地会话内） |
| 心跳注入 | tmux send-keys heartbeat | 社区土法，仅终端 |

## 2. 候选对比总表
| 候选 | 唤醒面板会话 | WSL2 可用 | 本地文件可见 | 认证要求 | 判语 | 出处 |
|---|---|---|---|---|---|---|
| 会话内置 scheduled tasks | ❌ 实测零触发（官方仅承诺 "running and idle" 的**终端**会话） | 终端可用/面板无 | ✅ | — | 面板不可依赖 | [docs/scheduled-tasks](https://code.claude.com/docs/en/scheduled-tasks) |
| Channels | 仅推**活会话**但要求 claude.ai/Console 认证 | 需 Bun+插件 | ✅ | claude.ai/Console（Bedrock/Vertex/Foundry 排除；网关未验证） | 本机网关认证+面向聊天桥，排除 | [docs/channels](https://code.claude.com/docs/en/channels) |
| Cross-session messaging | ❌ 发射范围不含 VS Code 面板会话；且被 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 整体禁用（本机实测存在） | ✅(含 WSL2，≥2.1.224) | ✅ | 排除 Bedrock/AWS/Foundry/Vertex 清单外 | 对面板=不可用；对终端=可启用 | [docs/cross-session-messaging](https://code.claude.com/docs/en/cross-session-messaging) |
| Routines（云） | ❌ 起新云端会话 | ❌ 云端看不到本地 | ❌ | claude.ai 订阅登录（有 AUTH_TOKEN 即隐藏 /schedule） | 双重死刑，排除 | [docs/routines](https://code.claude.com/docs/en/routines) |
| headless `claude -p`(±`--resume/--bare`) | ❌ 不唤醒面板（另起会话） | ✅ | ✅ | 任意（网关实测可跑） | **今天可用**的无人值守执行体 | [docs/headless](https://code.claude.com/docs/en/headless) |
| tmux send-keys 心跳（CLI 会话） | ✅ 真唤醒（idle 检测后注入 prompt） | ✅ | ✅ | 无 | 有效但要求主会话迁终端 CLI | [issue #27873 正文](https://github.com/anthropics/claude-code/issues/27873)、[claude-tmux-orchestration](https://github.com/primeline-ai/claude-tmux-orchestration)、[samwize 实践](https://samwize.com/2026-03-14/how-i-got-claude-code-to-monitor-slack-while-i-was-on-holiday) |

## 3. 排除清单及原因
- Channels / Routines / `/schedule`：认证墙（claude.ai 订阅或 Console key，本机为第三方网关 token；Routines 另需云端执行，看不到 WSL 文件）
- 外部注入面板：官方无入口——#24947 `claude inject`、#15553 programmatic input、#27441、#27873（VS Code Remote WSL2 用户原声）全部 open 或关为重复，issue #27873 明说面板是 webview contenteditable、`sendSequence` 打不进
- 内置会话定时器：官方语义=session-scoped+idle 才触发，面板实测失效，不作依赖

## 4. 关键技术判断
- **分化点**："唤醒"若特指**这个面板会话**——现环境无任何官方或社区手段，只有 CLI 形态可被唤醒（tmux send-keys / 升级+撤 kill-switch 后的 SendMessage terminal↔terminal）。
- **"无人值守巡检"的务实解**：触发器外置（WSL systemd timer——本机 pid1=systemd 已实证，`loginctl` Linger=off 待处理），执行体=headless `claude -p --bare`，动作=查台账指纹→异常自动 stop→写 ALERT 文件。"喊人"降级为"留字条"，下次会话续接时读。
- 采购前必测：①systemd user timer 在 WSL 是否存活跨 VSCode 断连 ②`--resume` 并发同一 session 与面板的互斥行为（若用 B 案）。

## 5. 缺口裁决表
| 缺口 | 状态 | 证据 |
|---|---|---|
| G1 本机是否存在 feature-flag 杀手 | 已闭合（存在） | env 实测 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`（shell + settings.local.json），官方文档规定该变量禁用 messaging |
| G2 面板会话能否收 SendMessage | 已闭合（不能） | 发布范围"same-machine CLI sessions at launch"，changelog 无面板支持条目 |
| G3 ≥2.1.224 升级可得性 | 已闭合 | 2026-08-07 发布（31 changes），扩展/CLI 均可升 |
| G4 原生 Windows 版本门槛（2.1.234 vs 2.1.239 两说） | 存疑·不影响 | 本机 WSL2 Linux 路径，无需裁决 |
| G5 WSL systemd-timer 持久性 | 未闭合（部署细节非唤醒手段） | 落地时实测 |

## 6. 推荐结论
- **短期（今晚主段/pilot 巡检用）**：headless 哨兵——WSL 侧 timer 每 15min `claude -p --bare` 跑四类指纹检查（diverted/零工/非 ok/跨臂日志逐字相同），异常即 `pilot_ctl stop` 冻结+写 `runs/ALERT`；恢复=下次人上线读字条。
- **中期（若"必须唤醒会话"成硬需求）**：主会话迁 CLI-in-tmux（放弃面板 UI，得 diff 可读性折损），心跳脚本社区成熟（claude-tmux-orchestration / Claudeman respawn 模式）；升级 ≥2.1.224 并从 settings.local.json/shell 撤 kill-switch 后可换 SendMessage 注入（terminal 会话间，比 send-keys 干净）。
- **长期观望**：#24947/#15553 若落地 `claude inject`/扩展 sendMessage 即回到正解，盯 issue。

## 7. 来源列表
上文表格内全部 URL；另：[changelog](https://code.claude.com/docs/en/changelog)、[whats-new w32](https://code.claude.com/docs/en/whats-new/2026-w32)、[blakecrosley](https://blakecrosley.com/blog/claude-code-cross-session-messaging)、[classmethod 2.1.224](https://dev.classmethod.jp/en/articles/20260807-cc-updates-v2-1-224/)、[issue #24947](https://github.com/anthropics/claude-code/issues/24947)、[issue #15553](https://github.com/anthropics/claude-code/issues/15553)、[issue #27441](https://github.com/anthropics/claude-code/issues/27441)、[claude-mux](https://www.reddit.com/r/ClaudeAI/comments/1srtnf3/claudemux_persistent_tmux_sessions_for_claude/)、[tmux 持久会话指南](https://www.devas.life/how-to-run-claude-code-in-a-tmux-popup-window-with-persistent-sessions/)。
