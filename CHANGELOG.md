# ai-dev-flow-server v3.0 变更说明

> 发布日期：2026-07-23
> 变更范围：Skill-Harness 分离架构 + Matt Pocock v1.1 五命令体系 + 基础设施约束层增强

## 一句话总结

吸收 Matt Pocock v1.1（16.2 万星事实标准）+ 社区最佳实践，采用"直接调用 + 基础设施兜底"架构，将 9-Gate 自研 skill 体系替换为 5 阶段轻量流程。

## 核心理念：Skill-Harness 分离

```
v2.1 嵌套方式：gate skill → 底层 skill → 约束逻辑耦合在 skill 内
v3.0 直接方式：Matt Pocock skill 直接干活 → 基础设施层（hooks/checkers）兜底约束
```

Agent = Model + Harness。约束由 Harness 保证，而非 Skill。Skill 保持简单直接；Hook/规则/配置提供确定性约束。

---

## Phase 1: Skill 层替换

### 退役

| 退役 | 原因 |
|------|------|
| gate-1-grill ~ gate-6-afk（7 个 gate skill） | 约束能力已下沉到 hook/checker |
| grill-me, to-prd, to-issues（3 个 CC skill） | 由 v1.1 对应 skill 替代 |
| caveman, zoom-out, write-a-skill（3 个） | Matt Pocock 已从仓库移除 |

### 新增

| skill | 来源 | 用途 |
|-------|------|------|
| `/grill-with-docs` | Matt Pocock v1.1 | 基于文档对话澄清需求（默认入口） |
| `/wayfinder` | Matt Pocock v1.1 | 多会话大任务决策地图（~5%） |
| `/research` | Matt Pocock v1.1 | 单 Agent 深度调研 |
| `/to-spec` | Matt Pocock v1.1 | 需求→规格（可逆向） |
| `/to-tickets` | Matt Pocock v1.1 | 规格→工单拆分 |
| `/implement` | Matt Pocock v1.1 | 工单→代码+内建审查 |
| `/code-review` | Matt Pocock v1.1 | 独立子代理审查全部 diff |

### 保留

diagnose, tdd, triage, prototype, handoff, setup-matt-pocock-skills, review-cc-cli, improve-codebase-architecture

总计：15 个 skill（退役 13 个，新增 7 个，保留 8 个）

---

## Phase 2: 基础设施约束层增强

### workflow-gate hook（PreToolUse）

- 首次 Edit/Write/Bash(写入) 前拦截，强制工作流评估
- `.workflow-route` 绑定 session_id，跨会话残留自动失效
- 死锁防护：`.workflow-route` 自身写入不受限
- 逃生机制：`~/.claude/.emergency-bypass` → 全部放行

### stage-tracker hook（PostToolUse）

- 产品检测（非 skill 调用检测）：spec.md → `spec:done`，issues/*.md → `tickets:done`，PR → `implement:done`
- 阶段约束为 advisory 警告，不硬拦截
- 阶段跳跃检测 + 无变化去重
- 排除 TEMPLATE.md 模板文件干扰

### suggest-rules hook（PostToolUse）

- 检测 `.devflow/rule-suggestions.md` 待处理项
- 30 分钟去重提醒
- `grep -cE '^\s*\[x\]'` 精准匹配行首已完成项

### check_constitution.py 重写（147→450 行）

- 15 项机器检查（原 7 项 + 8 项新增）
- 新增：安全红线扫描（auth/payment/crypto/delete/permission）
- 新增：上下文窗口预算估算（≤48K tokens）
- 新增：AC 验证级别校验（[auto]/[human-verify]/[decision]）
- 新增：blocked_by DFS 循环依赖检测
- 新增：Ponytail 可机器检查项 + Scope 边界 + 架构约束 + 前置准备 + 测试策略
- `--batch` 目录批量扫描模式

### 任务锁文件

- `mkdir .devflow/locks/<ticket-id>` 原子锁防同机并发
- reconciler.sh 回收：锁超过 6h → 自动清理

### 全流程 trace 日志（`.devflow/trace.jsonl`）

- hook: gate.pass / gate.block / gate.bypass / stage.transition / stage.skip
- checker: constitution.check
- migration: migration.v2_to_v3

### 量化指标追踪（`scripts/metrics.py`）

- ticket 状态统计 + PR 合并率 + 返工次数 + 平均消化时间
- dispatch.sh 自动更新

---

## Phase 3: 方法论补全

### CLAUDE.md 模板（156 行）

- 工作流自动路由：评估三问 + 路由表（6 路径）+ 评估输出格式
- 5 命令体系 + /wayfinder 使用边界
- 引导词体系（6 条）
- 模型路由建议
- 安全红线（5 类）
- 上下文预算（≤40%）

### 知识宪法更新

| 文档 | 变更 |
|------|------|
| `01-核心方法论.md` | v5.0 — 补充 v1.1 命令 + 引导词 + 安全红线 |
| `02-Step-Gate流程.md` | v3.0 — 9 Gate → 5 阶段，标注各阶段 skill+ 约束 |
| `03-Spec质量宪法.md` | **新增** — 11 项 + Ponytail 四问 + 三假设审计 + 5 级验证 |
| `04-Ticket质量宪法.md` | **新增** — 15 项含窗口预算 + 三级 AC 分类 |
| `08-安全红线宪法.md` | **新增** — 5 类红线 + 人工审查清单 + 逃生参考 |

### 模板更新

| 文件 | 变更 |
|------|------|
| `templates/spec-template.md` | 新增 — 121 行完整模板 + 19 项合规表 |
| `templates/issue-template.md` | v3.0 — AC 级别 + 窗口预算自检 + safety 字段 |
| `templates/gate-state.yml` | v3.0 — 5 阶段：explore→spec→tickets→implement→done |
| `templates/CLAUDE.md.base.append` | v3.0 — 5 命令 + 5 阶段状态机 + 安全红线 |

---

## Phase 4: 集成测试与文档（本版本）

### 新增集成测试（51 用例）

| 文件 | 用例 | 说明 |
|------|:---:|------|
| `tests/integration/routing.bats` | 19 | CLAUDE.md 14 段关键内容 + workflow-gate 3 行为 + hook 注册 2 |
| `tests/integration/hook-chain.bats` | 6 | workflow-gate→stage-tracker→trace 链 |
| `tests/integration/migration.bats` | 13 | v2→v3 gate-state 迁移（9 Gate→5 阶段映射） |
| `tests/integration/escape.bats` | 7 | 逃生机制（bypass 文件创建/删除/恢复） |
| `tests/integration/rollback.bats` | 6 | 回滚验证（备份恢复 + hook 完整性 + trace 审计） |

### 新增文档

| 文件 | 说明 |
|------|------|
| `docs/references/v2-to-v3-migration.md` | v2.1→v3.0 升级指南 |
| `docs/references/testing-strategy.md` | 测试策略（4 层 51 用例） |

### Bug 修复

- **workflow-gate.sh**: grep -oP lookbehind 中 `\s*` 导致 PCRE "not fixed length" 错误 → 改用 `\K` 重置匹配
- **stage-tracker.sh**: `issues/TEMPLATE.md` 被误计为 ticket → 排除模板文件
- **metrics.py**（Phase 3 审查修复）:
  - `git_stats()` pr_count/pr_merged 使用同一 grep，合并率永为 100% → 已修
  - `estimate_digest_time()` 用阶段名做 key 跨事件无法配对 → 已修
- **suggest-rules.sh**（Phase 3 审查修复）: `[x]` 匹配过宽 → 限制为行首模式

---

## 兼容性

- **向前兼容**：`install.sh --update` 自动检测旧 `.gate-state` → 调用 `migrate-gate-state.sh` 迁移到 `.devflow/stage`
- **备份保护**：迁移生成 `.gate-state.v2.bak`，可手动回滚
- **已运行 AFK 管线不受影响**：迁移只改阶段追踪文件，不影响 dispatch/reconcile 逻辑
- **旧 skill 保留**：退役 skill 在 `.archived/` 目录，不参与安装

---

## 影响范围

| 组件 | 影响 |
|------|------|
| 新安装（v3.0） | 完整 v3.0 流程，15 个现代 skill |
| `--update`（v2.1→v3.0） | 自动迁移 gate-state + 备份旧文件 + 替换 skill |
| 已运行 AFK 管线 | 无影响（管线兼容新旧两种 ticket 格式） |
| 已有项目 spec/issues | 无影响（宪法检查新增项为 warning，不阻断） |

---

# ai-dev-flow-server v2.1 变更说明

> 发布日期：2026-06-30
> 变更范围：角色分级模板系统 + `devflow role switch` 秒切命令

## 一句话总结

引入 `--role` 参数（owner/developer/agent-b）+ `devflow role switch` 秒切命令，不同项目获得不同 Agent 行为边界。

---

## 新增功能

### 角色分级模板系统（`--role owner|developer|agent-b`）

| 角色 | 权限 | 产出 | 适用 |
|------|------|------|------|
| `owner` | 全权 | 代码+PR+部署 | 个人项目 |
| `developer` | 业务代码+PR，禁改管线 | 代码+PR | 团队项目 |
| `agent-b`（默认） | 仅issue，handoff协作 | issue | 受限环境 |

### `devflow role switch` 秒切命令

```bash
devflow role              # 查看当前角色
devflow role switch <R>   # 切换角色
devflow role list         # 列出可用角色
```

切换时自动：替换 CLAUDE.md 约束段、创建/删除 `_handoff/`、创建/删除 `AGENTS.md`、更新 `config.yaml` role 字段。

### 模板拆分

- `CLAUDE.md.base.append` — 通用（Gate 流程、Issue 状态机、计划文件管理+ADR）
- `roles/{owner,developer,agent-b}/` — 角色专属约束

### 修复

- 解除模板中 OpenLobby 身份硬编码，改为 `__PROJECT__` 占位符

---

# ai-dev-flow-server v2.0 变更说明

> 发布日期：2026-06-30  
> 变更范围：`install.sh` / `uninstall.sh` 通用化 + 离线 skill 缓存 + 测试套件

## 一句话总结

install.sh 从硬编码 openlobby 服务器专用 → **环境自适应 + 三种部署模式**的通用安装器，一套脚本适配裸机 / VPS / Docker 容器 / WSL2。

---

## 新增功能

### 1. 三种部署模式（`--mode`）

```bash
bash install.sh <项目路径> --mode frontend   # 仅装开发工具链（gate/skills/config）
bash install.sh <项目路径> --mode backend    # 仅装调度管线（archon/scripts/调度器）
bash install.sh <项目路径> --mode full       # 全装（默认）
```

| 组件 | frontend | backend | full |
|------|:--------:|:-------:|:----:|
| gate 脚本（6 个） | ✅ | — | ✅ |
| gate skills（7 个） | ✅ | — | ✅ |
| gate-checklists（6 个） | ✅ | — | ✅ |
| CC skills（15 个） | ✅ 默认 | — | ✅ 默认 |
| settings + hooks + CLAUDE.md | ✅ 默认 | — | ✅ 默认 |
| .devflow/config.yaml | ✅ 简化版 | ✅ | ✅ |
| knowledge/（7 份知识文档） | ✅ | ✅ | ✅ |
| archon/（调度管线） | — | ✅ | ✅ |
| scripts/（检查脚本） | — | ✅ | ✅ |
| 调度器配置（root 段） | — | ✅ | ✅ |
| .gate-state | ✅ | — | ✅ |
| git hooks | ✅ | ✅ | ✅ |

### 2. 四种调度器（`--scheduler`）

| 值 | 输出内容 |
|----|---------|
| `systemd` | service + timer unit |
| `cron` | crontab 条目（`--user` 指定运行用户） |
| `external` | 提示文本（宿主机配置 `docker exec ...`） |
| `none` | 不输出（前端默认） |

不指定 `--scheduler` 时自动检测：Docker → none，有 systemd → systemd，有 crontab → cron。

### 3. 环境自适应

- 自动检测 Docker / systemd / cron 环境
- Docker 内自动创建 `~/.claude → ~/.config/claude` symlink（持久化）
- `--home <path>` 覆盖 `$HOME`（Docker 内 coder 用户路径与宿主机不同时使用）

### 4. 增量更新（`--update`）

```bash
bash install.sh <项目> --update          # 读取 .devflow/config.yaml 的 mode，只更新已有文件
bash install.sh <项目> --force --update  # 强制覆盖（config 模板更新后刷新 hook 等）
```

`--update` 不影响 `.gate-state` 和 `config.yaml` 的 mode 字段。

### 5. 预览与强制模式

| 参数 | 行为 |
|------|------|
| `--dry-run` | 只打印每步将做什么，不实际写入 |
| `--force` | 覆盖已有文件（**永不覆盖 `.gate-state`**） |
| `--no-config` | 跳过 settings + hooks + CLAUDE.md |
| `--no-skills` | 跳过 CC skill 安装 |
| `--skip-root` | 跳过 root 段调度器输出 |

### 6. 离线 skill 缓存（`skills-cache/`）

15 个 CC skill 纳入 git 管理，安装时不依赖网络。附带 `.version` 版本文件和 `sync-skills.sh` 同步脚本。

### 7. 自动化测试套件（`tests/`）

17 个 bats-core 测试文件，60 个用例，Docker 容器内运行：

```bash
bash tests/run_tests.sh              # Alpine + Ubuntu 双发行版
bash tests/run_tests.sh -f "update"  # 过滤单个测试
```

---

## 变更文件清单

| 文件 | 改动 | 说明 |
|------|:----:|------|
| `install.sh` | 重写 | +881/-270 行，新增 CLI 参数、环境检测、mode 条件化 |
| `uninstall.sh` | 新增 | 按 mode 反向清理，支持 `--dry-run`/`--force` |
| `config-templates/default/` | 新增 | settings.json 模板 + 4 个 hook + CLAUDE.md |
| `skills-cache/` | 新增 | 15 个 CC skill，git tracked |
| `templates/pre-commit` | 修改 | 新增 install.sh/uninstall.sh 保护 |
| `tests/` | 新增 | 17 文件 60 用例，Docker 测试框架 |

---

## 兼容性

**向前兼容**：旧的 `bash install.sh <路径> --tech-stack python` 用法不变，效果等同于 `--mode full --scheduler systemd`。

**新增参数**：`--mode`、`--home`、`--user`、`--scheduler`、`--no-config`、`--no-skills`、`--skip-root`、`--dry-run`、`--force`、`--update`。

---

## 典型场景

### 场景 1：本地开发机

```bash
git clone https://github.com/douxt/ai-dev-flow-server.git /tmp/devflow
bash /tmp/devflow/install.sh ~/my-project --mode frontend
```

### 场景 2：NAS / Docker 容器

```bash
# 容器内（coder 用户，$HOME=/home/coder）
bash install.sh ~/my-project --mode frontend --home /home/coder
```

### 场景 3：VPS 后端节点

```bash
bash install.sh /opt/my-project --mode backend --scheduler cron --user www
```

### 场景 4：预览变更

```bash
bash install.sh ~/my-project --mode full --dry-run
```

### 场景 5：升级已有安装

```bash
cd /opt/ai-dev-flow-server && git pull    # 先更新安装器本身
bash install.sh ~/my-project --update      # 只更新已有组件的文件
```

### 场景 6：卸载

```bash
bash uninstall.sh ~/my-project --mode full --force
bash uninstall.sh ~/my-project --mode frontend --dry-run  # 先预览
```

---

## 注意事项

1. **`.gate-state` 永不覆盖**：`--force` 也不会覆盖，防止丢失 Gate 进度
2. **`--update` 只更新已有文件**：不会引入新模式的文件。如需切换模式，用完整安装命令
3. **Docker 持久化**：容器内自动创建 `~/.claude → ~/.config/claude` symlink。确保 `~/.config` 挂载了持久卷
4. **CC skills 离线缓存**：版本跟随 repo。定期运行 `skills-cache/sync-skills.sh` 同步最新 skill
5. **首次使用**：安装后检查 `.devflow/config.yaml`，填写 telegram 配置（如需通知功能）

---

## v2.1 — 计划防覆盖 + 决策持久化（2026-07-01）

### 新增
- **plan-backup hook**：每次 Edit/Write 计划文件时自动 git 备份到 `~/.claude/plans/.git-backup/`
- **CLAUDE.md 模板追加 Agent B 权限边界**：明确 B 在业务项目可 merge PR、在管线框架只读、改管线走 handoff
- **CLAUDE.md 模板追加计划管理规则**：不覆盖旧计划、关键决策提取 ADR、ADR 格式规范

### 修改
- `config-templates/default/hooks/plan-backup.sh` — 新增
- `config-templates/default/settings.json` — PostToolUse 注册 plan-backup
- `config-templates/default/CLAUDE.md` — 追加计划管理段

### 已知约束
- hook 内部使用 `$HOME/.claude/plans/` 硬编码路径，Docker 依赖 `~/.claude` symlink。若未来部署修改 `__CLAUDE_HOME__` 指向且不走 symlink，所有 hook（含 audit-log/file-guard/bash-firewall）均需同步适配

### 影响
- 所有通过 install.sh 新安装的项目自动获得计划防覆盖能力
- 已有项目用 `bash install.sh <项目> --update` 可增量更新
- install.sh 无需修改 — hook 目录整体复制，新增文件自动跟随

---

## v3.3 宪法外部引用声明（2026-08-21）

> 租户反馈 FEEDBACK-003：spec 借鉴外部项目可能照抄历史遗留，无制度性拦截。

### 新增
- **Spec 宪法第 10 条扩展**：引入外部项目模式须声明 ①来源（项目+版本/日期）②借鉴了什么 ③与本项目约束的差异点及裁剪理由
- **check_constitution.py 第 16 项 `16.external_ref`**：检测外部项目引用信号（github.com URL / 星标 / 借鉴类动词），无来源声明 → warning
- **Ticket 宪法同步**：04 宪法第 16 行 + 速查卡；issue-template 自检清单第 17 条

### 影响
- `--update` 传播至所有已安装项目（check_constitution.py + 宪法 + issue-template + AGENTS.md）

---

## v3.4 门禁生效性修复（2026-08-27）

> UMES3 配置体检缺陷报告：三门禁 hook 自部署起 100% 未生效（P0）+ file-guard 自保护死代码（P0）+ skills .bak 洪水（P1）。

### 修复
- **三门禁 hook 吸收 UMES3 修复版**：stdin JSON 取参（旧 $1/$2 与 CC 协议不符）、exit 2 阻断语义、session_id 提取、函数定义序、heredoc 展开、gate 输出转 stderr
- **file-guard 模板重写**：stdin 取参 + 安全配置自保护 case 前置于豁免（原死代码）+ exit 1→2，无个人路径依赖
- **执行位**：模板 hooks 全部 755；install.sh 部署后显式 chmod（裸路径注册的 hook 必须可执行）
- **.bak 洪水**：skill 目录级备份移出 `skills/` 扫描根至 `~/.claude/.skill-backups/`（CC 不再误加载为真实 skill）；文件级/目录级同目标只留最新 1 份；旧式残留自动迁出；安装输出备份统计
- **文档措辞**：模型路由表注明第三方网关档位语义；Git 约束对齐 wt worktree 实践（PR 为 AFK 管线可选通道）

### 新增
- **安装后 hook 自检**（selftest_hooks，5 用例）：stdin JSON 模拟真实调用断言退出码，jq 缺失 SKIP，.emergency-bypass 存在时 workflow-gate SKIP
- **stdin 协议 bats**（tests/hooks/gate-hooks-stdin.bats，19 用例，GNU 镜像运行）；对照实验证明有效性（旧模板 19 挂）
- run_tests.sh 纳入 tests/hooks/*.bats（ubuntu 镜像）

### 已知约束
- 修复版 workflow-gate/test-gate-block 依赖 `grep -oP`（GNU）——busybox 环境静默失效，跨平台兼容待评估（roadmap DEFECT-001）

## v3.5 stacks 知识保鲜 M0（2026-08-28）

> FEEDBACK-002 M0 落地（调研见 roadmap 阶段二）：元数据 + 过期可见，stale 只标不删。

### 新增
- **stacks 元数据**：12 个 `knowledge/stacks/*/*.md` 头部 `>` 块注入 `reviewed_at: __REVIEWED_AT__` + `status: current`；install.sh 部署时（update/fresh 两处）将占位符刷为当天日期——**语义 = 每次部署即"最新知识待重审"，租户手工改的 reviewed_at 与 status 会被下次 --update 重置**（重审流程归 M2）
- **green-gate G2.5**（warning 档）：扫 `.devflow/knowledge/stacks/*/*.md`（SCRIPT_DIR 锚定），`reviewed_at` 早于 90 天 → 逐文件提示待重审；缺元数据不判；busybox `date -d` 不支持时静默跳过不误报；`GREEN_GATE_REVIEW_THRESHOLD=YYYY-MM-DD` 可覆盖阈值；成功文案同步 G2.1-G2.5
- 注意：--update 时 stacks 文件（含占位符模板 vs 已部署真实日期）cmp 必不等，每文件产生 1 个轮换 `.bak-*`（同目标只留最新 1 份，属预期）

### 修复（merge 折叠短路 + chmod 穿透，UMES3 问题五真根因）
- `merge-settings.py`：**两侧聚合同名 matcher**（此前只聚合 existing 侧，而模板自身含 3 个 `Edit|Write` 组 → 折叠结果被复制 N 次、自定义 matcher 原样透传，三胞胎永不清零）。现每 matcher 恰输出一组；真实 UMES3 数据实测 3 组→1 组
- `install.sh`：`chmod_x_nonsymlink` 统一替换用户级/项目级 hooks chmod 三处（DEFECT-004，chmod 沿 symlink 穿透篡改 claude-config 源 git mode）；fresh `--force` 遇 symlink 跳过不穿透
- 新增 `tests/unit/test_merge_settings.bats`（4 用例 + 自定义 matcher 折叠；容器无 python3 时 skip）；**双镜像 Dockerfile 补 python3**（merge-settings.py 是 python SUT，此前测试镜像根本跑不到）
- 勘误教训：8/28 回执"重跑 install 即折叠"系单组 9-hooks fixture 假阳性验证（未覆盖真实"3 独立同 matcher 组"形态）——幂等修复的测试 fixture 必须以**真实环境数据形态**构造

### 修复（selftest 盲区，UMES3 8/28 补记提醒②）
- `selftest_hooks._st` 改**裸路径直调**（原 `bash <script>`）——与模板注册形态一致，「部署丢执行位 → exit 126 静默崩溃」从盲区变可测；模板侧维持"裸路径 + 755 + 部署 chmod + selftest 裸调"四重防线，不改 bash 前缀注册（理由见 issues 回执）

### 修复（测试基建，DEFECT-002 扩展）
- workflow-gate.bats / test_plan_backup.bats **HOME 沙箱化**：前者 teardown/touch 原会删改真实 `~/.claude/.emergency-bypass`，后者 setup 的 `rm -rf "$HOME/.claude/plans/.git-backup"` 在宿主直跑 bats 调试时属破坏性删除——现全部落 mktemp 沙箱
- stacks-freshness.bats（6 用例双镜像）；其 inject 用例逮修 `inject_stacks_reviewed_at` 在 set -e 下末文件 grep 不中返回 1 崩溃 install 的缺陷
