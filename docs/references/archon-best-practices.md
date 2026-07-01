# Archon 最佳实践手册

@author: Claude Code
@created: 2026-06-22
@source: Archon 官方文档、社区实践、Cole Medin 系列项目

---

## 一、设计哲学

> **Agent = Model + Harness**
> 两个团队用同一个模型，完成率差距可达 60% vs 98%，差距就是 harness 质量。

Archon 的职责是管**流程**——Plan → Implement → Test → Review → PR，每一步都确定、可重复、可审计。AI 只管每一步的**智能决策**。

---

## 二、Workflow 设计最佳实践

### 2.1 黄金法则

| # | 法则 | 说明 |
|---|------|------|
| 1 | **AI 节点 + 确定性节点交替** | AI 产出后，bash 节点做验证，不依赖 AI 自检 |
| 2 | **loop 必加 fresh_context** | 每轮迭代新会话，上下文零污染 |
| 3 | **审批门放验证之后** | 人审的是已验证过的代码，不是半成品 |
| 4 | **一个 workflow = 一个任务** | 不批处理，每个 issue 独立跑 |
| 5 | **workflow 文件入 Git** | `.archon/workflows/` 版本控制 |

### 2.2 经典六节点管道

```yaml
plan → implement(loop) → validate(bash) → review → approve(interactive) → create-pr → mark-done(bash)
```

### 2.3 四种节点类型

| 类型 | 用途 | 示例 |
|------|------|------|
| `prompt` | AI 推理/编码 | `prompt: "实现认证模块"` |
| `bash` | 确定性操作 | `bash: "uv run pytest"` |
| `loop` | 迭代直到完成 | `loop: ... until: ALL_TASKS_COMPLETE` |
| `approval` | 人工审批 | `interactive: true` |

### 2.4 常见反模式

| 反模式 | 后果 | 修正 |
|--------|------|------|
| 全 AI 节点，无 bash 验证 | AI 自以为通过，实际没测 | 加 `bash: "pytest"` |
| 无审批门直接 push | 未审查代码进 main | `interactive: true` |
| loop 不加 `fresh_context` | 上下文污染，越跑越差 | `fresh_context: true` |
| 一个大 prompt 做所有事 | 不可审计、不可复现 | 拆成多个单职责节点 |
| 无 `max_iterations` | 无限循环烧预算 | 设硬上限 |

---

## 三、Claude Code 客户端最佳实践

### 3.1 核心规则

**给 CC 一个自验证闭环**——如果它能自己跑测试、看截图、验证结果，它会迭代到正确为止。

| 场景 | 验证方式 |
|------|---------|
| 后端 | `uv run pytest` |
| 前端 | Archon Chrome Extension 可视化 |
| 通用 | `/simplify` 检查代码质量 |

### 3.2 上下文管理（最关键）

```
手动 /compact 在 50% —— 不要等自动压缩
60-70% 上下文 → "Agent 昏迷区"：漏指令、犯低级错误
用 /statusline 实时监控
跑偏时 Esc Esc 回退，不要在污染上下文里纠正
```

### 3.3 CLAUDE.md 守则

```
理想 60 行，硬上限 300 行
只写 CC 无法从代码推导的：构建命令、分支约定、架构决策
用 <critical> 标签标记不可协商的规则
长规则拆分到 .claude/rules/ 按需加载
```

### 3.4 高效 Prompt

| 场景 | 用法 |
|------|------|
| 推进质量 | *"用你现在知道的一切，扔掉这个重新实现优雅方案"* |
| 强制自证 | *"证明给我看这能跑"* |
| 合并前审查 | *"grill 这些改动，不过关不许 PR"* |
| 修 bug | 直接贴错误 + 说 **"fix"**（别 micromanage，成功率 80%+） |

### 3.5 并行开发

```bash
# 3-5 个隔离 worktree 同时跑
claude --worktree
# 大迁移
/batch migrate src/ from Solid to React  # 扇出 N 个 agent
```

---

## 四、服务端部署最佳实践

### 4.1 运行模型

```
Archon (Node.js) → spawn Claude Code CLI (子进程)
  → cc-stack 代理 → DeepSeek / Qwen
```

- Archon 不直接调 API，通过 SDK spawn CC CLI
- CC CLI 通过 `ANTHROPIC_BASE_URL` 走你的代理
- 每个 workflow run 一个独立 worktree

### 4.2 端口规划

| 端口 | 服务 | 用途 |
|------|------|------|
| 8420 | Archon serve | workflow 引擎 + Web UI |
| 8421 | 审批看板 | 统一 Kanban |
| 3457 | cc-stack | 模型路由 |

### 4.3 资源

```bash
# 单 task 执行：
#   - 1 个 CC CLI 子进程（~200MB）
#   - 1 个 git worktree（~50MB）
# 并行 3 个 task → ~750MB 峰值
# 建议：1C 2GB VPS 足够
```

### 4.4 定时维护

```bash
# crontab
*/30 * * * * cd /opt/maf-hub && bash dispatch.sh   # 派发
0 3 * * *   cd /opt/maf-hub && archon isolation cleanup  # 清 worktree
0 4 * * *   cd /opt/maf-hub && archon workflow cleanup 30  # 清旧记录
```

### 4.5 systemd 模板

```ini
[Service]
Restart=always
RestartSec=5
# Archon crash 自动重启
# 审批看板 crash 自动重启
# 两个服务独立，互不影响
```

### 4.6 安全

- Tailscale 加密隧道 + 认证 → 不需要额外密码
- 看板和 Archon 都只监听内网（`127.0.0.1` 或 Tailscale IP）
- 不要暴露到公网

---

## 五、关键数字

| 指标 | 数据 |
|------|------|
| 良好 harness 的接受率 | 维护任务 74-92%，复杂功能 35-65% |
| Stripe 周 AI PR 数 | 1,300+（零人类编写代码行） |
| Archon 内置 workflow | 17 个 |
| 推荐并行 task 数 | 3-5 个 |
| CC 客户端上下文压缩线 | 50% manual，70% 必须 |

---

## 六、踩坑清单

| 坑 | 现象 | 解决 |
|----|------|------|
| bash 节点用 `$1` 而非 `$ARGUMENTS` | 变量为空 | bash 节点用环境变量 `$ARGUMENTS` |
| loop 不加 `fresh_context` | 后面任务质量崩 | 加 `fresh_context: true` |
| dispatch.sh 不写 run ID | 审批看板找不到对应 workflow | dispatch 写 `archon_run` 到 issue |
| 审批看板调 Archon REST API | API 不稳定 | 改用 `archon workflow approve <id>` CLI |
| `archon workflow run` 阻塞 dispatch | 排队卡死 | 用 `--detach` 后台跑 |
