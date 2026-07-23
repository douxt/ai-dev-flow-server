---
type: AFK               # AFK(无人步骤) | HITL(含人工步骤)
estimate: 0.5d           # ≤1d 宪法要求
effort: small            # small(<1d) | medium(1-2d) | large(>2d, 禁止ready)
status: backlog          # backlog → ready(人) → in_progress(自动) → done
blocked_by: []           # 依赖的 ticket ID 列表
needs_llm: true
needs_vision: false
needs_pdf: false
needs_docker: false
test_files: []           # 精确测试文件路径，禁止留空跑全量
safety: ""               # 安全敏感 → auth|payment|crypto|delete|permission（由 check_constitution.py 自动标记）
---

# <Ticket 标题>

## 背景

<为什么需要这个改动>

## Acceptance Criteria

- [ ] `[auto]` AC1: <可量化验收条件>
- [ ] `[human-verify]` AC2: <可量化验收条件>
- [ ] `[decision]` AC3: <需要人决策的条件>

## 前置准备

- [ ] <外部服务/Token/文件>

## 代码目录

- 实现: `<src/module/>`
- 测试: `<tests/module/>`

## Scope

**In:**
- <包含的改动>

**Out:**
- <不包含的改动>

## 架构约束

- <不可变规则>

## 测试策略

- 单元测试: <路径>
- E2E 验证: <方法>

## 风险

- 风险1: <描述> — 缓解: <措施>
- 回退: `git revert` 对应 commit

## 依赖表格

| SDK/工具 | 版本 | 参考 |
|----------|------|------|
| - | - | - |

## Ticket 质量自检（对照宪法 15 项）

- [ ] 1. estimate ≤1d
- [ ] 2. type 正确（AFK/HITL）
- [ ] 3. AC 可测量（标注 [auto]/[human-verify]/[decision]）
- [ ] 4. 代码目录已指定
- [ ] 5. 前置准备完整
- [ ] 6. mock/E2E 策略明确
- [ ] 7. SDK 用法可参考
- [ ] 8. 验收无主观
- [ ] 9. blocked_by 无循环
- [ ] 10. 架构约束已引用
- [ ] 11. AC 覆盖集成层
- [ ] 12. Scope 边界清晰
- [ ] 13. needs_* 已声明
- [ ] 14. test_files 已指定
- [ ] 15. 窗口预算 ≤40%（~48K token）
