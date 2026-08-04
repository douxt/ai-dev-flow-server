# ADR-009: 文件级阶段锁定——GREEN 阶段禁改测试文件

## 状态：已采纳

## 日期：2026-08-04

## 背景

5.7 `stage-gate-block.sh` 落地了四层硬化模型第一层：阶段 < `tdd:done` 时禁写实现源文件。但 `tdd:done` 之后所有文件全放行——GREEN 阶段 Agent 可以自由修改测试文件（削弱断言、删除失败测试），G1 反作弊规则 #1"禁止修改测试文件"仅以 advisory 提示存在，无可执行阻断。

5.8 将 G1 规则 #1 升级为 PreToolUse exit 2 硬阻断，完成四层硬化模型第二层。

## 决策

### 1. GREEN 窗口信号

使用双重信号判断"正在 GREEN 阶段"：

```
in_green_window = (.devflow/stage 存在 AND stage 索引 >= tdd:done)
                  AND (git log -1 --format=%s 含 "TDD: RED")
```

- **stage 文件**：保证 DevFlow 上下文（无 .devflow 的项目不受影响）
- **git log**：提供精确相位——GREEN commit 后最后 commit 不再是 RED，窗口自动关闭，多 ticket 自然流转

仅用 stage 文件不够——它不回归，无法区分"刚做完 RED 正在实现"和"已完成 ticket-1 要开始 ticket-2 /tdd"。

### 2. 断言以最终形式在 /tdd 写入

废除现有的"RED→GREEN 断言切换"流程（RED 断言 `code=1` → GREEN 重写为 `code=0`）。

标准化为：/tdd 阶段直接写最终业务行为断言，RED 由 stub 抛出 `NotImplementedError`/HTTP 501 保证（C2 认可的 RED 失败原因）。GREEN 阶段零测试文件编辑。

**理由**：断言切换要求 GREEN 阶段修改测试——与"禁止修改测试文件"直接冲突，无法同时成立。且 stub 异常已经提供真实的 RED 信号，断言不需要两套。

### 3. 逃生协议

1. **自然路径（推荐）**：GREEN commit → 窗口自动关闭 → 可修改测试
2. **TEST_BUG 协议**：测试有 bug → 停止，输出 `TEST_BUG: <file>:<line> — <原因>`，等人工判断
3. **多 ticket 流转**：ticket-1 GREEN commit 后窗口关闭 → 写 ticket-2 测试 → ticket-2 RED commit → 窗口重新激活

## 后果

### 正面

- G1 规则 #1 从"说了但没执行"变为"不可绕过"
- GREEN 阶段 Agent 无法削弱测试来提高通过率
- 多 ticket 场景自然支持（GREEN commit 自动解锁）
- 无额外状态文件——git log 即可判断

### 负面

- **Bash 绕过向量**：heredoc/tee/sed -i 绕过 Edit|Write matcher。green-gate.sh G2.1 + audit-log 为后手，不在此迭代解决
- **历史改写**：`git commit --amend` 移除 RED commit → 锁静默关闭。CLAUDE.md 已禁止 amend，bash-firewall.sh 是现有控制面
- **测试配置**：vitest.config.ts/playwright.config.ts 分类为源文件（`.ts`），GREEN 阶段允许修改——可能被用于绕过（在 config 中 disable 测试）
- **E2E test.fail() 标记**：若使用 Playwright `test.fail()` 作为预期失败标记，去除标记属于测试编辑，被 5.8 阻断。建议用真 RED（功能不存在→404/timeout）

## 拒绝的方案

### 方案 A：断言切换窗口豁免

在 GREEN 窗口中为"断言切换"开一个时间窗口（如 RED commit 后 5 分钟内允许改测试）。

**拒绝理由**：不可执行。强化断言（`toBeVisible` → `toBe(5)`）和弱化断言（`toBe(5)` → `toBeGreaterThan(0)`）在文件级别无法区分。任何豁免都将成为 Agent 的绕过路径。

### 方案 B：仅用 git log 信号

去掉 stage 文件判断，仅依赖 `git log -1 | grep "TDD: RED"`。

**拒绝理由**：丢失 5.7 的"无 .devflow → 放行"契约。误含"TDD: RED"的非 DevFlow 项目会被误锁。双重信号成本为零（一次 grep），保留安全边际。

### 方案 C：新增 stage 值 `tdd:red` / `tdd:green`

在 stage 文件中增加更细粒度的状态值。

**拒绝理由**：需要 stage-tracker 写新值，破坏现有六阶段兼容性。且 git log 已经提供等价信息——commit 就是最好的状态机。不引入新的状态管理复杂度。
