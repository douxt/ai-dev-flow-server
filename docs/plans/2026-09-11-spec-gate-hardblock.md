# Spec 出口门禁（spec-gate）实施计划 v2 —— 2026-09-11

## Context

来源反馈：`/home/dou/projects/UMES3/docs/feedback/spec-gate-hardblock-feedback-20260911.md`。
问题：阶段机只门控源码写入时机，`.md` 扩展名被 [stage-gate-block.sh:63](config-templates/default/hooks/stage-gate-block.sh#L63) 全仓豁免；spec 产物质量（合规表自查）零机器防线，UMES3 三轮不合规 spec 零报警。

v1→v2 经 4 路代理评审 + 主会话逐项实证，确认的关键翻案（全部实测，非转述）：
1. **warn 通道**：PostToolUse exit 0 的 stderr 模型不可见（官方语义），必须走 stdout JSON `hookSpecificOutput.additionalContext`（stderr 留空）——v1 的 warn 设计是死代码
2. **mtime 基线无效**：PostToolUse 触发于写入之后，文件 mtime 必为"刚刚"，豁免逻辑上覆盖不到它要防的场景；且 git checkout 重置 mtime、worktree 缺未跟踪 marker。改**安装时路径基线清单**
3. **旧 checker 实测**：`check_constitution.py --spec x` → `{"file":"--spec","error":"文件不存在"}` rc=1（`--spec` 被当路径，L460 `path=sys.argv[1]`），未回灌项目的钩子会把崩溃误读为缺项 → 全量误拦。UMES3 的 `.devflow/scripts/check_constitution.py` 尚处 M 未提交态，版本 skew 是现实而非假想
4. **硬软分级冲突**：[spec-checklist.md:27](gate-checklists/spec-checklist.md) 明文"S1-S5+S10-S13 必过，S6-S9 advisory"——v1"合规表任一❌硬拦"与现行口径打架
5. **轴线归属错误**：ADR-006 原则 1 明文"新门禁必须明确归轴"，spec-gate 五项全为结构校验 = **形式正确性轴**（从测试扩展到 spec 产物），非 v1 写的"有效性轴"
6. **L253 恒假 bug 属实但降级**：`scan_ac_levels` 返回裸捕获组 `"auto"`，L253 比较 `"[auto]"` 永假 → 恒 warning（不影响退出码）。--spec 仅做存在性匹配可避开，同批顺带修
7. `frontmatter` 为模块级 import（L21-27），目标机缺包则 --spec 整体崩——--spec 不需要 frontmatter，须懒导入
8. 计数口径需对账统一：宪法实为"11 规则 + P1-P4 + H1-H3 + VL = 合规表 17 行"，"13 项"是反馈的混乱口径，checklist 是 S1-S13 另一套编号——回执与文档必须映射表定死

## 工作流约束

- 首步 `wt create spec-gate`；分 Phase commit；合并回 main 走授权（`CLAUDE_MERGE_AUTHORIZED=1`）
- 回灌 UMES3 的 `--update` 以**合并后的 main**为 SOURCE（install.sh 有 git pull 副作用坑）
- `--update` 注入钩子后**旧会话不加载**（hook-config-change-requires-session-restart），观察期计时从新会话起

## Phase 1：check_constitution.py `--spec` 模式

改 `scripts/check_constitution.py`：
- 新分支插在 L460 `path = sys.argv[1]` 之前：`if "--spec" in sys.argv`，用法 `--spec <file.md> [--json]`
- `import frontmatter` 从模块级改为 ticket 路径内懒导入（--spec 不依赖）
- 校验项与**分级**（对齐 spec-checklist 口径，映射表写进代码注释与回执）：
  - **硬**（exit 1）：①`## Spec 质量宪法合规表` 节存在 ②合规表节内 S1-S5、S10-S13 对应行状态列含 `❌`（判定锚定：节内表格行第 3 列，节外不判）③Risks 节存在 ④AC 存在（复用 L111 正则失败则 L114 备选，**仅存在性，不消费捕获组**）
  - **advisory**（exit 0 + `--json` 输出 `advisories:[...]`）：Risks 条目 <5（`- ` 行计数）、S6-S9 行含 ❌、验证等级标注缺失
- 独立 commit 顺带修 L253：`"[auto]" in` → `"auto" in`
- trace 事件 `constitution.spec` 在成功路径记录（崩溃路径由钩子侧记，见 Phase 2）
- ticket 模式行为零改动（dispatch.sh:157 路径不碰）
- **Phase 内验证**：`python3 scripts/check_constitution.py --spec templates/spec-template.md` → rc 0；构造缺表 spec → rc 1 列缺项；`--spec` 对不存在的文件 → 错误 JSON rc 2（区分于业务失败的 rc 1，钩子据此降级）

## Phase 2：spec-gate.sh 钩子 + 部署 + 测试（测试并入本 Phase）

新 `config-templates/default/hooks/spec-gate.sh`，骨架照抄 stage-tracker.sh（stdin jq、`WORKSPACE="${WORKSPACE:-${WS_CWD:-$(pwd)}}"`、`[ -d "$WORKSPACE/.devflow" ] || exit 0`）：

**触发判定**（全部不满足 → exit 0 且写 trace 心跳事件 `spec-gate.skip <reason>`）：
- tool_input `.file_path` 存在且在 WORKSPACE 之下、匹配 `docs/specs/**/*.md`（递归）
- 不在基线清单 `.devflow/spec-gate-baseline`（安装时由 install.sh 枚举存量 `docs/specs/*.md` 相对路径生成；存量旧 spec 永久豁免，**不依赖 mtime/时钟**）
- 不在人工豁免清单 `.devflow/spec-gate-exclude`（每行一路径；豁免也写 trace 事件，可审计）
- 钩子不做文件内 skip 注释豁免（模型可自行贴注释消音 = 门禁可被模型关掉，弃用 v1 的 `<!-- spec-gate: skip -->`）

**执行**：调 `$WORKSPACE/.devflow/scripts/check_constitution.py --spec <file> --json`
- 钩子先探测：checker 不存在或无 `--spec` 能力（rc≥2 / 输出非预期 JSON 形状）→ **静默放行 + trace 事件 `spec-gate.degraded`**，绝不把崩溃解读为缺项
- 通过 → exit 0 + trace 心跳 `spec-gate.pass`

**warn 模式**（`.devflow/spec-gate-mode` 缺省 warn）：
- stdout 输出 `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"spec 缺项：…（对照 spec-checklist S#）"}}`，**stderr 保持空**，exit 0
- 每 session 每文件封顶报 3 次（`.devflow/.spec-gate-warned` 台账：`date|session_id|rel_path` 行，按日轮换防增长；不按缺项指纹去重——增量补写缺项集每变即"新报"，指纹去重防不住且会放过最终态）

**block 模式**：exit 2 + stderr 缺项清单（PostToolUse 语义 = 回灌模型，每次编辑都报，写入不回撤）；连续阻断计数 ≥3 升级提示"人工介入，勿死循环"（抄 stage-tracker `.verify-blocks` 现成模式）

**注册**：`config-templates/default/settings.json` PostToolUse 加 `{"matcher":"Edit|Write","hooks":[{"type":"command","command":"__CLAUDE_HOME__/hooks/spec-gate.sh","timeout":3000}]}`（组内惯例带 timeout）；目标项目经 merge-settings.py basename 去重注入 settings.local.json。⚠️ 实施时核对注入后**无双注册**（settings.json 与 settings.local.json 各一份 → 双跑，dual-config 坑）
- `install.sh`：部署 spec-gate 时生成 `.devflow/spec-gate-baseline` + `.devflow/spec-gate-mode`（缺省 warn）；`selftest_hooks()` 加两条：**正路径断言**（沙箱造 .devflow+基线+无合规表 spec → stdout 含 additionalContext）与降级断言（无 checker → rc 0）；新钩子自动被 L615/L627/L981 三个 glob 循环拾取，记得 chmod +x（126 与放行同形坑）

**bats**：新 `tests/hooks/spec-gate.bats`（run_tests.sh 自动收集，ubuntu-only），用例：反向(warn 出缺项/block exit 2)、正向、零干扰(references/、`docs/specs/x.txt`、无 .devflow、file_path 在 WORKSPACE 外)、基线豁免(存量路径静默)、exclude 静默、台账封顶(第 4 次同 session 不报)、checker 缺失/崩溃降级、缺 frontmatter 包时 --spec 可用（模拟：`python3 -c` 探针跳过）、双钩子串联共存（与 stage-gate-block 同沙箱各 rc 互不污染）、`--spec` 分支不破坏 ticket CLI 冒烟（现无 check_constitution 专项测试——评审证实，本文件兼补 ticket 冒烟 2 条）

## Phase 3：文档落地 + 回执 + 记忆

1. 本计划 → `docs/plans/2026-09-11-spec-gate-hardblock.md`
2. 回执 → `docs/feedback/spec-gate-hardblock-response-20260911.md`：逐条回应 §3（采纳+8 项修正及实证依据，含 v1 曾犯的 stderr 死代码错误以示同坑已填）；明确边界承接：§3.2/§3.3 缓行待台账、Bash 旁路（`cat>`/`mv`/`tee` 进 docs/specs 不经 Edit|Write matcher）为本版已知限制、口径对账表（17 行合规表 ↔ S1-S13 ↔ 检查项）
3. 修订 `gate-checklists/spec-checklist.md`：加"机器校验分层"节（哪些项由 spec-gate 硬拦/advisory）；⚠️ 项目级独立拷贝不被 --update 同步是已知盲区（install-sh-gate-checklist-sync-gap），UMES3 侧核对 md5
4. `docs/README.md` 索引同步（docs/feedback/ 若为本仓新目录）+ `CHANGELOG.md` 条目
5. 全局记忆 2 条：①§0 接线教训（评估接线必须 dump 全部 settings*.json）②PostToolUse warn 通道语义（exit 0 stderr 模型不可见，须 additionalContext；先 grep 合并组，可考虑并入 claude-code-hook-dev-pitfalls）
6. ADR `docs/decisions/00X-spec-gate-formal-axis.md`：归轴论证（形式正确性轴从测试产物扩至 spec 产物）、warn/block 两段制、基线清单 vs mtime 的取舍、拒绝 quack 判定的理由（新 spec 恰以"缺合规表"为拦截目标，含表才拦 = 门禁自杀）

## 观察期 → block 切换 → 回滚

- **切换判据（量化，用户执行）**：≥5 个不同 spec 文件的 warn 事件、trace.jsonl 中 `spec-gate.pass/degraded` 心跳存在（区分"无误拦"与"没运行"）、人工逐条回放标注 0 误拦；样本不足则延长，不默认切换；`.spec-gate-warned` 中 to-spec 首轮预期噪声（社区模板不含合规表）与真误拦分开统计
- **回滚**：`jq` 按 basename 删 `~/.claude/settings.local.json` hooks 中 spec-gate 条目 + 删钩子文件；`.devflow/spec-gate-mode` 改 `off` 值可作软开关（钩子读到 off → exit 0 静默，保留心跳）——软开关写进钩子第一版
- 性能验收：开发机（WSL）与 NAS 各 10 次取 p95 < 200ms；python3 ~10ms 冷启动已实测无虞，NAS 慢盘场景不达标则降级纯 bash grep（接受与 checker 双源，漂移风险记 ADR）

## 不做

- 不改 skills-cache/to-spec（用户定案：社区 skill 零分叉；代价=每条新 spec 首轮 warn 一次后自纠，属预期）
- 不做 §3.2 to-tickets 闸门、§3.3 tickets 对称项（视台账数据二期）
- 不做 LLM 语义审查、不做 quack 式内容判定、不做文件内 skip 注释
- 不动 stage-gate/workflow-gate 本体；不合并钩子链

## 风险与对策（v2）

| 风险 | 对策 |
|---|---|
| 误拦存量/旧 checker 项目 | 基线清单豁免 + 能力探测降级 + warn 先行 + off 软开关 |
| 静默失效（四层降级无声） | 全路径 trace 心跳/degraded/skip 事件，切换判据强制检查心跳非空 |
| block 死循环 | 每次重报 + 连续 3 次升级报人（verify-blocks 模式） |
| 门禁被模型自关 | 豁免清单在 .devflow/ 人工维护，文件内注释豁免弃用 |
| 口径漂移三套数 | Phase 1 映射表 + 回执对账表 + ADR 单点定死 |
| settings 合并事故 | merge-settings .bak 既有链 + 实施后 jq 核无双注册 + 会话重启提醒 |

## 执行记录（2026-09-11 实施当日）

- 分支 `spec-gate`（wt），3 commit：6eda8cd（checker --spec）→ 686f70b（钩子+注册+install）→ f52a069（bats 22 用例）
- **口径修正**：原"Phase 内验证 templates/spec-template.md → rc 0"错误——模板合规表为占位 `✅/❌`，属"未自查"应判硬缺项（rc 1：S1-S5 对应 5 项硬缺 + 9 项 advisory）。实现即按此语义：占位/空状态 = 未做自查
- 额外硬化：路径含 `..` 穿越段的 file_path 不处理（真实 tool_input 均为规范化绝对路径）
- **验证实况**：
  - bats 22 用例宿主机 bash 等价驱动全绿（`run()` 垫片，与 bats 文件同源转换）。正式 `run_tests.sh` 未跑：本地 `devflow-test:ubuntu` 为旧镜像（无 python3），docker build 需拉 `ubuntu:22.04`——docker hub 被 Windows 代理未启动阻断。**合并回灌前需代理在线重建镜像跑一次全套**
  - fresh + --update 沙箱实测（`--home` 隔离）：baseline create-once 正确（legacy 入列、安装后新增被管）、mode=warn 生成、hook 执行位、settings.local.json 注册、`hook 自检通过（8 项）`含 spec-gate 双断言
  - 端到端：新 spec → additionalContext 缺项；legacy → 静默；10 次 p95 = 70ms < 200ms
  - ticket 模式回归：与旧版输出 diff 除 ac_levels 修复处外逐字一致
- warn 通道实证：PostToolUse exit 0 stderr 模型不可见（官方语义），warn 走 stdout `hookSpecificOutput.additionalContext`
- 遗留待办：NAS 性能实测、UMES3 真机回灌、观察期台账、block 切换、全局记忆 2 条晋升、ADR 定稿
