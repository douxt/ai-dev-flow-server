# ADR-013: spec 出口门禁（spec-gate）归形式正确性轴，warn/block 两段制

## 状态：已采纳
## 日期：2026-09-11

## 背景

UMES3 反馈（docs/feedback/spec-gate-hardblock-feedback-20260911.md）：阶段机只门控"源码写入时机"，`.md` 全仓豁免，spec 产物内容零机器防线——同一会话三轮不合规 spec 零报警。需要 docs/specs 出口门禁。经 4 路代理评审 + 主会话实证后定稿。

## 决策

### 1. 归轴：形式正确性轴（ADR-006 原则 1 要求明确归轴）

spec-gate 全部检查为结构校验（合规表节/状态列/AC 存在/Risks 节），即"写得齐不齐"——**形式轴从测试产物扩展到 spec 产物**。内容有效性（方案好坏）归异构评审（G0 类比在测试侧），本门禁不涉。

### 2. 校验逻辑单源：check_constitution.py `--spec` 模式

拒绝钩子内自造 grep（会与 dispatch 校验器、spec-checklist 构成三套源——正是反馈抱怨的"两套源没粘合剂"的复发）。校验函数与被 UMES3 反馈点名"skill 模板 vs 宪法"两套源之弊同构，单源优先。

### 3. 通道语义：warn 走 additionalContext，block 走 exit 2

PostToolUse **exit 0 的 stderr 模型不可见**（官方语义；社区 issue #24788 佐证通道边界）。warn = stdout JSON `hookSpecificOutput.additionalContext` + stderr 留空 + exit 0；block = exit 2 + stderr。

### 4. 存量豁免：安装时路径基线清单（create-once），弃用 mtime

mtime 方案被实证否决三重理由：① PostToolUse 触发于写入后，mtime 必为"刚刚"，豁免覆盖不到目标场景；② git checkout 重置 mtime、worktree 不含未跟踪 marker；③ WSL/NAS 时钟漂移可致全量永久豁免。基线清单 = `--update`/fresh 时枚举存量 `docs/specs/*.md` 落 `.devflow/spec-gate-baseline`，重复 update 不刷新（安装后新增的无表 spec 本就该被管）。

### 5. 降级契约：内部错误绝不解读为缺项

退出码 `0=通过 / 1=硬缺项 / 2+=内部错误`；钩子对 rc≥2、checker 缺失、输出非 `{"mode":"spec"}` 形状（旧版无 --spec 时 rc=1 报"文件不存在"）、jq/python3 缺失——一律静默放行 + `spec-gate.degraded` 留痕。全路径 trace 心跳（skip/pass/warn/block/degraded），使观察期可区分"无误拦"与"没运行"。

### 6. 豁免面人工持有

`.devflow/spec-gate-exclude` 每行一路径。弃用文件内注释豁免（模型可自贴消音 = 管束对象可自我关闭）。"文中含合规表字样才门禁"的 quack 判定同步否决：门禁目标恰是"缺合规表的新 spec"，含表才拦 = 门禁自杀。

### 7. warn 每 session 每文件封顶 3 次；block 每次重报 + 连续 3 次升级报人

缺项指纹去重弃用——增量补写缺项集常变，指纹去重既防不住打断也放不过最终态。台账按日轮换。

## 后果

- 正面：spec "忘做宪法自查"这类事故从纯声明约束变为机器可判出口门禁；dispatch 与人工/AI 路径共用同一校验器。
- 代价与边界：① to-spec 社区 skill 不注入合规表（零分叉定案），每条新 spec 预期首轮 warn 一次后自纠；② Bash 写入旁路（`cat>`/`mv`/`tee`）不经 matcher，已知限制不补；③ 门禁是"事后 nag"非回滚——PostToolUse 写入已落盘，硬保证依赖模型响应 + 阶段推进链。
- 回滚：`jq 'del' settings.local.json hooks 中 spec-gate 条目` + 删 `~/.claude/hooks/spec-gate.sh`；软停 `.devflow/spec-gate-mode` 写 `off`。
- 关联：ADR-006（归轴原则）、DEFECT-014（平台 ADR 全集复制撞租户编号——本 ADR 传播时同样适用该缺陷，修复前租户侧编号冲突已知）。
