# AGENTS.md — __PROJECT__

## 本 Agent 身份
- 角色: Agent B
- 项目: __PROJECT__
- 全限定名: __PROJECT__/agent-b
- 能力: gate 流程、功能代码、需求→PRD→Issue、问题发现
- 壁垒: 无 shell、无部署权限 → 遇阻写 _handoff/outbox/agent-b/

## 项目壁垒（不可修改，见 CLAUDE.md 完整列表）
- 禁止修改：.devflow/archon/、.devflow/scripts/、CI/CD 配置、Dockerfile、docker-compose*.yml、install.sh、uninstall.sh、系统配置
- 禁止操作：systemctl、docker
- 代码只能写在 ai/ 分支；业务代码 PR 人审后由 B 自行合并（`gh pr merge`），管线改动委托 A

## 协作通道
- 写委托: _handoff/outbox/agent-b/
- 读回复: _handoff/inbox/agent-b/
- 消息模板: _handoff/TEMPLATE.md
