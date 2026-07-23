# v2.1 → v3.0 迁移指南

## 概述

v3.0 采用 Skill-Harness 分离架构，将原 9-Gate 自研 skill 替换为 Matt Pocock v1.1 五命令体系。`install.sh --update` 自动处理大部分迁移工作。

## 自动迁移

```bash
cd /path/to/ai-dev-flow-server
git pull
bash install.sh <项目路径> --update
```

`--update` 自动执行：
1. 检测旧 `.gate-state` → 调用 `migrate-gate-state.sh`
2. 备份旧 gate-state 到 `.gate-state.v2.bak`
3. 生成新 `.devflow/stage`（5 阶段）
4. 退役旧 skill → `.archived/`
5. 安装新 Matt Pocock v1.1 skill
6. 安装新 hook（workflow-gate + stage-tracker + suggest-rules）
7. 更新 CLAUDE.md 模板（含路由规则 + 引导词 + 安全红线）
8. 追加 trace/migration 事件到 `.devflow/trace.jsonl`

## Gate 映射

| v2.1 (9 Gate) | v3.0 (5 Stage) | 说明 |
|:---:|:---:|------|
| gate-1 (grill) | explore | 需求澄清 |
| gate-2 (spec) | spec | 规格编写 |
| gate-3+4 (issues) | tickets | 工单拆分 |
| gate-5+6 (implement) | implement | 实现+审查 |
| gate-7+8 (merge+retro) | done | PR 合入+复盘 |

迁移脚本取**最后通过的 gate** 映射到对应阶段。例如 gate-4 passed → `tickets:done`。

## 手动回滚

```bash
# 恢复旧 gate-state
cp .gate-state.v2.bak .gate-state

# 删除新 stage
rm .devflow/stage

# 恢复旧 skill（如需）
cp -r ~/.claude/skills/.archived/gate-* ~/.claude/skills/
```

## 文件变更对照

| 旧文件 | 新文件 | 操作 |
|--------|--------|------|
| `.gate-state` | `.devflow/stage` | 自动迁移 |
| `.gate-state` | `.gate-state.v2.bak` | 自动备份 |
| `~/.claude/skills/gate-*/` | `~/.claude/skills/.archived/gate-*/` | 退役备份 |
| `~/.claude/gate-checklists/` (6 份) | `~/.claude/gate-checklists/` (4 份) | 自动替换 |
| `~/.claude/workflows/gate-*.js` (9 个) | 不再需要 | 保留不删 |
| — | `.devflow/trace.jsonl` | 新增 |
| — | `.devflow/metrics.json` | 新增 |
| — | `.devflow/locks/` | 新增 |
| — | `.devflow/rule-suggestions.md` | 新增 |
| — | `.devflow/scripts/trace.sh` | 新增 |
| — | `.devflow/scripts/metrics.py` | 新增 |

## 兼容性说明

- **ticket 格式**：v3.0 新增字段（safety、AC 级别）为可选，旧 ticket 继续工作
- **AFK 管线**：dispatch.sh + reconciler.sh 向后兼容，无 breaking change
- **constitution 检查**：新增 8 项检查中，只有 `safety` 命中时标记 `⚠️ HUMAN_REVIEW_REQUIRED`，其余为 warning
- **逃生机制**：`~/.claude/.emergency-bypass` 新增，不影响现有配置
