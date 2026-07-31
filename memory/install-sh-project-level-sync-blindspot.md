---
name: install-sh-project-level-sync-blindspot
description: install.sh --update 只部署用户级 .claude/，项目级独立拷贝（gate-checklists/hooks）不被同步
created: 2026-07-31
source: manual
metadata:
  type: project
  related:
    - devflow-v3-evolution-lessons
    - hook-reminder-staleness-causes-gate-skip
---

# install.sh --update 项目级文件同步盲区

## 根因

`install.sh --update` 部署目标有两层：
- 用户级：`$CLAUDE_HOME/.claude/`（~/.claude/）← 默认部署目标
- 项目级：`$TARGET/.claude/`（项目/.claude/）← 仅当项目有独立拷贝时才需同步

部分项目的 `.claude/` 下有独立文件（非 symlink、不同 inode），这些文件**不被 --update 覆盖**。用户级的更新不会传播到项目级。

## 已发现的盲区（两次）

### 1. gate-checklists

```bash
# 用户级：~/.claude/gate-checklists/spec-checklist.md  ← --update 更新
# 项目级：.claude/gate-checklists/spec-checklist.md      ← 独立拷贝，不被更新
```

修复：在用户级 gate-checklist 循环后追加项目级同步。

### 2. hooks（2026-07-31 发现）

```bash
# 用户级：~/.claude/hooks/stage-tracker.sh  ← --update 更新
# 项目级：.claude/hooks/stage-tracker.sh     ← 独立拷贝，不被更新
```

修复：在用户级 hooks 循环后追加项目级同步。

## 修复代码

```bash
# 模式（install.sh --update 分支内）
for item in "$SOURCE/<dir>/"*.<ext>; do
    [ -f "$item" ] && deploy_file "$item" "$CLAUDE_HOME/.claude/<dir>/$(basename "$item")"
done

# 项目级同步（如果项目有独立拷贝而非 symlink）
project_dir="$TARGET/.claude/<dir>"
if [ -d "$project_dir" ] && [ ! -L "$project_dir" ]; then
    for item in "$SOURCE/<dir>/"*.<ext>; do
        [ -f "$item" ] && deploy_file "$item" "$project_dir/$(basename "$item")"
    done
fi
```

## 预防

- 每次在 install.sh --update 分支中新增部署目标时，检查是否需要同时覆盖用户级和项目级两层
- --update 后用 diff 验证关键文件在两个路径一致
- 检测独立拷贝的命令：`stat -c "%i" ~/.claude/<dir>/<file>` vs `stat -c "%i" .claude/<dir>/<file>`，不同 inode = 独立拷贝 = 盲区

## 潜在其他盲区

当前 install.sh --update 还部署到以下用户级路径，但未检查项目级同步：
- `~/.claude/workflows/` — 如有项目级独立拷贝，同样盲区
- `~/.claude/skills/` — skills-cache 部署目标，按名称匹配

**Why:** 项目可能因历史原因（旧版 install.sh、手动操作）产生独立拷贝。Symlink 的项目不受影响。
**How to apply:** 修改 install.sh 部署逻辑时，每个用户级循环后补项目级同步块。--update 后跑 `diff -r ~/.claude/<dir> .claude/<dir>` 确认无遗漏。
