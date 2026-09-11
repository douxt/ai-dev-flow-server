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

---

## 执行结果（2026-09-11）：选定路径 c

**选项 c 落地**：把零依赖自测挂进开发机看门狗（`nas/watchdog.sh` 新增第 0 步），每小时执行一次：

```bash
selftest_out=$(timeout 300 bash "$REPO_ROOT/tests/integration/health_check_selftest.sh" 2>&1)
[ $? -ne 0 ] && problems+=("巡检脚本自测失败（N 项断言不通过）")
```

理由：本机无 docker 镜像/无外网/未装 bats（`tests/run_tests.sh` 与 `run_local.sh` 都跑不了），而零依赖自测**本机与 NAS 都能跑**；挂进看门狗即获得"周期性执行 + 失败通知"两个属性，不需要新基础设施。

bats 薄封装（`tests/integration/test_health_check.bats`）保留：供有网/CI 环境走标准套件，不再是唯一入口。

### AC 验证

- [x] `[decision]` AC1: 路径 = c（零依赖自测挂看门狗）；理由：零新依赖 + 周期执行 + 与告警链路复用
- [x] `[human-verify]` AC2: **被执行过的证据** —— 2026-09-11 11:45 看门狗运行内含自测通过并写日志 `OK（漂移/心跳/积压 均正常）`（若自测失败会追加一条 problem 并推送）
- [x] `[human-verify]` AC3: 文档写明本机不可用与替代命令（见 `docs/bot/automated-testing-guide.md` 新增小节）

### 备注

- 全量 bats 套件仍需在有网/CI 环境执行；NAS 上的巡检相关自测可作为兜底（future: 把 selftest 也拷到 NAS 由 cron 跑）
