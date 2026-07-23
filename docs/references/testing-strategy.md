# DevFlow 测试策略 v3.0

## 分层架构

```
L1 单元测试（bats + pytest，每 Phase 同步交付）
  ├── hooks/workflow-gate.bats（9 用例）— PreToolUse 入口拦截
  ├── hooks/stage-tracker.bats（6 用例）— PostToolUse 产物检测
  └── check_constitution/（pytest，25+ 用例）— 15 项机器检查

L2 集成测试（bats，Phase 4）
  ├── routing.bats（17 用例）— CLAUDE.md 路由规则验证
  ├── hook-chain.bats（6 用例）— workflow-gate→stage-tracker→trace 链
  ├── migration.bats（13 用例）— v2→v3 gate-state 迁移
  ├── escape.bats（7 用例）— 逃生机制
  └── rollback.bats（6 用例）— 回滚验证

L3 安装器测试（bats，Docker，现有）
  ├── test_mode_*.bats（3 文件）— full/frontend/backend 三种模式
  ├── test_update.bats（4 用例）— --update 升级路径
  ├── test_role_*.bats（4 文件）— owner/developer/agent-b 角色
  └── test_*（10+ 文件）— legacy/idempotency/uninstall 等

L4 端到端（半人工）
  └── 真实项目走通标准路径：Plan Mode → grill → spec → tickets → implement → PR
```

## 覆盖目标

| 组件 | 目标 | 验证类型 |
|------|:---:|:---:|
| workflow-gate hook | 100% 分支覆盖 | 确定性 (exit code) |
| stage-tracker hook | 100% 分支覆盖 | 确定性 (文件输出) |
| check_constitution.py | >90% 行覆盖 | 确定性 (stdout/JSON) |
| install.sh 迁移路径 | 3 场景 × 3 模式 | 阈值型 (全通过) |
| hook 链串联 | 完整路径 + 异常路径 | 确定性 (trace 日志) |
| 逃生机制 | 创建/删除/恢复 | 确定性 (exit code) |

## 运行方式

### Docker（CI/完整验证）

```bash
bash tests/run_tests.sh              # Alpine + Ubuntu 双发行版，全量
bash tests/run_tests.sh -f "update"  # 过滤单个测试
```

### 本地（快速迭代）

```bash
# 需要 bats 框架
export REPO_ROOT=$(pwd)
bats tests/integration/routing.bats
bats tests/integration/migration.bats
# ...
```

## 已知限制

- **Docker 网络依赖**：测试运行依赖 `bats/bats:latest` 镜像，需 Docker Hub 可达
- **python-frontmatter**：check_constitution 需要此依赖，缺失时相关测试自动 skip
- **全局 git hooks 干扰**：本地运行需 `BYPASS_WT_CHECK=1` 绕过 pre-commit hook
- **systemd 输出**：安装器 root 段打印 systemd unit 文件（不实际写入），测试忽略该输出
