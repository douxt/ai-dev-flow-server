# Archon 官方文档参考（关键页面摘要）

@author: Claude Code
@created: 2026-06-22
@source: https://archon.diy

---

## CLI 命令

```bash
# 运行 workflow
archon workflow run <name> [message]
archon workflow run assist --cwd /path/to/repo "What does this function do?"
archon workflow run auto-execute "issues/020-review-types.md"
# 从断点恢复
archon workflow run <name> --resume

# 列出
archon workflow list

# 审批
archon workflow approve <run-id> "Looks good"
archon workflow reject <run-id> --reason "Needs more tests"

# 关闭非交互模式（CI/CD）
archon workflow run <name> --no-interactive

# Web UI
archon serve --port 8420
```

## Workflow YAML 节点类型

| 节点类型 | 字段 | 说明 |
|---------|------|------|
| AI prompt | `prompt:` | LLM 驱动 |
| Shell | `bash:` | 确定性命令，stdout = `$nodeId.output` |
| Script (TS/JS/Py) | `script:` + `runtime: bun \| uv` | 编程语言节点 |
| Loop | `loop:` | 重复执行直到 until 条件 |
| Approval | `approval:` | 暂停等待人工审批 |

## 变量

| 变量 | 含义 |
|------|------|
| `$ARGUMENTS` / `$USER_MESSAGE` | 用户消息 |
| `$1`, `$2`, `$3` | 位置参数 |
| `$ARTIFACTS_DIR` | 产物目录 |
| `$WORKFLOW_ID` | 运行 ID |
| `$BASE_BRANCH` | 基础分支 |
| `$nodeId.output` | 上游节点输出 |

## Loop 配置

- `until: COMPLETE` — AI 输出 `<promise>COMPLETE</promise>` 则结束
- `max_iterations: N` — 硬上限
- `fresh_context: true` — 每轮全新 AI 会话
- 迭代内错误 → 节点立即失败

## 重试

```
SDK 重试：3 次，2s 退避（瞬态错误）
  ↓ 全失败
节点重试：2 次，3s 退避
  ↓ 全失败
workflow 失败 → 人 opt-in resume
```

## 审批节点

```yaml
- id: review-gate
  approval:
    message: "请审查改动"
    capture_response: true
    on_reject:
      prompt: "根据反馈修改"
      max_attempts: 3
```

## DAG 恢复

```bash
archon workflow run <name> --resume
# 已完成节点跳过，从断点继续
# always_run: true 的节点强制重跑
```

## 执行模式

- 默认：有隔离（git worktree）
- `--no-worktree`：无隔离
- `--branch <name>`：指定分支
- `interactive: true`（workflow 级）：审批门在 Web UI chat 出现
- `--no-interactive`：CI/CD 模式，审批门自动通过

## 文件布局

```
.archon/
├── workflows/     # YAML workflow 文件
├── commands/      # Markdown 命令文件
├── scripts/       # .ts/.js/.py 脚本
└── config.yaml    # 项目配置
```
