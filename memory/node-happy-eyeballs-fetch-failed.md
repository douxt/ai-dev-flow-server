---
name: node-happy-eyeballs-fetch-failed
description: Node 20+ Happy Eyeballs 250ms 超时导致 MCP/undici fetch failed (ETIMEDOUT)，curl 正常但 Node 失败
metadata:
  type: reference
---

# Node Happy Eyeballs 导致 fetch failed（exa MCP 排查记录）

日期：2026-07-15

## 现象
- exa-web-search MCP（`npx exa-mcp-server`，stdio）所有工具返回 `fetch failed`
- 同机 curl 访问 `api.exa.ai` 正常（HTTP 404，~0.95s）
- Node 22 `fetch()` / `https.get()` 均 ETIMEDOUT，但原生 `net.connect(443, IPv4)` 成功（390ms）

## 根因
Node 20+ 默认启用 `autoSelectFamily`（Happy Eyeballs），每个候选地址的连接尝试超时仅 **250ms**（`autoSelectFamilyAttemptTimeout` 默认值）。本机到 Cloudflare（api.exa.ai）TCP 握手约 390ms > 250ms，所有候选（2×IPv4 + 2×IPv6，IPv6 本就不通）逐一被提前取消 → AggregateError ETIMEDOUT → undici 包装成 `fetch failed`。

curl 无此机制，正常 Happy Eyeballs 会保留竞速连接而非 250ms 硬取消，故 curl 不受影响。上游 issue：nodejs/node#54359。

## 排查路径（分层二分）
1. curl 直连 → 通（排除 DNS/防火墙/代理）
2. `env | grep -i proxy` → 无代理（排除代理差异）
3. `curl -6` 失败、`curl -4` 通 → IPv6 断路（但非主因）
4. Node `fetch` + `ipv4first` 仍 ETIMEDOUT → 排除纯 IPv6 假设
5. `net.connect` 通但 `https.get` 超时 + 快速返回 ETIMEDOUT（远小于内核 130s）→ 指向 autoSelectFamily 的 250ms 取消
6. `--network-family-autoselection-attempt-timeout=2000` → fetch 成功，确认

## 解决方法
`~/.claude.json` 的 exa-web-search 配置 env 中加：
```json
"NODE_OPTIONS": "--network-family-autoselection-attempt-timeout=2000"
```
（该 flag 在 NODE_OPTIONS 白名单内；`--no-network-family-autoselection` 也可，但会失去 IPv6 断路时的回退）

修改后无需重启 Claude Code 会话——MCP 进程在下次工具调用时重新拉起，自动读取新 env。

## 如何预防
- 任何 Node 写的 stdio MCP server 报 `fetch failed` 而 curl 正常时，优先怀疑 Happy Eyeballs 250ms 超时——高延迟链路（跨境 ~400ms RTT）+ Cloudflare 多地址域名是典型触发条件
- 验证一行命令：`node --network-family-autoselection-attempt-timeout=2000 -e "fetch('https://目标').then(r=>console.log(r.status))"`
- 本机 IPv6 已知不通（`curl -6` 立即失败），Node/其他运行时的 v6 优先策略都可能踩坑
