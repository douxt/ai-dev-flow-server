# AFK 脚本栈规范（服务器版）

> 关联文档：
> - [05-脚本质量宪法](05-脚本质量宪法.md) — 12 项运行时安全与健壮性规则
> - [02-Step-Gate流程](02-Step-Gate流程.md) — 流程编排

## 一、脚本清单

| 脚本 | 角色 | 执行者 | 调用方式 |
|------|------|:------:|----------|
| `dispatch.sh` | AFK 调度器：扫描 ready issue → 宪法检查 → 原子抢占 → 启动 Archon | systemd timer | `bash dispatch.sh <project_path>` |
| `reconciler.sh` | 状态修复器：检测卡住/孤儿 issue → 状态回收 | systemd timer | `bash reconciler.sh <project_path>` |
| `auto-execute-afk.yaml` | Archon 工作流：TDD 实现→测试→双模型审查→PR | dispatch.sh 调用 | `archon run auto-execute-afk <issue_file>` |
| `check_constitution.py` | 7 项机器可检查规则（派发前阻断） | dispatch.sh 调用 | `python3 check_constitution.py <issue> --json` |
| `cost_tracker.py` | 耗时+费用追踪 | dispatch.sh 调用 | `python3 cost_tracker.py log/logs --summary` |
| `notify.py` | Telegram 通知（审批/异常） | dispatch.sh / reconciler.sh 调用 | `python3 notify.py <消息>` |

### 脚本间调用关系

```
dispatch-<project>.timer（每 5 分钟）
  → dispatch.sh <project_path>
    → check_constitution.py <issue> --json    # 宪法前置检查
    → archon run auto-execute-afk <issue>     # 启动工作流
    → cost_tracker.py log --start <issue>     # 记录开始
    → (Archon 完成)
    → cost_tracker.py log --end <issue>       # 记录结束
    → notify.py "Issue #N 完成，待审批"        # Telegram 通知

reconcile-<project>.timer（每 15 分钟）
  → reconciler.sh <project_path>
    → 扫描 in_progress >6h 无活动 → 回收
    → notify.py "Issue #N 超时回收"
```

## 二、配置约定

### config.yaml（`.devflow/config.yaml`）

所有脚本从 `.devflow/config.yaml` 读取项目配置：

```yaml
project:
  name: my-project
  repo_url: git@github.com:user/my-project.git
  workspace: /opt/my-project

tech_stack:
  language: node
  package_manager: npm
  test_command: npm test
  lint_command: npm run lint

dispatch:
  branch_prefix: ai/
  max_retries: 3
  poll_interval_min: 5

review:
  cross_review: false
  constitution_check: true

notify:
  telegram_chat_id: "..."
  telegram_bot_token: "..."
```

## 三、dispatch.sh 规范

### 3.1 执行流程

```
[1/6] 扫描 issues/ 找第一个 status: ready（跳过 HITL，跳过 blocked_by 未满足）
[2/6] check_constitution.py --json 7 项机器检查
[3/6] 通过 → 原子抢占（ready → in_progress），git commit + push
[4/6] archon run auto-execute-afk <issue_file>
[5/6] 成本追踪记录
[6/6] notify.py 通知 Telegram
```

### 3.2 分支安全约束

- 只推 `ai/<###>-<desc>` 前缀分支
- push 前先 pull --rebase
- 禁止 force push
- 禁止修改 master/main

### 3.3 重试上限

同一 issue 最多 3 次自我修复尝试。超出后标记 `failed`，notify.py 告警。

## 四、reconciler.sh 规范

### 4.1 状态回收规则

| 状态 | 触发条件 | 操作 |
|------|---------|------|
| in_progress → ready | >6h 无 git 活动 | 回收，下次重新抢占 |
| failed → backlog | >24h | 回收，等待人工重新评估 |

### 4.2 孤儿检测

- in_progress 但对应 ai/ 分支不存在 → 回收为 ready
- in_progress 但 git 无对应 commit → 回收为 ready

## 五、auto-execute-afk.yaml 规范

Archon 7 节点工作流：

```
implement → validate → auto-review → cross-review → merge-reviews → create-pr → mark-in-review
```

### 各节点职责

| 节点 | 职责 | 类型 |
|------|------|:---:|
| implement | TDD 实现 AC，禁止扩范围 | LLM |
| validate | 跑测试套件，输出 tail -30 | bash |
| auto-review | DeepSeek 自审（安全/性能/可维护性） | LLM |
| cross-review | Qwen 交叉审查（需 mini-router 在线，否则跳过） | bash |
| merge-reviews | 对比双模型审查结论，综合评分 | LLM |
| create-pr | 推分支 + gh pr create | LLM |
| mark-in-review | 更新 issue status → in_review，git push | bash |

### implement 节点约束

```
严格只实现 AC 列出的内容，禁止修改无关文件、禁止顺手重构、禁止加额外功能。
```

## 六、check_constitution.py 规范

7 项机器可检查规则：

| # | 规则 | 检查方法 |
|:-:|------|------|
| 1 | estimate ≤1d | 解析 frontmatter，值 ≤8h 或 ≤1d |
| 2 | type 正确 | AFK 或 HITL |
| 3 | effort 已声明 | 数字+单位 |
| 4 | blocked_by 字段存在 | frontmatter 含 blocked_by |
| 5 | needs 字段存在 | frontmatter 含 needs_llm/vision/pdf 等 |
| 6 | test_files 已指定 | 路径字段非空 |
| 7 | status 为 ready | frontmatter status: ready |

输出 JSON：`{"pass": true/false, "checks": {...}, "errors": [...]}`。fail 时 dispatch 阻断派发。

## 七、已知陷阱与防护

| 陷阱 | 现象 | 防护 |
|------|------|------|
| dispatch.sh 找不到 issue | `NO_MORE_TASKS` 但明明有 ready | 用 `issues/ --include="*.md"` 递归搜索 |
| blocked_by 未满足 | 抢了依赖未完成的 issue | check_constitution 检查 blocked_by |
| git push 冲突 | dispatch 推失败 | push 前先 pull --rebase |
| Archon 超时 | implement 节点卡死 | dispatch.sh 设 timeout，超时标记 failed |
| Telegram token 过期 | 通知发不出 | notify.py 失败时写本地 log 兜底 |
| 多 dispatch 并发 | 两个 dispatch 抢同一 issue | 原子抢占通过 git push 竞态实现（先 push 者胜） |
