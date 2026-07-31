---
name: session-lessons-flow-gate-wiring-20260731
description: 本会话 10 个 commit——hook 提醒过期修复 + C0.5 测试发现 + test-gate.sh + 项目级同步盲区
created: 2026-07-31
source: manual
metadata:
  type: project
  related:
    - hook-reminder-staleness-causes-gate-skip
    - install-sh-project-level-sync-blindspot
    - gate-two-axis-architecture
---

# 本会话成果：门禁流程化——从"文档有"到"AI 真执行"

## 核心问题

质量门禁（C0-C7/G0/S13/R7/决策树）在 checklist 文档中已定义完整，但 AI 不执行——因为 hook 提醒内容是旧的、编号是过期的，AI 按提醒走自然漏检。

## 改动清单（10 个 commit，7 个文件）

| Commit | 文件 | 内容 |
|--------|------|------|
| `fix(hooks)` | stage-tracker.sh | 3 处提醒补全：S1-S10→S1-S13 + 决策树 + S11/S13 重点 |
| `fix(hooks)` | stage-tracker.sh | tickets:done 加决策树入口 + C7/R7 + 4条grep |
| `fix(hooks)` | stage-tracker.sh | tdd:done 加 G0 完整流程 + R7 分层一致性 |
| `fix(hooks)` | workflow-gate.sh | 注入文本同步：S1-S10→S1-S13 + 决策树 + C7/G0 |
| `feat(install)` | install.sh + RULES.md.test-quality | ADR 部署 + RULES.md 标记区间追加 |
| `feat(gate)` | test-checklist.md + stage-tracker.sh | C0.5 测试实际执行验证（防 PASS(0) 真空通过）|
| `feat(gate)` | test-checklist.md + test-gate.sh + install.sh | P1：C1 执行计数 + C0.5 RTK 绕过 + 通用 test-gate.sh |
| `fix(hooks)` | stage-tracker.sh | tickets:done 引用 test-gate.sh 替代手动 grep 列表 |
| `fix(install)` | install.sh | 项目级 hooks 同步（gate-checklist 同款盲区第二次踩坑）|
| `fix(test-gate)` | test-gate.sh | P0: Total 解析 / P1: config 子目录 / P2: .bak 排除 |

## 关键经验教训

### 1. Hook 提醒是门禁执行的关键路径

门禁体系的约束链路：
```
workflow-gate（首次拦截）→ stage-tracker（阶段切换提醒）→ AI 按提醒执行 → checklist
```

hook 提醒不是"辅助文档"——它是 AI 在决策时刻看到门禁编号的**唯一入口**。提醒过期 = 门禁不存在。

**预防**：每次新增门禁，grep hook 文件确认三处提醒（spec:done / tickets:done / tdd:done）是否覆盖。

### 2. 项目级 .claude/ 独立拷贝是系统性盲区

install.sh --update 只部署到 `$CLAUDE_HOME/.claude/`（用户级）。部分项目的 `.claude/` 下有独立文件（非 symlink），这些拷贝从不更新。已发现两次：
- gate-checklists（S13 不到达 UMES3）
- hooks（stage-tracker 新版不到达 UMES3）

**预防**：每个 install.sh 部署循环后加项目级同步块。详见 [[install-sh-project-level-sync-blindspot]]。

### 3. PASS(0) 是比断言弱更根本的漏洞

"0/0=100% 失败"是真空通过——所有 C0-C7 + G0 门禁都用 grep/静态分析，没有一条检查"测试真的执行了"。C0.5 一行 `--list | grep Total:` 堵住了这个洞。

**预防**：门禁体系中每个"全部通过/全部失败"的判断，都必须先确认 N > 0。

### 4. 现场验证发现的问题文档设计阶段发现不了

test-gate.sh 的三个 bug：
- `len(suites)` = 文件数不是测试数（空文件可绕过）
- config 文件在子目录时发现不到
- grep 命中 .bak 备份文件产生假阳性

全部是 UME3 实际跑脚本时发现的。文档里看不出来。

**预防**：通用脚本写好必须找实际项目跑回归验证，不能只靠 review。

### 5. 安装/部署机制的回归风险高

本会话 merge 操作两次失败（在 worktree 内运行 `git merge` 是 no-op）。install.sh 在 source repo dirty 时 --update 失败，需要 stash。

**Why:** worktree 隔离 + 主仓库保护虽然安全，但操作流程复杂，merge 方向容易搞反。
**How to apply:** 从主仓库目录合并（非 worktree），合并前确认 source repo clean。在主仓库目录记录 merge checklist。
