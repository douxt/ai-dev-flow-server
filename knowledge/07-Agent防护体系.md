# Agent 防护体系

> 防止 AI 代码生成 agent（Claude Code）在 AFK 开发过程中产生多余操作、越界访问、遗漏任务的方法论与落地记录。

## 核心原则

**"System prompts are not security boundaries."** — 2025 行业共识。Prompt 规则是建议性的，Agent 可以读、承认、但照样忽略。必须多层叠加：机械阻断 → 工具白名单 → Hook 拦截 → Prompt 约束，缺一不可。

## 防线下钻

```
第 5 层: Prompt 软约束      ~50-70%  ← 建议性，Agent 可能忽略
第 4 层: .claudeignore        ~90%   ← 上下文排除，Agent 看不到
第 3 层: deny 规则            ~80%   ← 机械阻断工具访问，但可被 Bash/Skill 绕过
第 2 层: PreToolUse hooks     ~100%  ← 不可绕过的物理阻断，覆盖 Skill/Bash/Read 等
第 1 层: --allowed-tools      ~100%  ← 工具级白名单，但 Skill 可能绕过
```

**deny 规则已知绕过方式**：`python -c "open('.env').read()"` 替代 `cat .env`。`Skill` 替代 `WebSearch`。Hook 层专门拦截这类绕过。

## 落地方案全览

### 防乱跑

| # | 措施 | 机制 |
|---|------|------|
| 1 | pycache 清理 | prep-once.sh 执行前 |
| 2 | `.claudeignore` | 上下文排除（pycache/secrets） |
| 3 | `settings-afk.json` deny | Read/Bash 工具阻断 |
| 4 | `--allowed-tools` 白名单 | 工具级拦截 |
| 5 | Prompt：禁止行为/角色边界/变更预算 | 软约束 |
| 6 | PreToolUse hook：硬阻断 secret.json + Skill | 不可绕过 |
| 7 | Prompt：禁止 ls/find/Glob 探索 | 软约束 |
| 8 | 可读文件白名单：issue 明确列出 | 需读 > 禁读 |
| 9 | 可用依赖与接口表格 | 预置 SDK 信息，抑制探索动机 |

### 防漏做

| # | 措施 | 机制 |
|---|------|------|
| 10 | 完成检查表（7 项） | Prompt 软约束 |
| 11 | 外部依赖规则 | 默认真连，issue 说 mock 则 mock |
| 12 | `prep-once.sh` 前置准备 | Docker/文件/token 检查 |
| 13 | 通用 Token 注入 | secret.json → /tmp/maf-env.sh |
| 14 | Issue 前置准备章节 | 标准化 issue 模板 |
| 15 | Issue 拆分原则 | ≤1d，按阶段拆 |
| 16 | HITL 过滤 | prep/ralph 跳过非 AFK |
| 17 | PROMPT heredoc | 彻底消除 bash 转义 |

### 防迷路

| # | 措施 | 机制 |
|---|------|------|
| 18 | TDD 流程强制拆 commit | 每模块 test+impl → commit |
| 19 | 导入模式指引 | import 路径参考 |
| 20 | 目录以 issue AC 为准 | 禁止自建目录 |
| 21 | 测试文件扫描注入 | prep-once 扫描 → prompt 列出 |
| 22 | Token 验证命令 | `os.environ` 直查，无需读文件 |
| 23 | 参数匹配检查 | 检查表要求函数签名对齐 issue 描述 |

## 关键实践

### 1. 清理残留 + .claudeignore

AFK 循环中，`__pycache__/` 下的旧 `.pyc` 文件引诱 agent 花大量时间反编译。解决：
- 跑 AFK 前清理缓存
- `.claudeignore` 排除编译产物和敏感文件

```
__pycache__/
*.pyc
config/secret.json
.env
.env.*
dist/
*.tmp
/tmp/
```

### 2. AFK 专用 deny 规则

创建 `.claude/settings-afk.json`，deny 规则覆盖：
- 敏感文件：`config/secret.json`、`.env*`、`~/.ssh/**`
- 编译缓存：`__pycache__/**`
- 运行时目录：`workspace/**`、`logs/**`

**局限性**：deny 只拦截 Read/Write 工具。Agent 可通过 Bash `python -c "open('secret.json')"` 绕过 → 见实践 6。

### 3. CLI 工具白名单

在 ralph-once.sh 中通过 `--allowed-tools` 限制：
- 阻止 `Agent`（subagent 全库探索）
- 阻止 `WebSearch`/`WebFetch`（上网搜索）
- **注意**：`Skill` 可能绕过此限制 → 见实践 6

### 4. Prompt 软约束体系

**禁止行为**：
```
- 禁止以任何方式访问 config/secret.json
- 禁止反编译 __pycache__
- 禁止修改非 issue 范围的文件
- 禁止新增依赖（除非 issue 明确要求）
- 禁止尝试恢复已删除的代码
- 禁止读取与 issue 无关的代码
- 禁止将所有改动攒到一个 commit
- 禁止用 ls/find/Glob 遍历探索项目目录结构
```

**完成检查表**：
```
- AC 清单中的每一条都已实现
- issue 正文中的额外约束必须实现，禁止自行判断"不必要"而跳过
- 函数/模块参数要与 issue 正文描述对齐，不要过度简化
- 外部依赖已对接
- 涉及外部系统必须实际连接跑通端到端，不能只 mock
- 所有新模块都有对应单元测试
- 未修改非 issue 范围的文件
- 每个逻辑点已单独 commit
```

### 5. prep-once.sh — AFK 前置准备

Agent 不能启动 Docker、准备文件。由独立脚本完成：
1. 扫描 ready issue
2. git pull + 清理 pycache
3. 启动外部服务（Docker 等）
4. 检查测试文件（扫描 → `/tmp/maf-test-files.txt`）
5. 导出所有 secret.json key → `/tmp/maf-env.sh`
6. 跳过 HITL issue
7. 输出状态报告

### 6. PreToolUse Hook — 硬阻断

**问题**：prompt 规则和 deny 规则无法阻止 Agent 用 Bash 绕过读取 secret.json；`Skill` 工具可绕过 `--allowed-tools` 白名单。

**解决**：PreToolUse hook，覆盖 `Bash|Read|Glob|Skill` 工具调用。

```bash
# 拦截 Skill
if [ "$TOOL_NAME" = "Skill" ]; then
    echo "BLOCKED: Skill 在 AFK 模式下禁止使用" >&2
    exit 2
fi

# 拦截 Bash 中的 secret.json
if echo "$CMD" | grep -qF 'secret.json'; then
    echo "BLOCKED: 禁止访问 config/secret.json" >&2
    exit 2
fi
```

exit code 2 将 stderr 作为反馈返回给 Agent，Agent 知道原因并调整行为。

### 7. Token 注入 + 验证

- prep-once.sh 将 secret.json 所有 key 大写导出到 `/tmp/maf-env.sh`
- ralph-once.sh 测试前 `source /tmp/maf-env.sh`
- Prompt 给验证命令：`python3 -c "import os; print(os.environ.get('TOKEN','')[:8])"`
- 代码从 `os.environ['TOKEN']` 读取

### 8. PROMPT Heredoc

PROMPT 用双引号字符串时，中文引号反复打断 bash 解析。改为 unquoted heredoc：

```bash
PROMPT=$(cat <<PROMPT_EOF
...prompt 内容，任意引号、反引号、特殊字符均可...
PROMPT_EOF
)
```

### 9. 测试文件扫描注入

prep-once.sh 扫描测试数据目录，ralph-once.sh 注入 PROMPT：

```
## 可用测试文件
/data/file1.pdf
/data/file2.pdf
以上路径已知，直接 Read 使用，禁止用 ls/find 查找。
```

### 10. HITL Issue 过滤

prep-once.sh 和 ralph-once.sh 检查 issue 的 `type:` 字段，跳过非 AFK：

```bash
ISSUE_TYPE=$(grep "^type:" "$ISSUE_FILE" | awk '{print $2}')
if [ "$ISSUE_TYPE" != "AFK" ]; then
    exit 0
fi
```

### 11. Issue 拆分原则

- 单 issue 工时 ≤1d
- 能独立验证、独立交付的算一个 issue
- Issue 正文自带"分阶段"描述的，直接按阶段拆
- 拆分后依赖链清晰，明确 blocked_by
- 类型标记：AFK / HITL

### 12. 可用依赖预注入

prompt 新增可用依赖与接口表格，列出已安装 SDK 的 import 路径和调用方式。最后追加禁令：`所有依赖已安装，不要在 curl 或网上找 API 文档`。

### 13. API 参数匹配检查

完成检查表增加硬约束：
```
- [ ] 函数/模块的输入参数要与 issue 正文描述的行为匹配，不要过度简化
```

## 防护层级对比

| 绕过方式 | 对应防护 |
|----------|----------|
| `Read(secret.json)` | deny 规则 + hook 拦截 |
| `python -c "open('config/secret.json')"` | hook 拦截 all Bash 含 secret.json |
| `Skill(firecrawl-*)` | hook 拦截 Skill 工具 |
| `ls / find` 探索目录 | prompt 禁令 + 文件注入 |
| curl 探 API | 依赖表格注入 |
| 正文化引号打断 | heredoc 彻底解决 |
| Agent 工具全库扫 | --allowed-tools 白名单 |

## 参考来源

- [Claude Code Hooks](https://claude.com/blog/how-to-configure-hooks)
- [Claude Code Safety Net](https://github.com/kenryu42/claude-code-safety-net)
- [Claude Code Governance RFC](https://github.com/anthropics/claude-code/issues/45427)
- [Agent Governance Framework](https://github.com/Wiktor-Potapczyk/agent-governance-framework)
- [The Change Budget Prompt](https://dev.to/novaelvaris/the-change-budget-prompt-stop-scope-creep-in-ai-assisted-coding-4jbd)
