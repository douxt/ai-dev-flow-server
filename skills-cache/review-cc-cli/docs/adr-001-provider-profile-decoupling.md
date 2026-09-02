# ADR-001: Provider Profile——评审引擎与主会话网关解耦

## 状态：已采纳
## 日期：2026-08-28

## 背景

skill 起 `claude -p` 子进程评审时完全继承主会话环境变量（端点、密钥、模型），评审模型被迫与开发模型同源。用户主会话常挂阿里云 qwen 网关，需要评审换用其他服务商（如 DeepSeek 官方），且未来任意端点可配。

## 决策

1. 独立 profile 文件 `~/.claude/review-providers.json`：每 provider 声明 `base_url`（限 Anthropic 协议）、`token_file`（密钥路径）、`model`、`pack_model`（ADR-002 引入）、`aliases`；顶层 `default` 键（默认 null 保旧行为）
2. **密钥三层分离**：密钥明文只存 `~/.claude/secrets/*.key`（600，目录 700）；profile 只存路径；子命令只出现 `$(cat <token_file>)` 形式——明文不进 prompt/transcript/audit-log（验收 P2/H10 以 grep 0 命中实证）
3. **显式 `--provider <名称>` + 自然语言双入口**，flag 优先；启动子进程前强制回显「已解析 provider/model/base_url/来源」，歧义（≥2 命中）必停问不猜
4. **硬失败语义**：profile 缺失 / 名称未知 / token_file 无效 → 停止并列出可用项，绝不静默回退继承 env（回退 = "以为换了模型实际没换"，评审结论污染比不出结论更糟）
5. install.sh 只在目标不存在时种模板，**`--force` 也不覆盖用户 provider 配置**
6. 模型 ID 一律双引号（`[1m]` 后缀会被 shell glob 吞）

## 后果

- 评审端点与开发会话彻底正交；`claude -p` 的 env 优先级实证：`--model` 覆盖继承的 `ANTHROPIC_MODEL`，无需双保险（Risk 2 证伪项）
- 引入 /proc/<pid>/environ 暴露面 → 限定个人独占机器，共享环境不适用（文档如实声明）
- `claude-*` 别名透传到异构端点时由对端映射档位（DeepSeek 官方映射到自家模型），回显以返回 JSON `modelUsage` 为准

## 拒绝的方案

- **profile 内直接存密钥**：破坏"文件可随手分享/入库示例"边界，且 grep 泄漏审计面扩大
- **未知 provider 静默回退默认端点**：与评审独立性原则冲突（见决策 4）
- **keychain / 加密存储集成**：过度设计，600 权限文件 + 审计 grep 已达个人机需求
- **改 settings.json 的 env 段做切换**：触碰受保护基础设施，且影响面是全 CLI 而非仅评审子进程
