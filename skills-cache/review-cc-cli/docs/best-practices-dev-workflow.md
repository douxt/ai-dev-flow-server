# 开发流程固化：最佳实践与推荐方案

## 问题

AI 辅助开发中，流程靠人记、靠自觉调用，导致：
- 忽评忽不评，取决于当时想不想得起来
- 步骤顺序飘移（有时先写代码后补计划，有时反过来）
- 新人/新项目没有流程可循，从零摸索

目标：将「计划→PRD 评审→编码→代码评审→提交」固化为可复用、可发布、可跳过的工程流程。

## 方案对比

| 方案 | 固化程度 | 复杂度 | 可分发 | 灵活性 |
|------|---------|--------|--------|--------|
| A: Skills + Rubrics + CLAUDE.md 约定 | 低（靠自觉） | 最低 | ✅ 单 repo | 最高 |
| B: Skills + settings.json Hooks | 中（关键节点强制） | 低 | ✅ 单配置 | 高 |
| C: Archon YAML 工作流 | 高（DAG 强制执行） | 高（Docker + MCP） | ✅ 随仓库 | 中 |
| D: B + C 混合 | 高（核心钩子 + 复杂场景工作流） | 中-高 | ✅ | 高 |

## 推荐：方案 D（渐进式固化）

### 第一层：基础约束（settings.json hooks）

在 `~/.claude/settings.json` 中配置 hook，在关键节点自动触发 review：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "git commit",
        "hooks": [{
          "type": "command",
          "command": "claude -p \"运行 /review-cc-cli 检查当前改动...\" "
        }]
      }
    ]
  }
}
```

此层作用：git commit 前自动触发代码评审，不靠人记。

### 第二层：结构化流程（skills 串联）

将现有 skills 串成标准开发流水线：

```
/plan-prd <需求>           → 产出 PRD（to-prd skill）
    ↓
/review-cc-cli --rubric prd  → PRD 评审（prd.md rubric）
    ↓
/plan <PRD>                → 产出实现计划
    ↓
/review-cc-cli --rubric plan → 计划评审（plan.md rubric + worktree 检查）
    ↓
编码实现                     → 在 worktree 中开发
    ↓
/review-cc-cli [--loop]    → 代码评审（可循环收敛）
    ↓
git commit && git push     → 提交（hook 自动触发最终检查）
```

每个 `/review-cc-cli` 步骤可被用户跳过（`--quick`），灵活度保留。

### 第三层：复杂场景（Archon 工作流）

当项目规模大、多人协作、需要严格门禁时，将上述流程写成 Archon YAML 工作流：

```yaml
nodes:
  - id: prd
    prompt: "基于需求生成 PRD"
  - id: review-prd
    depends_on: [prd]
    prompt: "/review-cc-cli --rubric prd <prd文件>"
  - id: plan
    depends_on: [review-prd]
    prompt: "基于 PRD 创建实现计划（含 worktree 创建步骤）"
  - id: review-plan
    depends_on: [plan]
    prompt: "/review-cc-cli --rubric plan <plan文件>"
  - id: implement
    depends_on: [review-plan]
    loop:
      prompt: "读取计划，实现下一个任务"
      until: ALL_TASKS_COMPLETE
  - id: review-code
    depends_on: [implement]
    prompt: "/review-cc-cli --loop <改动范围>"
  - id: approve
    depends_on: [review-code]
    interactive: true
```

## 实施路径

1. **立即可做**：把 prd.md rubric + plan.md rubric + review-cc-cli SKILL.md 作为一套发布
2. **短期**：写一个安装脚本，一键部署 skills + rubrics + hooks 配置
3. **中期**：加 Archon 工作流 YAML 到 skills 仓库，用户可选启用
4. **长期**：做成 `npx skills add douxt/dev-workflow` 一键安装全套

## 核心原则

- **固化不僵化**：每一步都可跳过或简化（`--quick`/`--scope`/直接跳过）
- **渐进接入**：新人可以从单个 skill 用起，不用一次全装
- **工具无关**：流程描述不绑定具体工具名（worktree 不写成 `wt create`）
- **评审必带参考文档**：代码评审必须 `--with` 需求/设计文档

---

## 并行 vs 串行评审（调研报告）

### 背景

review-cc-cli 当前采用串行模式：单个 `claude -p` 子进程评审所有文件。业界已广泛实践并行多 agent 评审，以下做详细对比。

### 架构对比

| 维度 | 串行（当前） | 并行（多 agent） |
|------|------------|-----------------|
| 执行方式 | 单 `claude -p` 审全部 | N 个 agent 各审一个维度，同时跑 |
| 典型流程 | Read → Analyze → Output | Orchestrator → [Security\|Correctness\|Performance\|Style] → Verifier → Synthesize |
| 去重 | 不存在（单输出） | Verifier 交叉比对去重 + 合并 |
| bias 控制 | 无——首发现锚定后续 | 每个 agent 独立上下文，无交叉感染 |
| 速度 | 线性累加 | 3-5× 加速（并行瓶颈 = 最慢 agent） |
| 成本 | 1× token | 3-4× token（N 个 agent 各加载项目上下文） |

### 优缺点

#### 串行（当前方案）

| 优点 | 缺点 |
|------|------|
| 成本最低，1 次上下文加载 | 锚定偏差：第一个发现主导整个评审 |
| 零协调成本 | 确认偏差：找到一种解释就停止 |
| 无文件冲突 | 上下文退化：长评审质量下降 |
| 可 `/resume` 恢复会话 | 维度遗漏：倾向一种问题类型 |
| 最适合小 PR、单文件改动 | agentic laziness：审到一半就收工 |

#### 并行（多 agent）

| 优点 | 缺点 |
|------|------|
| 维度隔离：安全/性能/正确性独立审 | 成本 3-4×（每个 agent 独立加载上下文） |
| 对抗验证：verifier 交叉检查降低误报 | 协调成本：spawn prompt + 结果合并 |
| Anthropic 内部数据：误报 <1%，84% 大 PR 有发现 | 同文件编辑冲突（只读评审无此问题） |
| 3-5× 加速（并行瓶颈 = 最慢 agent） | 最大实用 agent 数 3-5，超过不划算 |
| 消除三种失败模式：懒惰/自偏好/目标漂移 | 会话不可恢复（agent team 无 /resume） |

### 业界实践数据

| 来源 | 方案 | 关键数据 |
|------|------|---------|
| Anthropic 内部 | Explorer×N → Verifier → Synthesize | 16%→54% PR 获评审评论，<1% 误报，$15-25/次 |
| `/ultrareview` | 并行 explorer + critic 交叉检查 | 发现 bugs 和确认 bugs 是不同任务，分开做 |
| CodeX-Verify | 4 agent（security/correctness/perf/maintainability） | +28.7pp 单 agent，+39.7pp 多 agent 优势 |
| PAR/MMAR | 2 同模型竞争 / 多模型交叉批判 | 最坏 severity 决胜负；多模型互审防幻觉 |
| hamelsmu 插件 | 最多 4 并行 Codex agent | diff + holistic + 条件激活领域 agent |

### 对 review-cc-cli 的建议

**当前阶段不建议大改。** 原因：

1. review-cc-cli 定位是轻量、低成本的即时评审工具
2. `--loop` 已提供多轮收敛，部分弥补了单 agent 盲区
3. 并行大幅增加 token 成本（3-4×），与「人人都能用」的定位冲突
4. 用户可手动并行：开两个终端各跑 `/review-cc-cli` 不同维度

**建议的渐进路径：**

| 阶段 | 做法 | 收益 |
|------|------|------|
| 短期 | 加 `--parallel <维度列表>` 参数 | 可选启用，不改默认行为 |
| — | 维度：security/correctness/performance/style | 每个维度独立 agent + 独立 rubric |
| — | 并行 agent 输出 → 主进程去重合并 | 减少 false positive |
| 中期 | 加 `--verify` 参数（对抗验证） | 学 Anthropic verifier 模式 |
| 长期 | 支持 Claude Code Workflow/Agent Teams API | 原生并行，自动管理 worktree |

### 推荐的最优并行模式（供参考）

```
/review-cc-cli --parallel <改动范围>
        │
   Orchestrator（分析 diff，选择维度）
        │
   ┌────┼────┬────┐
   ▼    ▼    ▼    ▼
  Sec  Corr Perf Style    ← 4 个 claude -p 并行，各带独立 rubric
   │    │    │    │
   └────┼────┼────┘
        ▼
   Verifier（交叉检查，去重，合并）
        │
        ▼
   最终报告（按 severity 排序，标注发现 agent）
```

此模式不改变默认行为，用户加 `--parallel` 才启用。
