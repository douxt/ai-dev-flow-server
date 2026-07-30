---
created: pre-2026-07
name: ssh-tailscale-synology-timeout
description: Synology DSM OpenSSH 8.2 + Tailscale SSH 握手挂起问题与解决
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0234377b-5787-452d-8508-bfc3df0d6fc0
---

# Synology DSM SSH over Tailscale 超时问题

## 根因

Tailscale 路径 MTU 不到 1280（实测 ~1208 字节）。SSH Kex 握手包 >1208 字节，带 DF 标志，被中间路由静默丢弃。TCP 连接和 banner 正常（小包），但 Kex 协商超时。

## 解决方法

**临时**：`sudo ip link set dev tailscale0 mtu 1200`
**持久化**：`echo 'FLAGS="--tun-mtu=1200"' | sudo tee -a /etc/default/tailscaled && sudo systemctl restart tailscaled`

已知 issues（备查，非本次根因）:
- [Tailscale #4382](https://github.com/tailscale/tailscale/issues/4382) — OpenSSH 8.2p1 特定
- [Tailscale #6459](https://github.com/tailscale/tailscale/issues/6459) — Synology Firewall 阻隔 Tailscale 流量
- [Tailscale #4163](https://github.com/tailscale/tailscale/issues/4163) — DS218+ SSH 超时
- [Tailscale #3627](https://github.com/tailscale/tailscale/issues/3627) — Synology 向外 SSH 挂起

## 解决方法

1. **Synology 防火墙加白名单**（最可能）：控制面板 → 安全 → 防火墙 → 添加允许规则，来源 IP `100.64.0.0/10`
2. 或直接关闭 DSM 防火墙测试
3. 降级 OpenSSH 客户端到 7.9
4. nc proxy 绕过：`-o "ProxyCommand=nc %h %p"`（已验证无效）

## 如何预防

- NAS SSH 出问题时，先用 `nc <ip> 22` 测 banner，banner 有但 ssh 超时 → 查防火墙/OpenSSH 兼容
- 多次重试失败后应搜网络而非反复换参数
