# 回执：spec-gate 硬阻断反馈处理结果（2026-09-11）

> 回应：`/home/dou/projects/UMES3/docs/feedback/spec-gate-hardblock-feedback-20260911.md`
> 处置：**方向全部采纳，实施于本仓 `spec-gate` 分支（3 commit，v3.7）**；§3 设计案有 8 处经实证修正。本文档为设计案与边界定稿，请 UMES3 侧知悉后 `--update` 回灌。

## §0 调查方法警示

已核实属实并致谢：全局流程钩子确实挂在 `settings.local.json`（本会话 dump 全量 settings*.json 复核，4 个流程钩子 + 4 个 PostToolUse 全在 local 版）。"评估接线必须 dump 全部 settings*.json"将晋升为全局记忆。

## §3 设计案逐条裁定

| 反馈条款 | 裁定 | 依据 |
|---|---|---|
| §3.1 挂载 PostToolUse Edit\|Write、管 docs/specs 产物结构 | ✅ 采纳 | 与 stage-gate 正交定性成立 |
| §3.1 "grep 级校验四件套" | ⚠️ 修正 | 自造 grep = 与 dispatch 校验器成第三套源。改为 `check_constitution.py --spec` 模式，校验逻辑单源；钩子仅调用+分发 |
| §3.1 exit 2 + stderr（warn 语义） | ⚠️ 修正 | **PostToolUse exit 0 的 stderr 模型不可见**（官方语义实测确认）。warn 模式改 stdout JSON `hookSpecificOutput.additionalContext`；block 才走 exit 2+stderr |
| §3.1 合规表"无 ❌ 即过" | ⚠️ 修正 | 与 spec-checklist L27"S6-S9 为 advisory"打架。分级：表行 #1-#5（=S1-S5 必过项）❌/未填写 → 硬失败；#6-#11/P/H/VL → advisory。占位 `✅/❌` = 未自查，同判 |
| §3.1 触发条件"路径匹配" | ⚠️ 增补 | 存量旧 spec 基线豁免**不能用 mtime**（PostToolUse 触发时 mtime 必为"刚刚"，豁免逻辑空转；git checkout 还会重置 mtime）。改安装时生成的**路径基线清单** create-once |
| §3.2 to-tickets 前置闸门 | ⏸ 缓行二期 | "mtime 最新 spec"启发式在并行/断点场景拿错目标；先积累 spec-gate 台账数据，有"spec 已合规但拆票仍漏查"证据再上 |
| §3.3 tickets 对称项 | ⏸ 缓行二期 | 同上，dispatch 路径已有 check_constitution 覆盖机器项 |
| §4 验证方案 5 条 | ✅ 全承接 | 反向/正向/零干扰/性能/串联 → 落为 `tests/hooks/spec-gate.bats` 22 用例；自测文件名弃用 `.` 前缀隐藏名（曾与豁免规则互斥，已删该豁免） |
| §5 不做清单 3 条 | ✅ 尊重 | 另加：不做"文中含合规表字样才门禁"的 quack 判定——门禁目标恰是"缺合规表的新 spec"，含表才拦=门禁自杀 |

## 实施中额外发现（反馈未覆盖）

1. **旧版校验器崩溃误读风险**：未回灌项目的 `check_constitution.py` 无 `--spec`，会把 `--spec` 当文件路径、rc=1 报"文件不存在"——钩子若把 rc=1 一律当"缺项"即全量误拦。契约：checker 退出码 `0=通过 / 1=硬缺项 / 2+=内部错误`，钩子对 2+ 及非 `{"mode":"spec"}` 形状输出一律**静默放行 + degraded 留痕**。
2. **`frontmatter` 依赖**：原模块级 import 缺包即整脚本崩，--spec 不需要它 → 懒导入。
3. **顺带修复存量 bug**：`10.ac_levels` 比较 `"[auto]" in set(裸捕获组)` 恒假 → 恒 warning（不影响退出码，仅噪声）。
4. **降级可观测**：jq 缺 / python3 缺 / checker 缺 / 崩溃 / 豁免 / pass 全路径写 `.devflow/trace.jsonl` 心跳（`spec-gate.*` 事件），防"四层静默降级"把"没运行"伪装成"无误拦"。
5. **豁免面人工持有**：`.devflow/spec-gate-exclude`（每行一路径）。弃用文件内注释豁免——模型可自行贴注释消音 = 门禁可被管束对象自我关闭。
6. **Bash 旁路为已知限制**：`cat >`/`tee`/`mv` 进 docs/specs 不经 Edit|Write matcher，本版不补（成本错配；dispatch 出口仍会拦）。

## warn → block 切换判据（人工，观察期后）

1. `.devflow/trace.jsonl` 存在 `spec-gate.pass/degraded` 心跳（证明钩子在跑）
2. ≥5 个不同 spec 文件出现过 warn，人工逐条回放标注 **0 误拦**（to-spec 社区模板首轮的"预期补表 warn"不计误拦）
3. 满足后向项目 `.devflow/spec-gate-mode` 写 `block`；软停写 `off`
4. 回滚：jq 摘 settings.local.json 中 spec-gate 条目 + 删钩子文件（命令见 ADR-013）

## 口径对账表（终结"13 项/11 项/S1-S13"三套数）

| 合规表行（spec-template 17 行） | checklist | 机器校验（--spec） |
|---|---|---|
| #1-#5 | S1-S5 | **硬**：节存在 + 行状态 ✅ |
| #6/#8-#11 | （无 S 对应，宪法内项） | advisory |
| #7 | S6 | advisory |
| P1-P4 | S7 | advisory |
| H1-H3 | S8 | advisory |
| VL | S9 | advisory |
| —（产物级） | S10-S13 | S10 写入即真；S11-S13 归人工评审 |

宪法正名：**11 规则 + Ponytail 4 问 + 三假设 3 + 验证层级 = 合规表 17 行**；反馈所称"13 项"不再使用。

## UMES3 侧待办（回灌时）

- 以**合并后的 main**为 SOURCE 跑 `bash install.sh <UMES3> --update`（勿用进行中 worktree——install 有 git pull 副作用）
- 若 UMES3 有人工改动过 `.devflow/scripts/check_constitution.py`（git 状态 M）：deploy_file 会先备份 `.bak-<ts>` 再覆盖，改过的内容需人工回并
- 回灌后**重启 CC 会话**钩子才注册生效（hook 在会话启动时加载）
- 项目级 gate-checklists 独立拷贝不被 --update 同步（已知盲区）：核对 `spec-checklist.md` md5
