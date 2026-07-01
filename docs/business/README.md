# DevFlow

@author: Claude Code
@created: 2026-06-23
@status: 🔵开发中

移动端 AI 开发全流程管理系统——聊天对齐 → PRD → Issue → 审批 → 自动执行 → PR 审查。

## 技术栈
- Archon (coleam00/archon)：YAML workflow 执行引擎
- OpenLobby (kkkkk1k1/openlobby)：CC 多会话 Web 聊天
- FastAPI + htmx：审批看板（自建）
- cc-stack：模型路由代理

## 文档索引
| 文档 | 说明 |
|------|------|
| [prd.md](prd.md) | 产品需求文档 |

## 代码
- 审批看板：`docs/business/devflow/approval_board.py`（待开发）
- Archon workflow：`.archon/workflows/align.yaml`, `.archon/workflows/auto-execute.yaml`
- dispatch.sh：服务器端派发脚本

## 依赖
- MAF Agent：无（独立服务）
- 外部服务：cc-stack 代理、Gitee API、Tailscale
