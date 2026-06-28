---
from: {project}/agent-b
to: dev-machine/agent-a
project: {project}
type: infra_fix | deploy_request | tool_request | question | status_report
id: {project}-{date}-{seq}
status: pending
created: {ISO timestamp}
---

## 问题描述
<B 发现了什么问题？简短描述现象和影响>

## 操作清单
- [ ] <精确的可执行命令 1>
- [ ] <精确的可执行命令 2>

## 验证方法
<A 完成后如何确认成功：具体命令 + 预期输出>

## 相关上下文
- 项目路径: <目标项目绝对路径>
- 相关文件: <涉及的文件路径>
- 相关 issue: <如有，填 issue 编号>
