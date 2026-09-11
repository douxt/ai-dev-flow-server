---
type: HITL
estimate: 0.5d
effort: small
status: backlog
blocked_by: []
needs_llm: false
needs_vision: false
needs_pdf: false
needs_docker: true
test_files:
  - tests/integration/health_check_selftest.sh
  - tests/integration/test_health_check.bats
safety: ""
---

# T8 测试基础设施可达性：让新增测试真的被执行

## 背景

实测本机：docker **无任何镜像**、**无外网**（`docker pull` 失败）、**未安装 bats**、`npx --offline bats` 取不到。而 `tests/run_tests.sh` 依赖 `bats/bats:latest` 与 `ubuntu:22.04` 镜像，`run_local.sh` 依赖本机 bats → **阶段一新增的 bats 文件在本机永远不会被执行**（零依赖自测可跑，bats 只是薄封装）。

## 选项

- **a.** 预拉/预置镜像到本机（需一次性网络）
- **b.** 把 bats 执行固定到有网机器/CI（NAS 或远端）并写清入口
- **c.** 把 `tests/integration/health_check_selftest.sh` 挂到开发机 cron（T5 的看门狗里，每小时跑一次，零依赖）
- **d.** 放弃 bats 薄封装，只保留零依赖自测（减少"永不执行"的假安全）

## Acceptance Criteria

- [ ] `[decision]` AC1: 明确并落地上述一条路径（a/b/c/d）
- [ ] `[human-verify]` AC2: 给出该路径**被执行过一次**的证据（日志/时间戳）
- [ ] `[human-verify]` AC3: 文档写明"本机不可用"的前提与替代命令（`docs/bot/automated-testing-guide.md` 或 `tests/README`）

## Scope

**In:** 选定路径 + 落地 + 文档。
**Out:** 重写既有测试用例、改造整个测试框架。

## 风险

- 风险1: 选 d 会让 bats 覆盖消失 — 缓解: 若选 d，需在 AC 中记录理由与替代保障
- 回退: `git revert`
