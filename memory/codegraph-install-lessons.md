---
created: pre-2026-07
name: codegraph-install-lessons
description: CodeGraph MCP 安装与配置踩坑——target 名、副作用、cli mcp list 校验
metadata: 
  node_type: memory
  type: feedback
  severity: medium
  originSessionId: 328233bd-f000-40b8-ac3c-375e70ce9d4c
---

# CodeGraph MCP 安装踩坑

**发现日期**: 2026-07-13
**项目**: ai-dev-flow-server
**codegraph 版本**: v1.1.6

## 踩坑 1: target 名是 `claude` 不是 `claude-code`

`codegraph install --print-config claude-code` 会报 `Unknown target` 错误。
正确命令:
```bash
codegraph install -t claude -l global -y
```
可用 targets: `claude`, `cursor`, `codex`, `opencode`, `hermes`, `gemini`, `antigravity`, `kiro`

## 踩坑 2: install 的 3 个文件副作用

`codegraph install -t claude -l global -y` 会修改:
1. `~/.claude.json` — 加 `codegraph` 到 `mcpServers`(stdio 类型,`codegraph serve --mcp`)
2. `~/.claude/settings.json` — 写 2 次,auto-allow 权限(你的 file-guard 自保护可能报警,这是正常行为)
3. `~/.claude/CLAUDE.md` — **追加 CodeGraph 使用说明章节**;若已存在则检测到,不重复

安装后务必查一次 `claude mcp list | grep codegraph` 确认已注册。

## 踩坑 3: 安装完成后不会立即生效

MCP server 在**会话启动时**加载。`codegraph install` 完成后,当前会话的 `codegraph_*` MCP 工具仍不可用(`no such tool`)。必须**重启 Claude Code 会话**工具才出现。

重启前可先用 CLI 临时替代:`codegraph query/explore/node/callers -p <project-path>`

## 踩坑 4: 配置不含项目路径,跨项目可复用

`codegraph serve --mcp` 是 CWD 感知的——MCP server 在哪个项目启动,就向上找最近的 `.codegraph/` 目录。所以:
- 一份全局配置(写在 `~/.claude.json` 的 `mcpServers.codegraph`)即可供所有项目使用
- 若某项目已有 `.codegraph/`(如 `~/dev` 父级 + `~/dev/references` 子级),MCP server 自动定位到最近的索引
- **无需每个项目单独配置**(如 UMES3 项目已有的配置可直接复用,因它不含路径参数)

## 踩坑 5: 多项目索引层级

`~/dev/` 父级 `.codegraph` 覆盖所有子项目(3881 文件)。`~/dev/references/` 子级 `.codegraph` 独立覆盖参考项目(1333 文件,含 7 个 bot 记忆插件)。MCP server 在 `ai-dev-flow-server` 项目启动时找最近索引(目前无 `.codegraph`),若无则向上找 `~/dev/.codegraph`。

**建议**:`ai-dev-flow-server` (Python 插件)应在项目根 `codegraph init` 建专用索引,这样查询当前项目不走父级大索引,更快且不混参考项目符号。
