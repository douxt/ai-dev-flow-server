# _handoff/ — Agent 协作收件箱

本目录是 Agent A（dev-machine）与 Agent B（__PROJECT__）之间的异步通信通道。

## 目录结构

```
_handoff/
├── README.md              # 本文件
├── TEMPLATE.md            # 消息模板
├── outbox/
│   └── agent-b/           # B 写委托 → A 读取并处理
├── inbox/
│   └── agent-b/           # A 写回复 → B 读取并验证
└── archive/               # 已处理消息归档（>30 天自动清理）
```

## 角色

| 角色 | 身份 | 能力 |
|------|------|------|
| Agent A | dev-machine/agent-a | 完整 shell，基础设施，部署，PR 合并 |
| Agent B | __PROJECT__/agent-b | gate 流程，功能代码，需求→PRD→Issue |

## 通信流程

```
B 发现问题 → 写 outbox/agent-b/ → git push
  → dispatch.sh 检测 → Telegram 通知人
  → 人开 VSCode → A 读消息 → 逐条执行
  → A 写回复到 inbox/agent-b/ → push
  → Telegram 通知"已修复" → B git pull 看到回复
```

## 消息格式

见 TEMPLATE.md。所有消息必须包含 YAML frontmatter（from/to/project/type/id/status）。

## B 的硬性约束

见仓库根 `AGENTS.md` 和 `.claude/CLAUDE.md` 中的 Agent B 行为边界章节。

B 不能做的事：
- 修改 master 分支、合并代码
- 修改受保护文件（.devflow/、Dockerfile、systemd 配置等）
- 执行基础设施操作（systemctl、docker 等）

遇到以上情况 → 写 outbox/agent-b/ 委托 A。
