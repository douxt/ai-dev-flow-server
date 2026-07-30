---
name: devflow-v3-evolution-lessons
description: DevFlow v3.0→v3.2 全流程演进踩坑——Hook叠加、文档同步、skill覆盖、AFK恢复
created: 2026-07-24
source: stop-hook
metadata: 
  node_type: memory
  type: project
  originSessionId: 60ba59f5-6030-454f-82eb-c0d04f5099d3
---

## v3.0→v3.2 演化路径

```
v3.0: grill → to-spec → to-tickets → implement → code-review (5阶段)
v3.1: +spec评审 +TDD前置 +tdd门禁 +就绪门禁
v3.2: Hook叠加 +AFK自动续跑 +C1-C4转换检查 +文档同步 +上下文管理
```

## 核心教训

### 1. Skills/Hooks 分离原则（最重要）

**Why:** v3.1 把 DevFlow 约束嵌入了 upstream skill（implement Prerequisites、to-spec step4），导致：
- 上游更新时冲突
- sync-skills.sh 会覆盖修改
- 职责混淆

**How to apply:** Skills=内容(上游不改), Hooks=约束(DevFlow), Gate Checklists=门禁标准
- 不改 `skills-cache/*/SKILL.md`（除 sync-skills.sh 的同步逻辑）
- 所有流程提醒/门禁引用注入到 `hooks/stage-tracker.sh`、`hooks/workflow-gate.sh`
- 检查清单放在 `gate-checklists/`

### 2. 多文档版本同步（v3.2 最大踩坑）

**Why:** v3.2 升级只改了 `.claude/CLAUDE.md` 和 hooks，漏了 10 个文件：
- `knowledge/01-核心方法论.md`、`02-Step-Gate流程.md`、`templates/gate-state.yml`
- 6 个 `gate-checklists/*.md`
- `templates/CLAUDE.md.base.append`（还残留一份 5 阶段定义）

AI 读到矛盾指令（一份说 6 阶段停，一份说 5 阶段不用停）→ 行为退化到最简路径。

**How to apply:** 版本升级时必须全面审计 + 修复后验证。审计命令：
```bash
grep -rn "v3\.[0-9]\|旧阶段数" knowledge/ templates/ gate-checklists/
```

**How to prevent:** 每次版本升级计划中必须有"全面文档同步"步骤，列出所有受影响文件。

### 3. install.sh cp -rL 覆盖问题

**Why:** `cp -rL source_dir existing_dir` 当 dest 已存在时会把源复制到目标内部（不覆盖）。
修复方案：先 `mv dest → dest.bak-timestamp`，再 `cp -rL source dest`。

**额外问题:** dest 为 symlink 时 `[ -d "$dst" ]` 返回 false，备份逻辑跳过，cp 报 "cannot overwrite non-directory"。

### 4. TDD 前置与 AFK 的平衡

**Why:** v1.0 TDD+实现在一起，AFK 全自动但可能造假。v3.1 强制 TDD 独立后 AFK 断裂。

**解决方案:** 混合模型——人管决策边界，Agent 管执行
- 人工唯一介入点: C1-C4 确认（确认 RED 为真）
- AFK: /implement 自动重试最多 3 次
- 同层无依赖 ticket 可并行 /implement

### 5. 上下文管理策略

**When to /clear vs /compact vs 新会话:**
- spec:done → /compact（评审前清理）
- tickets:done → handoff + /clear + 新会话（最佳断点）
- tdd:done → /compact（批次间）
- /review-cc-cli、/code-review → 已用独立子代理，自动隔离

## 相关记忆

- [[worktree-merge-lessons-20260717]] — worktree 合并踩坑
- [[working-style-feedback]] — 协作铁律
- [[langbot-plugin-best-practices]] — 插件开发最佳实践
