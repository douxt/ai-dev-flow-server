---
name: worktree-merge-lessons-20260717
description: 一次大规模 worktree 合并清理全流程踩坑与经验
metadata: 
  node_type: memory
  created: 2026-07-25
  source: stop-hook
  origin_session: d45c2e4d-a6ae-493e-8747-87a3f477d892
  type: feedback
  originSessionId: d45c2e4d-a6ae-493e-8747-87a3f477d892
---

---

# Worktree 堆积合并清理全记录

**日期**: 2026-07-17
**关联**: [[langbot-plugin-best-practices]] [[working-style-feedback]]

## 背景

bot 项目积压了 7 个未合并 worktree（最早 4 天前），涉及同文件 `default.py`（~1200行）的大量重叠改动。本次一次性全部合并、补齐测试、清理干净。

## 踩坑

### 1. 大改动搁置，小碎片先合 → 根因残留
- **表现**: 7/13 写了后台队列重构（+900行），但只合了 21 个小 fix。重构在 worktree 躺 4 天。
- **根因**: 大改动"太重"，审核畏难；小碎片容易审，跳队先合。
- **教训**: **大改动优先合**，它是基础；小碎片是治标。顺序不能反。

### 2. NAS 热修补不经过 git → 两边脱节
- **表现**: NAS 上有 face-unknown-fix 的代码（`_face_cache`），但 git main 没有；git main 有队列重构，NAS 没有。
- **根因**: 为了快速修复，直接把代码拷到容器里。
- **教训**: 所有改动必须走 git → merge → 部署，不能跳过 git。[[langbot-config-update-safety]]
- **排查方法**: `ssh root@nas "docker exec langbot grep -c '关键字' /path/file.py"` 对比两边特征。

### 3. 同文件多 worktree 并行 → 合并冲突地狱
- **表现**: 4 个分支同时改 default.py，合并时 24 处冲突。
- **教训**: **同一时间一个 worktree 原则**。修完立即合，不攒批。

### 4. 重复分支（bg-queue-refactor vs extract-quote-fix）
- **表现**: 两个分支从同一 merge-base 分出，前 5 个 commit 哈希完全相同。重复工作。
- **教训**: 如果需要继续在一个分支上工作，从该分支 checkout -b，不要从 main 重新开始。

### 5. 合并技术取舍
- `-X theirs` 丢掉了 main 的新修复 → 危险
- `--union` (git merge-file) 对纯增量改动有效，但可能产生碎片代码
- **最终方案**: 手动从 commit 提取纯增量逻辑块，逐个植入最新 main。工作量大但结果最干净。

### 6. 测试全部依赖 Docker → 部署前零验证
- **表现**: 8 个测试脚本全是 E2E，需要在容器里跑。本地改完代码只有语法检查。
- **修复**: 补齐 pytest 本地单测（81 tests），用 sys.modules patching 模拟 SDK。见 [[test-suite-design]]
- **教训**: 每个改动至少配 1 个本地可跑的测试。

## 正确流程

```
排查问题 → 修 → 测试 → 合并 → 部署 → 清理 worktree
                              ↑
                         这一步最容易遗忘
```

## 部署阶段补充经验

### 7. 烟雾测试必须在容器充分启动后运行
- **表现**: 第一次部署烟雾测试大量失败（/sync 超时、code=None）
- **根因**: 容器重启后 2 分钟才完全初始化，8 秒不够
- **教训**: 部署后等 10-15 秒，或主动检查 init.log。[[nas-deploy-and-smoke-test]]

### 8. 烟雾测试 DB 查询失效 → 改用 HTTP 验证
- **表现**: napcat 容器无法连接 langbot-plugin 的 SQLite
- **教训**: 跨容器测试只能用 HTTP API，不能直接访问对方文件系统

### 9. 测试层次：L1 本地单测 + L2 部署烟雾 + L3 E2E 回归
- 每层覆盖不同的风险面
- L1 改代码即跑，L2 部署即跑，L3 定期跑

**How to apply:**
1. 每天 `git wt-status` 检查未合并 worktree，超过 1 天不合并就是问题
2. file-guard hook 现在自动展示未合并列表，创建新 worktree 前会被提醒
3. 所有修改先合到 main，再从 main 部署到 NAS
4. 修改后跑 `uv run pytest tests/ -v`（本地 0.4s）
5. 部署用 `./deploy.sh`，自动跑烟雾测试验证
6. **修复完立即合并**，不等到"功能完整"
7. 大改动优先合，小碎片不要跳队
