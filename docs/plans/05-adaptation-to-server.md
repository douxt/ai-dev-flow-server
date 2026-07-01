# ai-dev-flow 服务器版：独立项目级开发约束

## 定位

独立子项目，和 MAF-Hub **同级**，不是 MAF-Hub 的一部分。

MAF-Hub 是 DevFlow 的前段基建（OpenLobby + Kanban + Telegram + mini-router），这个是**项目级开发流程约束模板**。每个新项目用模板一键装上 gate 流程 + AFK 管线。

```
MAF-Hub/              ← DevFlow 前段基建（服务端不变）
ai-dev-flow-server/   ← 项目级约束模板（新独立项目）
```

## Grill 决策记录

| # | 决策 | 结论 |
|:---:|------|------|
| 1 | Gate 0/5 装不装 | **全装 6 个**（适配后），Gate 0 在 .gate-state 标 passed |
| 2 | .gate-state 放哪 | **项目仓库**，不耦合 MAF-Hub |
| 3 | 项目独立性 | **独立仓库 ai-dev-flow-server**，和 MAF-Hub 同级 |
| 4 | Archon 模板差异（Python/Node/Go） | **显式 config 文件**，不用 CLAUDE.md 推断（不可靠） |
| 5 | install.sh 分权限 | **用户段**（www）+ **root 段**（手动），分离 |
| 6 | dispatch 是否查 gate 状态 | **半自动不查**，dispatch 只看 issue ready + 宪法 |

## 与 ai-dev-flow（本地版）的关系

| | ai-dev-flow 本地版 | ai-dev-flow 服务器版 |
|------|------|------|
| **运行环境** | 本地 CC 终端 | OpenLobby（手机浏览器） |
| **gate 触发** | 人敲 `/gate-X` | 人敲 `/gate-X`（路径适配后） |
| **AFK 执行** | `ralph-once.sh` 本地循环 | dispatch.sh + Archon workflow |
| **审批** | 无 | notify.py 直连 Telegram（token/chat_id 从 MAF-Hub 复制） |
| **部署方式** | `install.sh` 装到本地项目 | `install.sh` 装到服务器上的项目仓库 |

**复用**：gate 脚本逻辑（需改路径引用）、宪法文档、.gate-state 状态机、方法论
**替换**：后段（ralph-once.sh → dispatch.sh + Archon）
**新增**：config 文件、.timer 模板、notify.py、Archon workflow YAML

## 项目结构

```
ai-dev-flow-server/
├── README.md
├── install.sh                 # 一键安装（用户段 + root 段提示）
├── uninstall.sh               # 反向清理
├── config.example.yaml        # 项目配置模板（技术栈、仓库URL、分支策略）
├── templates/
│   ├── gate-state.yml         # .gate-state 模板
│   ├── CLAUDE.md.append       # 追加到项目 .claude/CLAUDE.md
│   ├── issue-template.md      # 含宪法检查表的 issue 模板
│   ├── dispatch.timer         # systemd timer 模板
│   └── reconciler.timer
├── workflows/                 # 从 ai-dev-flow 复制并适配路径
│   ├── gate-1-grill.js        # ✅ 不改（无硬编码路径）
│   ├── gate-2-prd.js          # 🔄 重定向宪法路径：ai-dev-flow/ → .devflow/knowledge/
│   ├── gate-3-issues.js       # 🔄 同上 + docs/requirements/ → docs/
│   ├── gate-4-review.js       # ✅ 不改（无硬编码路径）
│   ├── gate-5-prep.js          # 🔄 重定向宪法路径 + 替换 prep-once.sh → 检查 .devflow/ 完整性 + config.yaml 有效
│   └── gate-6-afk.js           # 🔄 重定向宪法路径 + 替换 ralph-once.sh → 确认 AFK 管线就绪，输出「ready issue 将被自动消化」
├── archon/
│   ├── auto-execute-afk.yaml  # 新建：通用版 Archon 工作流（模板变量从 config.yaml 读）
│   ├── dispatch.sh             # 新建：通用 AFK 调度器（读项目本地 issues/）
│   └── reconciler.sh           # 新建：通用状态修复器
├── scripts/
│   ├── check_constitution.py  # 新建：7 项机器可检查规则（其余 7 项 LLM 检查由 gate-4-review 的 /review-cc-cli 负责）
│   ├── cost_tracker.py        # 新建：耗时+费用追踪
│   └── notify.py              # 新建：直连 Telegram Bot API（复用 MAF-Hub 的 token/chat_id）
└── knowledge/                 # 从 ai-dev-flow 适配，保持独立文件（不合并）
    ├── 01-核心方法论.md        # 直接复制
    ├── 02-Step-Gate流程.md     # 🔄 重写服务器场景（dispatch+Archon 替代 ralph）
    ├── 03-PRD质量宪法.md       # 直接复制
    ├── 04-Issue质量宪法.md      # 直接复制
    ├── 05-脚本质量宪法.md       # 直接复制
    ├── 06-AFK脚本栈规范.md      # 🔄 重写服务器场景
    └── 07-防护体系.md           # 直接复制
```

> ⚠️ gate 脚本标注"不改"的指逻辑不改，仍需统一替换硬编码的知识文档路径（`ai-dev-flow/` → 项目内 `.devflow/knowledge/`）。

### Gate 服务器版行为

| Gate | 本地版 | 服务器版 | 改动 |
|------|--------|---------|:---:|
| **1** grill | 调 `/grill-me` 拷问需求 | 同左 | 无 |
| **2** PRD | 读宪法 → 调 `/to-prd` → 出口检查 | 同左（路径改为 `.devflow/knowledge/`） | 路径 |
| **3** Issues | 读 PRD+宪法 → 拆 issue → 17 项出口检查 | 同左（PRD 路径改为 `docs/`） | 路径 |
| **4** Review | 调 `/review-cc-cli --rubric plan` 评审 issues | 同左 | 无 |
| **5** Prep | 跑 `prep-once.sh` → 检查依赖/Docker/token | 检查 `.devflow/` 目录完整 + `config.yaml` 有效 + dispatch.timer 已激活 | 替换 |
| **6** AFK | 跑 `ralph-once.sh` AFK 循环 | 输出「AFK 管线就绪，ready issue 将由 dispatch.timer 自动消化」，人确认后标 passed | 替换 |

### 宪法检查分层

| 层 | 项数 | 谁做 | 何时 |
|-----|:---:|------|------|
| 机器确定 | 7 | `check_constitution.py`（estimate/type/effort/blocked_by/needs/test_files/status） | dispatch.sh 派发前 |
| LLM 辅助 | 7 | `/review-cc-cli`（在 gate-4-review 中调用） | 人执行 gate-4 时 |
| 人终审 | — | 审批看板 / Telegram 按钮 | in_review 后 |

## install.sh 做的事

```
install.sh <项目路径> [--tech-stack <python|node|go>] \   # 用户段（www 可执行）
            [--test-cmd <命令>] [--lint-cmd <命令>] [--pkg-mgr <npm|yarn|pnpm|uv|pip|cargo>]
  ├─ 0. 预检：目标路径是 git 仓库？CLAUDE.md 存在？issues/ 目录存在？测试套件存在？
  ├─ 1. 生成 .devflow/config.yaml（技术栈默认值 + 手动覆盖项写入）
  ├─ 2. 复制 workflows/ → ~/.claude/workflows/（处理后路径）
  ├─ 3. 复制 templates/.gate-state → 项目/.gate-state
  ├─ 4. 幂等追加 CLAUDE.md.append → 项目/.claude/CLAUDE.md（先 grep marker 查重）
  ├─ 5. 复制 archon/ + scripts/ + knowledge/ → 项目/.devflow/（注入 config.yaml 变量）
  ├─ 6. 复制 issue 模板 → 项目/issues/TEMPLATE.md
  ├─ 7. 输出检查清单：预检结果 + 下一步
  └─ 8. 输出 root 段命令（copy-paste 执行）

# --tech-stack 默认映射（均可通过 --test-cmd / --lint-cmd / --pkg-mgr 覆盖）
#   node  → pkg:npm,  test:npm test,      lint:npm run lint
#   python→ pkg:uv,   test:uv run pytest,  lint:uv run ruff check
#   go    → pkg:go,   test:go test ./...,  lint:go vet ./...

# root 段（手动）：
  ├─ 复制 .devflow/templates/dispatch-<project>.timer → /etc/systemd/system/
  ├─ 复制 .devflow/templates/reconcile-<project>.timer → /etc/systemd/system/
  ├─ systemctl daemon-reload
  └─ systemctl enable --now dispatch-<project>.timer reconcile-<project>.timer
```

> timer 命名用项目名前缀（如 `dispatch-openlobby.timer`），避免多项目冲突。

## 试点：OpenLobby 移动端适配

### 前置条件

```
# 人在 OpenLobby 执行（一次性的准备工作）
1. GitHub fork kkkkkk1k1/openlobby → douxt/openlobby
2. git clone git@github.com:douxt/openlobby.git /opt/openlobby
3. cd /opt/openlobby && npm install && npm run build
4. 确认 npm test 可通过（至少有一个测试）
5. 创建 .claude/CLAUDE.md（项目技术栈说明）
6. mkdir -p issues/ && touch issues/.gitkeep
```

### 流程

```
# 服务器上
cd ai-dev-flow-server
bash install.sh /opt/openlobby --tech-stack node
  → 预检 → config.yaml → gate 脚本 → .gate-state → .devflow/
  → 输出 root 命令

# root 粘贴执行
systemctl enable --now dispatch-openlobby.timer reconcile-openlobby.timer

# 人在 OpenLobby
创建会话 → cd /opt/openlobby
  → /gate-1-grill → 对齐需求
  → /gate-2-prd   → 出 PRD
  → /gate-3-issues → 拆 issue
  → 人拖 issue 到 ready → dispatch-openlobby 自动消化
  → Telegram 审批
```

## 和 MAF-Hub 的边界

| MAF-Hub 组件 | 状态 | 试点中角色 |
|------|:---:|------|
| **OpenLobby** (:3001) | ✅ 已部署 | 人在手机聊天交互 |
| **mini-router** (:3457) | ✅ 已部署 | 模型路由（试点仅直连 DeepSeek） |
| **Kanban** (:8421) | ⚠️ worktree 未合并 | 人拖拽 issue 状态。试点可暂用文件直接改 status |
| **Telegram Bot** | ⚠️ worktree 未合并 | 审批通知。notify.py 自带直连兜底 |

| 试点项目组件 | 来源 | 角色 |
|------|------|------|
| **ai-dev-flow-server** | 新独立仓库 | gate 流程 + AFK 管线（装到 /opt/openlobby） |
| **MAF-Hub dispatch 自身** | MAF-Hub | ❌ 试点不用，只消化 MAF-Hub 自己的 issues |

## 配置接口（config.yaml）

```yaml
# .devflow/config.yaml — install.sh 生成，dispatch/Archon 读取
project:
  name: openlobby
  repo_url: git@github.com:douxt/openlobby.git
  workspace: /opt/openlobby

tech_stack:
  language: node                # --tech-stack 设置
  package_manager: npm          # --pkg-mgr 覆盖
  test_command: npm test        # --test-cmd 覆盖
  lint_command: npm run lint    # --lint-cmd 覆盖

dispatch:
  branch_prefix: ai/
  max_retries: 3
  poll_interval_min: 5

review:
  cross_review: false          # 试点不用 Qwen 交叉审查
  constitution_check: true

notify:
  telegram_chat_id: "<从 MAF-Hub config/telegram.json 复制>"
  telegram_bot_token: "<同上>"
```

## 分支安全约束

dispatch.sh 在第三方项目中强制遵守：
- 只推 `ai/<###>-<desc>` 前缀分支
- push 前先 pull --rebase
- 禁止 force push
- 禁止修改 master/main
- create-pr 用 `gh pr create`（GitHub），不直接 merge

> 这些约束写入 dispatch.sh 自身，不依赖目标项目的 git hook 或 branch protection。

## 验证节点

| 步骤 | 验证 | 失败处理 |
|------|------|---------|
| install.sh 预检 | git repo? CLAUDE.md? issues/? 测试套件? | 输出缺失项清单，退出 |
| install.sh 完成 | `ls .devflow/` 完整 | 逐项检查 |
| root 段完成 | `systemctl is-active dispatch-*.timer` | `journalctl -u dispatch-*.service -n 20` |
| 首条消息 | OpenLobby 中 `ls` 看到项目文件 | 确认工作目录 |
| Gate 1 完成 | `.gate-state` 中 gate-1: passed | 重跑 gate-1 |
| AFK 首跑 | `dispatch.sh` 手动跑一次，确认 issue 被抢占 | tail -f logs/dispatch.log |

## 实施步骤

| # | 事项 | 内容 |
|:---:|------|------|
| 1 | 创建仓库 | `mkdir ai-dev-flow-server` → git init → 建完整目录结构 |
| 2 | 适配 gate 脚本 | 6 个 workflow → 统一替换 `ai-dev-flow/` → `.devflow/knowledge/`，gate-5/6 替换 prep-once/ralph 引用为 dispatch 指引 |
| 3 | 创建 AFK 管线 | 新写：dispatch.sh + reconciler.sh + auto-execute-afk.yaml + .timer 模板（不依赖 MAF-Hub 任何已有文件） |
| 4 | 创建 scripts | 新写：check_constitution.py（7项机器检查）+ cost_tracker.py + notify.py |
| 5 | 适配知识文档 | 7 份 .md → 02/06 重写服务器场景，其余保留 |
| 6 | 写 install.sh / uninstall.sh | 含预检、幂等、变量注入、分权限段 |
| 7 | 试点验证 | install.sh → /opt/openlobby → 走通全流程 |

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| OpenLobby 会话能否 `cd /opt/openlobby` 未验证 | 试点前手动测试：在 OpenLobby 敲 `ls /opt/openlobby` |
| 1C 2GB 服务器多项目共存资源不足 | 试点阶段仅 1 项目，AFK 限制并发 1；多项目前升级或迁移 Phase 6 (NAS) |
| Kanban 不支持多项目 | 试点手动改 issue status 文件，后续 Kanban 增加 `--issues-dir` 参数 |
| Kanban / Telegram Bot 代码在 worktree 未合并 | 试点前从 worktree 合并到 MAF-Hub master 并部署 |
