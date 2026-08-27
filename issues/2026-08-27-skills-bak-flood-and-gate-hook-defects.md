# ai-dev-flow-server 安装产物缺陷报告：skills .bak 洪水 + 三门禁 hook 从未生效

- 日期：2026-08-27
- 来源：UMES3 侧 `/config-health-diagnose` 全量配置体检（报告见 claude-config `skills/config-health-diagnose/reviews/2026-08-27-global+UMES3.md`）
- 涉及版本：AI Dev Flow v3.2（install.sh + config-templates）
- 严重度：问题一 P1（实际影响近 P0）；问题二/三 P0（安全机制静默失效）

## 摘要

在 UMES3 用户环境（WSL，claude-config 纳管 ~/.claude）的例行配置体检中，发现三类可归因到 ai-dev-flow-server 安装/模板产出的缺陷。UMES3 侧已完成止血与修复，本报告说明根因、证据与对上游的改进建议，防止其他安装环境复发。

---

## 问题一：install.sh 每次运行把旧 skill `mv` 成 `.bak-<时间戳>`，永不清理 → 累积 977 个被 Claude Code 当真实 skill 加载

### 根因（代码定位）

`install.sh` 三处备份逻辑均生成带时间戳的 `.bak` 且**无任何轮换/清理**（全文件 grep 无 `rm.*bak-\*`）：

| 位置 | 行为 | 影响路径 |
|---|---|---|
| L407-418（CC skills 循环） | `[ -d $dst ] && bak="${dst}.bak-$(date +%Y%m%d-%H%M%S)"; mv $dst $bak` | `~/.claude/skills/<name>.bak-*`（目录） |
| L421-433（gate skills 循环） | 同上 | 同上 |
| L309-312（deploy_file 函数） | 文件级同模式 `cp $dst $bak` | `项目/.devflow/**.md.bak-*`、`gate-checklists` 等 |

关键设计错误：**备份目的地放在 `~/.claude/skills/` 内**，而 Claude Code 会扫描该目录下所有含 SKILL.md 的子目录并注入系统提示——备份副本因此全部变成"真实 skill"。

### 实测影响（UMES3 环境，2026-08-27 清理前）

- `.bak-*` 共 **977 个**（974 目录 + 3 个悬空 symlink），真实 skill 仅 64 个
- skill 清单注入：.bak 占 **240KB / 256KB（94%）**，估算每会话启动多耗 **4–6 万 token**，恒定重复；磁盘 27MB（有效仅 1.6MB）
- 时间分布与安装次数吻合：07-29:15 / 07-30:78 / 07-31:160 / 08-01:160 / 08-04:64 / 08-05:32 / 08-16:80 / **08-21:388**（8/14 体检时 509 个，两周内翻倍）
- **异常点（建议上游排查）**：`review-cc-cli.bak-*` 累计 456 个 ≈ 其他 skill（约 100）的 4.5 倍；且环境里存在 3 个指向 `claude-config/skills/review-cc-cli` 的悬空 .bak symlink——怀疑有额外调用路径（如 `/review-cc-cli` 自举或某 workflow 单独重跑 install）在放大该条目，或 `mv` 对 symlink dst 的处理有额外行为
- 次生污染：`deploy_file` 模式同样在业务项目里堆 `.devflow/knowledge/*.md.bak-*`（UMES3 工作区现存 12+ 个，污染 git status）与 memory 目录 `*.md.bak-*`

### UMES3 侧已执行的处置（供参考，非上游修复）

1. 全量 `tar czf` 归档（974 目录 + 3 链接，3.8MB，覆盖校验无遗漏）→ 删除
2. 核对 64 个可加载 skill 与清理前真实数一致，关键 skill 逐一存活
3. 备份保留：`~/.claude/backups/config-fix-20260827/skills-bak.tar.gz`，可精确还原任一副本

### 对上游的改进建议

```bash
# 方案 A（最小改动）：备份前轮换删除同前缀旧 .bak-*，仅保留最近 1 份
find "$(dirname "$dst")" -maxdepth 1 -name "${skill_name}.bak-*" -exec rm -rf {} +

# 方案 B（更优）：备份移出扫描目录
#   skills 备份 → ~/.claude/.skill-backups/（不在 skills/ 内，不被扫描）
#   项目 .devflow 备份 → .devflow/.bak/ 或直接依赖 git（目标多为受版本控制文件）

# 方案 C（配合 A/B）：install.sh 结束段输出统计
#   "本次新增备份 N 个 / 历史残留已清理 M 个"
```

另建议：`deploy_file` 的文件级 `.bak-<ts>` 改为「内容不同才备份 + 同名只留最新一份」。

---

## 问题二：三个安全门禁 hook 自部署起 100% 未生效（workflow-gate / stage-gate-block / test-gate-block）

以下脚本经 install 链路部署到用户 `~/.claude/hooks/`。**真实会话调用中无一执行过拦截逻辑**，CLAUDE.md 中"工作流评估强制/阶段门禁/L0 测试门禁"均为纸面规则。共 7 处缺陷：

| # | 缺陷 | 位置 | 后果 |
|---|---|---|---|
| 1 | 用 `$1/$2` 取 TOOL_NAME/TOOL_INPUT，但 Claude Code PreToolUse 协议是 **stdin 传 JSON**；注册命令为裸路径不传参 | 三脚本头部 | 真实调用 `$1` 未绑定 |
| 2 | 脚本带 `set -euo pipefail` | 同上 | 缺陷 1 直接 → **每次调用崩溃 exit 1**（非阻塞错误，模型无感知）|
| 3 | workflow-gate 拦截路径 `exit 1`（PreToolUse 中仅 exit 2 阻断+注入 stderr 给模型） | 末段 | 即使修好取参也不拦截；`stage-gate-block.sh:6` 注释自证"exit 2 是唯一可靠阻断"——团队已知，未统一 |
| 4 | `session_id="${CC_SESSION_ID:-unknown}"`，无任何来源注入该变量 | workflow-gate L61 | route 文件恒 `unknown|pending`，跨会话共享、二次编辑永久放行 |
| 5 | `is_test_file` 在第 69 行调用、第 98 行才定义（bash 无函数提升） | stage-gate-block | GREEN 窗口反作弊层即使前病全愈也静默失效 |
| 6 | `is_test_file` 内 `$FILE_PATH` 被引号 heredoc（`<<'GREEN_BLOCK'`）锁死不展开；stage-gate-block.sh **无执行位**而注册为裸路径（无 `bash` 前缀）| stage-gate-block | 消息显示字面量；进程起不来（Permission denied）|
| 7 | test-gate.sh 输出走 stdout（exit 2 时仅 stderr 注入模型） | test-gate-block L42 | 失败细节对模型不可见，拦截无指导性 |

### UMES3 侧修复现状（2026-08-27）

- 三脚本已按上表 7 项全部修复：stdin JSON 解析（保留 `$1/$2` 手动测试兼容 + jq 缺失降级放行）、exit 2、session_id 取 stdin、函数定义前移、heredoc 去引号、chmod +x、gate 输出转 stderr
- **12 态单测全过**（workflow 首拦/同 session 放行/新 session 重拦；stage pre-tdd 拦源码放文档/GREEN 拦测试放实现；test-gate 成败/非 RED 放行），并在真实会话中观察到活体拦截
- 已纳入 claude-config git 跟踪（`hooks/`），`~/.claude/hooks/` 原位置改 symlink；原始崩溃版备份于 `~/.claude/backups/config-fix-20260827/`

### 对上游的改进建议

1. **修复版直接吸收回 config-templates / 安装源**（联系 UMES3 侧取 `claude-config/hooks/{workflow-gate,stage-gate-block,test-gate-block}.sh`），否则其他环境重装即回退
2. install.sh 加**安装后 hook 自检**（B5.8 生效性验证），示例：
```bash
selftest_hook() {  # $1=脚本 $2=期望exit
  local rc
  printf '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/gate-selftest.ts"},"session_id":"selftest-%s","cwd":"/tmp"}' "$(date +%s)" \
    | "$1" >/dev/null 2>&1; rc=$?
  [ "$rc" = "$2" ] || { echo "❌ hook 自检失败: $1 期望 exit $2 实得 $rc"; return 1; }
}
```
3. 文档措辞修正：在自检落地前，CLAUDE.md/README 中"门禁强制执行"应注明依赖条件，避免"文档声明失实"（我们已为此踩过一次归因偏差，见记忆 devflow-gates-not-automatic）

---

## 问题三：file-guard「安全配置自保护」为死代码（模板同病）

- 位置：`config-templates/default/hooks/file-guard.sh`（及其部署实例）——第 47 行豁免 `case` 含 `$HOME/.claude/*` → **先于**第 51 行 `$HOME/.claude/settings.json|settings.local.json|hooks/*` 保护分支命中并 `exit 0`
- 后果：保护分支不可达；"settings.json 和 hooks/ 受自保护，不可修改"的播报声明不实——任何会话的 agent 可**无提示修改防御 hook 与权限配置本身**（实证：本次 UMES3 侧连续修改三个 hook 文件零拦截）。与 session-start 播报、CLAUDE.md 声明直接矛盾
- 修复：把自保护 `case` 移到豁免 `case` 之前，或从豁免模式排除 `settings.json|settings.local.json|hooks/*|.git-hooks/*`；修复后补一条 `echo ... | file-guard.sh` 期望 exit 2 的单测
- 关联不对称发现：bash-firewall 的 `PROTECTED_REPOS` 不含 `$HOME/dev/*`，而 file-guard 的 repo case 含 `$HOME/dev/*`——两钩子保护面不一致，建议对齐

## 问题四（低优先，文档层）

- 模板 CLAUDE.md「模型路由建议」（Opus/Sonnet/Haiku）在使用第三方网关（本环境 ANTHROPIC_* 已映射 Qwen）时名存实亡，`/review-cc-cli --opus` 类指令路由的实际模型与文档不符——建议模板注明前提或在 install 时检测网关配置输出提示
- 模板「所有代码变更走功能分支 → PR → 审查 → 合并」与 wt 工具链"worktree 分支 + 用户下令合并 master"实际实践冲突，建议二选一并标注适用域

## UMES3 侧改动台账（截至 2026-08-27，均已提交/备份）

| 改动 | 位置 | 回退 |
|---|---|---|
| 三门禁 hook 修复+纳管 | claude-config `hooks/`（git），`~/.claude/hooks/` symlink | `~/.claude/backups/config-fix-20260827/*.sh` |
| 977 .bak 归档删除 | `~/.claude/skills/`（64 真实 skill 无损） | 同目录 `skills-bak.tar.gz` |
| UMES3 密钥 symlink 断开 | UMES3 commit `8ca94b7`，项目层改为无 env 真实配置 | `ln -sf ~/.claude/settings.local.json <项目>/.claude/settings.local.json` |
| 体检报告 | claude-config `skills/config-health-diagnose/reviews/2026-08-27-global+UMES3.md` | — |

待排期（UMES3 侧）：P0-1 权限 allow 收窄、P0-2 敏感路径成对 deny、其余 3 环境（go-vue-scaffold / ai-dev-flow-server / MAF-Hub）的密钥 symlink 同法断开。

—— 由 UMES3 侧 Claude Code 配置体检生成，数据均可从上述备份/报告复核。

---

## 上游处理记录（ai-dev-flow-server，2026-08-27）

| 问题 | 处置 | 落点 |
|------|------|------|
| 一 .bak 洪水 | ✅ 方案 B+A 结合：skill 备份移出 skills/ 扫描根 → `~/.claude/.skill-backups/`；文件级/目录级同目标只留最新 1；旧式残留自动迁出；安装结束输出统计（方案 C）。`review-cc-cli.bak 4.5 倍异常`不再放大（根因=永不清理），调用路径专项排查遗留 | install.sh（rotate_file_bak / rotate_skill_bak） |
| 二 三门禁失效 | ✅ 吸收 UMES3 修复版（claude-config hooks/）进 config-templates；hooks 全量 755 + install 部署后显式 chmod；新增安装后 hook 自检 selftest_hooks（5 用例含 file-guard 保护复活）；新增 stdin JSON 协议 bats 19 用例（对照实验：旧模板全挂/新模板全绿）；旧 workflow-gate.bats 3 处"期望 exit 1"断言修正为 2（与坏实现一致错的测试） | 89e1deb |
| 三 file-guard 死代码 | ✅ 模板重写：stdin JSON 取参（原 `$1` 同样坏）+ 自保护 case **前置于豁免** + exit 1→2，无 common.sh/个人路径依赖。**注意**：claude-config 116 行部署版的 case 顺序 bug 属个人基础设施，需环境侧另行修复（本仓库不动） | config-templates/default/hooks/file-guard.sh |
| 四 文档措辞 | ✅ 模型路由表加第三方网关档位说明注；Git 约束"功能分支→PR→合并"改为与 wt 实践一致（PR 为 AFK 管线可选通道） | config-templates/default/CLAUDE.md |

已知残留：修复版 workflow-gate/test-gate-block 使用 `grep -oP`（GNU 依赖），busybox 环境会失效——已在 tests/run_tests.sh 注明 stdin 测试仅 ubuntu 镜像跑；跨平台兼容改造待评估。
