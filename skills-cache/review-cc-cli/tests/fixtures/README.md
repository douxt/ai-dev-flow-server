# 并行评审验收 fixture

`fixture-bugs.js` 是一个植入已知问题的测试文件，用于验证 `--parallel` 管道正确性。

## 植入问题清单

### 真实 bug（预期 verifier confirmed）

| # | 维度 | 行号 | 严重度 | 描述 |
|---|------|------|--------|------|
| 1 | correctness | 22 | high | `userId` 未做 null 检查直接拼入 SQL |
| 2 | correctness | 35 | high | `for` 循环 off-by-one：`<=` 应为 `<` |
| 3 | correctness | 51 | medium | `== 0` 类型强制，应用 `===` |
| 4 | security | 47 | high | API 密钥硬编码 `sk-abc123xyz456` |
| 5 | security | 22 | high | SQL 注入 — 字符串拼接 `+ userId`（与 #1 同行） |
| 6 | performance | 36 | medium | N+1 查询 — 循环内逐条查 `order_items` |
| 7 | style | 56 | low | 魔法数字 `3`，应命名常量 |
| 8 | performance | 61 | medium | `setInterval` 创建后无 `clearInterval` |
| 9 | style | 69 | low | `legacyNormalize` 函数未被调用（死代码） |
| 10 | correctness | 95 | high | `reportId` 未做 null 检查（与 #1 同根因） |

> 行号已于 2026-08-28 逐行核对 fixture-bugs.js 实码（P5 冒烟中发现原表自建立起即与文件漂移）。

### 语义重复

- **BUG #1**（行 22）与 **BUG #10**（行 95）：同一 null-check 遗漏模式，不同位置
  - Stage 1 不碰撞（不同行号）
  - Stage 2 应形成候选对（同文件 + desc Jaccard > 0.3）
  - Stage 3 verifier 应判定为同一根因 → 交叉引用标注

### False positive（预期 verifier marked false_positive）

| # | 行号 | 内容 | 排除理由 |
|---|------|------|---------|
| F1 | 28 | `user == null` | `== null` 是 JS 惯用法，同时检查 null/undefined |
| F2 | 79 | 注释掉的 `oldDiscount` | 有明确 KEEP-FOR-REFERENCE 标记，非死代码 |
| F3 | 84 | `const sq = x => x * x` | 短箭头函数中单字母变量可接受 |

## 验收标准

### 三级去重

1. **Stage 1**（精确碰撞）：#1 与 #5 同在行 22，若两维度分别报出则应合并为一条（severity=high）；实测中单 agent 已合并报告则无碰撞可并，属正常
2. **Stage 2**（候选配对）：BUG #1 和 #10 应形成候选对（同文件 + 相似 desc）
3. **Stage 3**（LLM 判重）：verifier 应合并或交叉引用 #1 和 #10

### Verifier

- 10 条确认 → ≤ 15 全验
- F1-F3 标记 false_positive，各附排除理由
- BUG #1-#10 标记 confirmed（≥ 8 条）
- 无新增发现（verifier 不生成新 finding）

### 维度覆盖

| 维度 | 预期发现 |
|------|---------|
| correctness | #1, #2, #3, #10 |
| security | #4, #5 |
| performance | #6, #8 |
| style | #7, #9 |

## 回归测试

串行 `/review-cc-cli` 与 `--parallel` 对同一 fixture 的 confirmed 数量应一致（≥ 8 条）。

## Provider 模式验收（--provider / 自然语言）

前置：`~/.claude/review-providers.json` 含 deepseek 与 ali 两个 profile（参照 config/review-providers.example.json），对应 token_file 已放置且非空。

| # | 操作 | 预期 |
|---|------|------|
| P1 | `/review-cc-cli --provider deepseek --scope tests/fixtures/fixture-bugs.js` | 子进程返回 JSON 的 `model` 字段 == profile 声明的模型；启动前回显「已解析 provider=..., model=..., base_url=..., 来源=显式参数」 |
| P2 | 跑完 P1 后检查本会话 transcript 与 `~/.claude/logs/file-audit.jsonl` | grep 密钥明文 0 命中；命令文本仅含 `$(cat <token_file>)` 形式 |
| P3 | `/review-cc-cli --provider not-exist` | 报错列出全部可用 provider 名；不启动任何 claude -p 子进程；不降级为对话内评审 |
| P4 | 不带 --provider 且（default=null **或 profile 文件根本不存在**） | 命令与旧版逐字一致（无 env 前缀）且无报错——provider 体系对零配置用户完全透明 |
| P5 | `/review-cc-cli --provider deepseek --parallel --scope tests/fixtures/fixture-bugs.js` | 全部维度 agent + verifier 的 model 字段一致；confirmed 数量与串行 P1 一致（≥ 8） |
| P6 | `/review-cc-cli --provider ali --model "qwen3.8-max[1m]"` | 显式 --model 覆盖 profile.model；模型名含 `[1m]` 不被 shell 破坏 |
| P7 | 自然语言：`用 deepseek 评审这次改动` | 命中 alias → 等效 --provider deepseek，回显来源=自然语言 |
| P8 | 自然语言：`用 ds 审 flash 模型` | provider=deepseek + 模型叠加匹配到该端点现行 flash 档（名字随上游漂移，2026-09-15 实测 = `deepseek-flash`；匹配按"包含 flash 的端点支持名"判定，不硬编码全名），回显两者 |
| P9 | 歧义输入（alias 同时命中 2 个 provider） | 停下列出候选询问，不启动子进程 |
| P10 | token_file 不存在或为空 | 硬失败报错，指明缺失文件路径，不回退继承 env |

install.sh 幂等：连续执行两次，第二次不覆盖已存在的 `~/.claude/review-providers.json`，`~/.claude/secrets/` 存在且权限 700。

## Hetero 模式验收（--hetero 异构双层）

前置：deepseek profile 含 `model` + `pack_model`；`--hetero` 默认超时 900s，外层一律 run_in_background。

| # | 操作 | 预期 |
|---|------|------|
| H1 | qwen 会话内裸 `/review-cc-cli --hetero --scope fixture`（无 provider） | lead/pack 解析为 qwen max/flash 档，回显来源=网关别名解析；modelUsage 键集恰 = {lead, pack}（无泄漏） |
| H2 | `--hetero --provider deepseek` | lead/pack = profile 声明值（上游改名后以实值为准，2026-09-15 = 双 `deepseek-flash` 同质 ack 路径）；modelUsage 键集 == {lead}（同质继续）或 == {lead, pack}（异构），无计划外第三键（混入即整单失败） |
| H3 | `--hetero --provider deepseek --pack "<lead名>[1m]"` | 显式覆盖生效、`[1m]` 端点可解析；同质判定按归一化规则（剥 `[1m]` 后与 lead 相等）→ 查 ack：有 ack 不警告仅回显标注，无 ack 走 H8 警告路径（F-5 联动） |
| H4 | 自然语言「用 deepseek pro 带 flash 评审」（含 provider 线索+模式词） | 解析 hetero+provider+lead/pack 全中，回显来源=自然语言；若裸说「pro带flash」同时命中多 profile → 按歧义询问 |
| H5 | `--hetero --parallel` / `--hetero --loop` | 报错不启动任何子进程 |
| H6 | 对 fixture-bugs.js 跑 H2 全流程 | merged 命中答案卷真实 bug ≥8（2026-08-28 实测基线 9/9）；F1/F2/F3 不出现在 merged 或指挥官明示拒绝理由（hetero 管线无独立 verifier，FP 排除属指挥官职责）；聚合 JSON 含 5 个来源键；modelUsage 各键 inputTokens>0 |
| H7 | 权限双探针（均已实测 2026-08-28）：(a) 无防线时子 agent 写**不被拦截**——规格据此要求士兵 prompt 硬性植入只读句；(b) 有防线时诱导指挥官派写任务 → 拒绝，`/tmp/hetero-probe2.txt` 不存在 | 防线为 prompt 软约束（无钩子兜底），规格与验收如实声明，不写成硬拦截 |
| H8 | profile 缺 pack_model + `--hetero --provider deepseek` | pack:=lead，输出同质警告并询问，不静默、不跨端点回退别名 |
| H9 | 双基线回归：**A** 无 provider 无 hetero 的旧路径（裸串行/`--parallel`/`--loop`）模板 | 与 main@78dc294 逐字一致（零配置透明铁律，加固不惊扰） |
| H9b | **B** provider/hetero 激活路径模板 | 基线 main@5eaf85d，目标态含 `--setting-sources user` + `< /dev/null` 且**全部调用点无遗漏**（串行④完整形态/Loop④/Parallel③各 agent+verifier/hetero 指挥官+预检，2026-09-15 ADR-003 有意变更非回归） |
| H10 | 任一 hetero 跑完后审计：聚合 JSON、外层 result、本会话 transcript、file-audit.jsonl | grep 密钥明文 0 命中（命令文本仅 `$(cat <token_file>)` 形式）；新增——核对 result 中无子代理转述的 env 值（防被注入士兵 echo env 经聚合 JSON 外泄） |

## 环境故障注入验收（加固回归）

J↔验收锚点：J1=运行时 profile 止血（Phase 0，非本文件）；J2=H9b 模板全调用点核对 + F-2 smoke；J3=F-2；J4=F-1a/F-1b；J5=H2/H6 端到端；J6=F-4；J7=回流零漂移核对（维护会话执行记录）。

> 通道纪律：以下所有被测模板改动均在 douxt/skills 源仓 worktree 完成后回流，**禁止直接编辑 `~/.claude/skills/review-cc-cli`**（安装副本是分发产物，私改=漂移源头；安装目录不做 git init）。

前置：注入类操作用 python 读写保行尾（CRLF 坑），改前先 `cp .bak`，测后**立即还原**并 `diff` 核对 + `git -C <项目> status` 确认无残留。

| # | 注入 | 预期 |
|---|------|------|
| F-1a | 沙箱目录（非真实项目）`.claude/settings.local.json` env 段塞 `"CLAUDE_CODE_SUBAGENT_MODEL": "nonexistent-model-xyz"` → 跑标准模板（含 `--setting-sources user`）hetero | 项目层切断生效：预检②通过、兵正常建立（对照基准） |
| F-1b | 同沙箱**去掉** `--setting-sources user` 复现旧链路 | 预检② env 污染哨兵报警（echo 比对 ≠ 注入值，实测 T2 现象）；或兵全灭被 F-3 路径标注——两者必居其一，不接受静默成功 |
| F-2 | profile `model` 改 `deepseek-v4.1-flash`（已死名）→ 跑 provider/hetero | 预检① smoke 400 + 回显端点 supported 列表；**不启动正式评审**；经确认后回写 profile + 刷新 `last_verified` |
| F-3 | 复用 F-1 变体（`--setting-sources` 去掉 + nonexistent 兵模型）使子代理全灭 | 指挥官禁代跑：维度全部入 missing_dimensions；外层判 `BLOCKED(独立层未建立)`；`usage.inputTokens` 规模 ≈ 单层量级 → 账本规模断言触发降格；报告不得以"独立评审完成"口径流转 |
| F-4 | 零配置：删 profile 文件（或移走）→ 裸 `/review-cc-cli` 与 `--parallel` | 完全静默旧行为（J6）：无预检、无报错、不提示；仅显式 `--provider`/hetero-profile 链请求时硬失败 |
| F-5a | profile 构造 lead==pack（归一后）且**无** homogeneous_ack → 跑 hetero | 同质警告出现并询问，不静默 |
| F-5b | 同配置补上 `homogeneous_ack:{date,reason}` → 再跑 | 不警告，回显标注「同质（ack <date>）」；删除 ack 字段复跑 → 警告恢复（机制可逆） |
