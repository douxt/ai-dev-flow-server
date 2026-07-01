# MAF-Hub — 完整实施计划 v4.1

@author: Claude Code
@created: 2026-06-22
@updated: 2026-06-23
@workflow: 最终方案（已 grilled）

## 关键决策汇总

| # | 决策 | 结论 |
|---|------|------|
| 1 | 执行引擎 | Archon 替代 ralph，Phase 3 部署 |
| 2 | 前段聊天 | OpenLobby，Phase 2 部署 |
| 3 | 审批看板 | 自建 FastAPI + htmx，~380 行，统一 UI |
| 4 | 数据交换 | 全走 Git，issue 格式不变 |
| 5 | 前/后段隔离 | align workflow（人驱动）+ auto-execute workflow（机器驱动），两份独立 |
| 6 | 宪法检查 | 机器检查 15 条 + LLM 判断 9 条 + 人终审 2 条，一次性准入，写入 issue 的 `constitution: passed` |
| 7 | 轻重分流 | execute-light 单节点，简单改动跳过完整流程 |
| 8 | 每个 Gate | `interactive: true`，自然语言控制跳过/重来 |
| 9 | 模型路由 | cc-stack 代理透明生效，Archon `model` 字段指定 |
| 10 | 派发机制 | dispatch.sh + flock + cron 5min + 人点 ready 即时触发 |
| 11 | 审批门超时 | 不设超时，Archon 暂停时不占资源 |
| 12 | mark-done 推送失败 | 重试 3 次 + 退避，最终失败不阻断，reconciler 兜底 |
| 13 | 双数据源同步 | Archon 实际状态为权威源，reconciler 每 5 分钟同步 issue |
| 14 | 审批卡片 | 摘要（文件列表+AI审查+测试）+ 外链 Gitee PR diff |
| 15 | PR 状态展示 | done 列卡片调 Gitee API 获取 open/merged/closed |
| 16 | 备份 | 当前 Git 即可，后期再考虑 |

---

## 零、开发流程固化（Archon Workflow 编码）

将 MAF-Hub 现有的 AI 开发流程（8 个 Gate +14 项宪法）编码为 Archon workflow。轻重分流，自然语言控制。

### 流程总览

```
简单改动              标准流程                大型项目
────────              ────────                ────────

一句话描述              完整对齐                全 Gate 走完
  │                      │                      │
  ▼                      ▼                      ▼
execute--light       align → execute          align → execute
  单节点实现           grill→PRD→issues          → review → retro
  自动通过              每个 Gate 人审批          每步可跳过
```

每个 Gate 都是 `interactive: true`，人可以说：
- `"通过"` / `"ok"` → 进入下一 Gate
- `"跳过"` / `"skip"` → 跳过当前 Gate
- `"重来"` / `"再看一遍安全性"` → 回到当前 Gate
- `"直接出 PRD"` → 跳到指定 Gate

### Workflow 1：align（对齐阶段）

```
Gate 1: grill-me
  prompt: 读取需求，逐项提问对齐
  interactive: true         ← 人回答每个问题

Gate 2: to-prd
  depends_on: [grill]
  prompt: 基于对齐结果生成 PRD
  interactive: true         ← 人扫描，确认 Out of Scope

Gate 3: to-issues
  depends_on: [prd]
  prompt: 按 PRD 拆分 issue，对照 14 项宪法
  loop:
    until: CONSTITUTION_PASS
    fresh_context: true
    max_iterations: 3

Gate 4: constitution-check
  depends_on: [to-issues]
  prompt: |
    逐条对照 14 项质量宪法检查每个 issue。
    输出不通过的条目和原因。
    通过则输出 <promise>ALL_PASS</promise>
  loop:
    until: ALL_PASS
    max_iterations: 3
    fresh_context: true

Gate 5: approve-issues
  depends_on: [constitution-check]
  interactive: true         ← 人最终审批 issue 列表
  prompt: "展示全部 issue + 宪法检查结果。人确认后标记 ready。"
  宪法检查是一次性准入审查——通过后 issue frontmatter 加 `constitution: passed`。
  后段 execute 不再重复检查。
```

### Workflow 2：execute（执行阶段）

```
Gate 6: implement
  prompt: |
    读取 $1（issue 路径）。
    TDD 实现：先写失败测试 → 最小实现 → 重构。
    每个 AC 独立提交。失败最多重试 3 次。
  loop:
    until: ALL_ACS_DONE
    fresh_context: true
    max_iterations: 10

Gate 6b: verify
  depends_on: [implement]
  bash: "uv run pytest tests/ -x"

Gate 6c: auto-review
  depends_on: [verify]
  prompt: |
    用安全/性能/可维护性三个角度审查 diff。
    输出问题列表。如无问题输出 <promise>CLEAN</promise>。

Gate 6d: approve-implementation
  depends_on: [auto-review]
  interactive: true
  prompt: "展示改动 + 审查结果。人审批。"

Gate 6e: create-pr
  depends_on: [approve-implementation]
  prompt: "推送并创建 PR。"

Gate 6f: mark-done
  depends_on: [create-pr]
  bash: |
    sed -i 's/^status: in_progress/status: done/' "$ARGUMENTS"
    cd /opt/maf-hub && git add "$ARGUMENTS" && git commit -m "done: $(basename "$ARGUMENTS")" && git push
```

### Workflow 3：review（审查+复盘）

```
Gate 7: code-review
  prompt: /code-review 检查代码质量
  interactive: true

Gate 7b: security-review
  depends_on: [code-review]
  prompt: /security-review 检查安全问题
  interactive: true

Gate 8: retro
  depends_on: [security-review]
  prompt: |
    总结本次开发：什么做对了、什么踩坑了、
    宪法是否需要更新。
  interactive: true
```

### 轻量路径

```yaml
# .archon/workflows/execute-light.yaml
# 简单改动：跳过 align + review，直接实现
nodes:
  - id: implement
    prompt: |
      用户请求：$USER_MESSAGE
      如果是小改动（typo、单文件修改、简单配置），直接改。
      改动超过单文件 → 问人是否走标准流程。
    interactive: true
```

### 触发方式

```bash
# 标准流程
archon workflow run align "实现用户认证模块"

# 轻量
archon workflow run execute-light "修 README 错字"

# 跳过 align，直接执行已有 issue
archon workflow run execute "issues/phase2-compiler/020-review-types.md"
```

---

## 架构总览

```
手机浏览器
  ├─ OpenLobby（:3001）         ← 前半段：聊天/grill/PRD/issues
  │   ├─ 多会话 CC               ← 每个会话独立 session ID
  │   ├─ 会话状态：working / waiting / idle
  │   └─ 产出 issue → git push
  │
  ├─ 审批看板（:8421）           ← 中间：全局 Kanban + 审批
  │
  └─ Archon Web UI（:8420）      ← 后半段：执行监控

轻量云服务器
  ├─ OpenLobby    （:3001）  ← CC 多会话管理
  ├─ 审批看板      （:8421）  ← 自建 FastAPI
  ├─ Archon serve （:8420）  ← workflow 引擎
  ├─ dispatch.sh  （cron）    ← 扫 ready → 派发
  ├─ cc-stack     （:3457）  ← 模型路由
  └─ ralph        （过渡保留） ← 扫非试点 issue

数据流：全走 Git。OpenLobby 产 issue → push → 看板确认 → dispatch → Archon 执行。
```

---

## Phase 1：本地试点（2h）

### Step 1.1：安装

```bash
curl -fsSL https://archon.diy/install | bash
```

### Step 1.2：初始化

```bash
cd /home/dou/dev/MAF-Hub
archon init
```

### Step 1.3：选试点 issue

`issues/phase2-compiler/020-review-types.md`（0.5d，无依赖，AFK）

### Step 1.4：写 workflow（本地和服务器共用）

```yaml
# .archon/workflows/auto-execute.yaml
nodes:
  - id: implement
    prompt: |
      阅读 $1。
      按 AC 完成实现。写代码、写测试、跑通。
    loop:
      until: ALL_TASKS_COMPLETE
      fresh_context: true

  - id: validate
    depends_on: [implement]
    bash: "uv run pytest tests/ -x"

  - id: auto-review
    depends_on: [validate]
    prompt: "审查改动，按安全/性能/可维护性列出问题。"

  - id: approve
    depends_on: [auto-review]
    interactive: true
    prompt: "展示改动 + 审查结果，等待审批。"

  - id: create-pr
    depends_on: [approve]
    prompt: "推送分支并创建 PR。"

  - id: mark-done
    depends_on: [create-pr]
    bash: |
      sed -i 's/^status: in_progress/status: done/' "$ARGUMENTS"
      echo "PR: $create-pr.output" >> "$ARGUMENTS"
      cd /opt/maf-hub && git add "$ARGUMENTS" && git commit -m "done: $(basename "$ARGUMENTS")"
      for i in 1 2 3; do
        if git pull --rebase && git push; then exit 0; fi
        git push 2>&1 | grep -qE "rejected|403|auth" && exit 1
        sleep $((i * 5))
      done
      # 最终失败不阻断：PR 已创建，dispatch.sh 下次兜底
```

### Step 1.5：跑 + 验证

```bash
archon workflow run auto-execute "issues/phase2-compiler/020-review-types.md"
# 验证清单：
# □ CLI 输出格式（是否打印 run ID）
# □ $ARGUMENTS 在 bash 节点中的实际行为
# □ Web UI 自动打开 → 观察 → 审批 → 完成
```

### Step 1.6：决定

```
可行 → Phase 2
不可行 → rm -rf .archon/，继续全量 ralph
```

---

## Phase 2：OpenLobby + 审批看板（5h）

目的：手机可以完整操作前半段（多会话 CC 聊天/grill/PRD/issues）+ 全局 Kanban 审批。

### Step 2.1：部署 OpenLobby

```bash
ssh user@vps
# 已有 Node.js 22+
npx openlobby
# → http://vps-ip:3001，首次设密码
```

```ini
# /etc/systemd/system/openlobby.service
[Unit]
Description=OpenLobby Session Manager
After=network.target

[Service]
User=www
Environment=ANTHROPIC_BASE_URL=http://localhost:3457
Environment=ANTHROPIC_API_KEY=your-key
ExecStart=npx openlobby
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now openlobby
# → https://vps-name.tailnet-name.ts.net:3001
```

### Step 2.2：部署审批看板

```bash
cd /opt && git clone git@gitee.com:cybxcoder/maf-hub.git
cd maf-hub
pip install fastapi uvicorn pyyaml python-frontmatter
```

### Step 2.3：审批看板后端 `approval_board.py`（~150 行）

- 递归扫描 `issues/` → 解析 YAML frontmatter
- 3 个 API：`GET /api/issues`、`PUT /api/issues/{path}`、`GET /`
- 改 status → 自动 git commit + push
- 调 Archon CLI 获取运行状态 + approve/reject

### Step 2.4：审批看板前端 HTML（~250 行，内联模板）

- 四列 Kanban：draft | ready | in_progress | done
- 卡片嵌入 Archon 执行状态（节点进度）
- 审批门到达时，卡片展开摘要（改动文件列表、AI 审查评分+建议、测试结果）+ [Approve] [Reject] + [查看完整 PR diff →] 跳 Gitee——手机不嵌入完整 diff
- done 列卡片：读取 issue 中 `PR:` 字段 → 调 Gitee API 获取 PR 状态（open/merged/closed + CI 状态），30s 刷新时同步更新
- 移动端单列 + 横向滑动，每 30s 刷新

### Step 2.5：启动审批看板

```ini
# /etc/systemd/system/approval-board.service
ExecStart=uv run uvicorn approval_board:app --host 0.0.0.0 --port 8421
```

```bash
sudo systemctl enable --now approval-board
# → https://vps-name.tailnet-name.ts.net:8421
```

### Step 2.6：安全

Tailscale 统一隧道，三个服务都在 tailnet 内，不加额外密码。

### 端口总览

| 端口 | 服务 | 用途 |
|:---:|------|------|
| 3001 | OpenLobby | 多会话 CC 聊天 |
| 8421 | 审批看板 | 全局 Kanban + 审批 |
| 8420 | Archon | workflow 引擎（Phase 3 部署） |
| 3457 | cc-stack | 模型路由

---

## Phase 3：Archon 部署 + 过渡（3h）

### Step 3.1：安装

```bash
ssh user@vps
# Node.js 22+
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Archon（裸机安装）
curl -fsSL https://archon.diy/install | bash

# Claude Code CLI（SDK 会 spawn 它）
npm install -g @anthropic-ai/claude-code

cd /opt/maf-hub && archon init
cp /home/dou/dev/MAF-Hub/.archon/workflows/auto-execute.yaml .archon/workflows/
```

### Step 3.2：环境变量

```bash
# /opt/maf-hub/.env — 两个服务共用
ANTHROPIC_BASE_URL=http://localhost:3457    # cc-stack 代理
ANTHROPIC_API_KEY=your-key
ARCHON_PORT=8420
```

### Step 3.3：dispatch.sh

```bash
#!/bin/bash
# /opt/maf-hub/dispatch.sh
cd /opt/maf-hub && git pull

for f in $(grep -rl "^status: ready" issues/phase2-compiler/); do
  sed -i 's/^status: ready/status: in_progress/' "$f"
  git add "$f" && git commit -m "dispatch: $(basename $f)"

  # 后台派发
  archon workflow run auto-execute "$f" --detach
  sleep 1
  RUN_ID=$(archon workflow runs --json --limit 1 | jq -r '.[0].id')
  echo "archon_run: $RUN_ID" >> "$f"
  git add "$f" && git commit -m "link: $(basename $f) → $RUN_ID"
done

git push
```

**reconciler：** 所有 archon_run 非空但 status 还在 in_progress 的 issue，查 Archon 实际状态。不一致时 Archon 说了算——completed → done，failed → failed，paused → 保持。issue 文件是展示层，Archon 是权威源。

```bash
chmod +x dispatch.sh
# crontab：flock 防并发 + 每 5 分钟兜底
*/5 * * * * flock -xn /var/run/dispatch.lock -c 'cd /opt/maf-hub && bash dispatch.sh'
# 每天清理 worktree
0 3 * * * cd /opt/maf-hub && archon isolation cleanup
```

**立即派发**：审批看板改 status → ready 时，后端异步调 `dispatch.sh`。`flock` 保证并行不出冲突，加上 dispatch.sh 开头的 `git pull` 同步最新状态，不会重复派发。

### Step 3.4：启动

```ini
# /etc/systemd/system/archon.service
[Unit]
Description=Archon Workflow Engine
After=network.target

[Service]
User=www
WorkingDirectory=/opt/maf-hub
EnvironmentFile=/opt/maf-hub/.env
ExecStart=archon serve --port 8420
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now archon
```

### Step 3.5：ralph 不改

ralph 继续运行，扫 phase2-compiler 以外的 issue。过渡前把 phase2-compiler 里 `in_progress` 的 issue 手动清回 ready。

---

## Phase 4：过渡观察（1 周）

```
Archon 跑 phase2-compiler 的 7 个 issue
ralph 跑其他所有 issue
审批看板统一管理全局

观察指标：Archon 成功率、是否有冲突、审批体验
```

---

## Phase 5：全量切换（0.5h）

```bash
# dispatch.sh 扫全量
sed -i 's|issues/phase2-compiler/|issues/|g' dispatch.sh

# 停 ralph
# 删 cron 或 disable service
```

---

## Phase 6：自动 PR 审查（1h）

```yaml
  - id: auto-review-qwen
    depends_on: [validate]
    model: sonnet              # cc-stack → DeepSeek V4 Pro
    prompt: |
      用安全/性能/可维护性三个角度审查 diff。
      输出结构化问题列表。
```

---

## Phase 7：成本追踪（1h）

Archon 自动记录每次 run 的 token 用量。加一个脚本汇总到 issue 或定期输出报告。

---

## 开发量

| Phase | 内容 | 时间 |
|:---:|------|:---:|
| 1 | 本地试点 | 2h |
| 2 | OpenLobby + 审批看板 | 5h |
| 3 | 服务器部署 Archon | 3h |
| 4 | 过渡观察 | 1 周 |
| 5 | 全量切换 | 0.5h |
| 6 | 自动 PR 审查 | 1h |
| 7 | 成本追踪 | 1h |
| **合计** | | **11.5h** |

---

## 端口分配

| 端口 | 服务 | 用途 |
|:---:|------|------|
| 8420 | Archon | workflow 引擎 + Web UI |
| 8421 | 审批看板 | 统一 Kanban |
| 3457 | cc-stack | 模型路由代理 |

---

## 服务器组件清单

| 组件 | 运行方式 | 用途 |
|------|---------|------|
| Node.js 22+ | 裸机 | OpenLobby + Archon 运行时 |
| OpenLobby | systemd, :3001 | CC 多会话聊天 |
| Archon | systemd, :8420 | workflow 执行 |
| Claude Code CLI | npm global | SDK 子进程 |
| Python 3 | 裸机 | 审批看板 |
| cc-stack | systemd, :3457 | 模型路由 |
| Docker 项目 | 容器 | 不受影响 |

---

## 流程全景

```
1. 手机打开 OpenLobby → 创建会话 → 聊天/grill → 产出 PRD
   → /to-issues → 产出 issue 文件 → git push
2. 手机打开审批看板 → 看 issue 列表 → 拖到 ready → 自动 git push
3. dispatch.sh（cron 30min）→ git pull → 找到 ready → 标 in_progress
   → archon workflow run --detach → 写 run ID → git push
4. Archon 执行 → CC SDK spawn CLI → cc-stack 路由到 DeepSeek
   → implement → validate → auto-review → [审批门暂停]
5. 审批看板 30s 刷新 → 看到审批门 → 人点 [Approve]
   → 调 archon workflow approve <id> → Archon 继续
   → create-pr → mark-done（写 status: done）→ git push
6. 人审查 PR → merge
```

---

## 待验证项（Phase 1 解决）

- [ ] `archon workflow run` 的 stdout 输出格式
- [ ] `--detach` 后 `archon workflow runs --json` 能否立即拿到新 run
- [ ] `$ARGUMENTS` 在 bash 节点中的实际值（包含完整路径？）
- [ ] cc-stack 代理下 Archon 的 SDK 调用是否正常
