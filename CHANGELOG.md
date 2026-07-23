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
