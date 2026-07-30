# Claude Code → OpenCode 迁移最佳实践

> 状态：持续更新 | 日期：2026-07-10 | 环境：Linux, DeepSeek V4 系列

## 一、配置文件对照表

| Claude Code | OpenCode | 兼容/状态 |
|-------------|----------|----------|
| `~/.claude/CLAUDE.md` | `~/.config/opencode/AGENTS.md` | opencode 自动 fallback 读取 |
| 项目 `CLAUDE.md` | 项目 `AGENTS.md` | 同上，用 `/init` 生成 |
| `~/.claude/settings.json` | `~/.config/opencode/opencode.jsonc` → `permission` | 需手工转换 |
| `~/.claude/skills/*/SKILL.md` | `~/.config/opencode/skills/*/SKILL.md` | 自动兼容，同格式 |
| 项目 `skills/*/skill.md` | `.opencode/skills/*/SKILL.md` | 文件名大小写差异，已兼容 |
| `.claude/hooks/*.js` | `.opencode/plugins/` | **不兼容**，需重写 |
| CC PreToolUse 钩子 | 无等价物 | 改为 permission 规则 + plugins |
| CC PostToolUse 钩子 | 无等价物 | 同上 |

**优先级**：`AGENTS.md` > `CLAUDE.md`；`.opencode/skills/` > `.claude/skills/`；全局 < 项目级

## 二、Agent 设计模式

### CC 模式 → opencode 映射

```
CC 的 "Plan Mode" toggle → opencode 的 plan primary agent (Tab 切换)
CC 的 /compact → opencode 的 auto compaction (配置 compaction.auto: true)
CC 的 Task 子代理 → opencode 的 subagent 系统 (Task tool + @mention)
CC 的单一模型 → opencode 的 per-agent model 覆盖
```

### 当前方案（已完成）

```
build (primary, DeepSeek V4 Pro)  → 主力开发
plan (primary, 继承主模型)        → 分析/方案，禁止 edit/bash
flash-explore (subagent, V4 Flash) → 代码探索，只读
flash-general (subagent, V4 Flash) → 通用研究/执行
flash-scout (subagent, V4 Flash)   → 快速查找
```

### 已知坑

- **Bug #21952**：内置 agent 的 `model` 覆写不生效，subagent 仍继承主模型 → 解决方案：创建独立名称的自定义 agent（如 `flash-explore` 代替 `explore`），通过 `instructions` 提示主模型使用它们
- **建议**：update 到最新 opencode 版本检查是否已修复

### 扩展建议

根据 ai-dev-flow-server 的 gate 体系，可创建专用 agent：

```jsonc
"agent": {
  "gate-grill": {
    "mode": "subagent",
    "description": "Gate 1 — 需求对齐拷问",
    "model": "deepseek/deepseek-v4-pro",
    "prompt": "task:./skills/gate-1-grill/skill.md",
    "permission": { "edit": "deny" }
  }
}
```

## 三、权限迁移指南

### settings.json → opencode.json permission

```jsonc
// CC settings.json:
{ "permissions": { "allow": ["Bash(git *)", "WebFetch(domain:github.com)"], "additionalDirectories": ["/path/to"] } }

// opencode 等价:
{
  "permission": {
    "bash": { "git *": "allow" },
    "webfetch": { "*github.com*": "allow" },
    "external_directory": { "/path/to/**": "allow" }
  }
}
```

### 转换规则

| CC 写法 | opencode 写法 | 说明 |
|---------|--------------|------|
| `Read(*)` | `read: "allow"` | 默认已 allow |
| `Edit(*)` | `edit: "allow"` | 默认已 allow |
| `Bash(git *)` | `bash: {"git *":"allow"}` | 对象语法 |
| `Bash(*)` | `bash: "allow"` | 简写 |
| `WebFetch(domain:x.com)` | `webfetch: {"*x.com*":"allow"}` | 通配符匹配 |
| `additionalDirectories` | `external_directory: {"path/**":"allow"}` | 目录树匹配 |

### 三种动作

- `"allow"` — 无需确认
- `"ask"` — 弹窗确认
- `"deny"` — 禁止

### 重要默认值

- `edit`、`bash`、`read` 默认 `allow`
- `doom_loop`、`external_directory` 默认 `ask`
- `.env` 文件读取默认 `deny`（.env.example 除外）

## 四、代价与风险清单

### 可复用（零成本）

- [x] 20+ 全局 skills（`~/.claude/skills/`）→ 自动加载，格式不变
- [x] 7 个 gate skills → 自动加载（skill.md 大小写兼容）
- [x] MCP server 配置 → 写到 opencode.json 的 `mcp` 段
- [x] `wt` 工具 → 独立 shell 脚本，与编辑器无关
- [x] `~/.git-hooks/pre-commit` → git 层面，不受影响

### 需重建（中等成本）

- [ ] **4 个钩子脚本**：`log-activity.js`、`pre-compact.js`、`sync-context.js`、`sync-plan.js`
  - 改为 opencode plugins（TypeScript/JavaScript，遵循 plugin API）
  - 或改为首次 session 时执行 `AGENTS.md` 指令
- [ ] **权限规则**：从 settings.json 逐条转换
- [ ] **记忆碎片化**：CC 用 `~/.claude/projects/` 分项目存记忆 → opencode 用 `~/.config/opencode/` 统一配置 + 项目 `AGENTS.md`
  - 关键决策继续写 `memory/` 或 `CLAUDE.md`，确保跨会话可查

### 不兼容（高风险）

- [ ] **PreToolUse/PostToolUse 钩子**：opencode 无等价机制
  - file-guard 和 bash-firewall 的 Edit/Write 拦截功能无法直接迁移
  - 替代：用 permission 规则做限制（`edit: { "*": "deny", "src/**": "allow" }`）
  - 审计：依赖 `audit-log` 的位置需另找方案

### 新能力（收益）

- [x] **多 session 并行**：同时开多个 agent，自动端口隔离
- [x] **会话分享**：`/share` 生成链接给团队
- [x] **LSP 集成**：opencode 自动加载 LSP 辅助代码理解
- [x] **per-agent 模型**：主力用 Pro、子任务用 Flash，Token 成本更优
- [x] **远程配置**：`.well-known/opencode` 组织级统一配置
- [x] **撤销/重做**：`/undo` `/redo` 比 CC 灵活

## 五、分步迁移路线

### 阶段 1：基础验证（已完成）

- [x] 安装 opencode（`npm install -g opencode-ai`）
- [x] 配置模型 + provider（`~/.config/opencode/opencode.jsonc`）
- [x] 验证 `opencode debug config` 通过
- [x] 验证 API 连通性 + 模型列表
- [x] 创建 flash-* subagent + instructions 解决 bug #21952

### 阶段 2：权限对齐

- [ ] 从 `.claude/settings.json` 提取所有 allow 规则
- [ ] 逐条转为 opencode.json 的 permission 对象
- [ ] 给 build agent 收窄权限（如 `git push` → ask）
- [ ] 给 plan agent 确认 edit/bash → deny
- [ ] 配置 `external_directory` 覆盖 additionalDirectories

### 阶段 3：钩子重建

- [ ] 分析 4 个钩子的功能（log-activity、pre-compact、sync-context、sync-plan）
- [ ] 判定哪些可以用 permission 替代，哪些需要 opencode plugin
- [ ] 对必须 plugin 的，用 opencode plugin API 重写
- [ ] 对可简化的，改为 AGENTS.md 指令（如 session 开始时 sync context）

### 阶段 4：收尾

- [ ] 运行 `opencode /init` 生成项目 `AGENTS.md`
- [ ] 将 CLAUDE.md 中 opencode 不理解的规则（如 CC hook 相关）标记为条件段
- [ ] 删除已失效的 CC 专属配置（如 settings.json 中被迁移的规则）
- [ ] 写 `memory/opencode-known-issues.md` 记录踩坑

## 六、常见问题

### Q: CLAUDE.md 和 AGENTS.md 同时存在怎么办？

AGENTS.md 优先。建议先用 `/init` 生成 AGENTS.md，再逐步从 CLAUDE.md 迁移内容过去。

### Q: skills 文件名大小写？

opencode 兼容 `skill.md` 和 `SKILL.md`。建议统一为 `SKILL.md`（大写）避免潜在问题。

### Q: worktree 机制还可用吗？

`wt` 是独立 shell 工具，与编辑器解耦。worktree 开发流程不受影响。

### Q: 如果不小心切回 CC 怎么办？

CLAUDE.md 保留不变，openCode 会 fallback 读取，CC 正常读取。两者可同时存在，过渡期无风险。

### Q: subagent 模型不生效？

已知 bug #21952。当前 workaround：创建独立名称的自定义 agent，在 instructions 中要求主模型使用它们。定期检查 opencode 更新看是否修复。
