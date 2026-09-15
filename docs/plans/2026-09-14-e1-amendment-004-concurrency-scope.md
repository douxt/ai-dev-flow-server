# E1 Amendment-004：并发口径精确化 + 沙箱上下文卫生

> 2026-09-14 · 追加 Amendment-001/002/003 · 本件**精确化（非废除）**预注册 §6 冻结清单中"本机负载纪律"一条；§6 其余冻结项不变

## 一、触发：用户质疑 + 实证核查

原 §6 措辞"实验夜不并行跑其他 agent 任务"过宽。用户要求核实"本机 token-plan 是否真出过 429/限流"。全盘扫描 3338 个日志/轨迹（`~/.claude/projects`、`.cc`、langbot、E1 runs、cut-optimizer）结论：**零真实 API 限流证据**——所有 "429/限流/overloaded" 命中均为误报：repo `research/` 存档里的网络抓取状态码、被测功能测试文件名 `test_rate_limit.py`、DevFlow trace 时间戳数字、记忆钩子提示词正文。

## 二、口径修订（替代 §6 该子条）

**禁止（会污染测量）**：E1 pilot/主段**跑批窗口内**，用**同一 ali token-plan 账号**并发跑其它重型 claude agent（争抢同账号服务端缓存/限流 → 威胁 run 存活率与各臂对称性）。

**允许（无害）**：
- 其它 provider / 其它 API key 的会话（codex 自带、deepseek 直连、OpenRouter 等）照常并行；
- 本机轻载开发（编辑、读、跑小任务）；
- 其它项目 Claude Code 会话（只要不猛占 CPU、不走同一 ali 账号）。

**残余不确定性（诚实）**：本机从未做过"同账号 18 路真解并发"的压力，"没观察到"≠"不会发生"。→ 由 pilot 台账 `status` 字段实测：若 pilot 期出现 `timeout/agent-error` 集中于某臂，即坐实对称性破坏，回到本条收紧。

**理由锚**：疗效指标 P1/P2 由判分跑 pytest 定，只要 run 不被中途截断，何时判分结果不变；行为货币刻意只计非缓存 fresh token（input+output），cache_read/creation 抖动不入账。故"轻度并发"对**决策依据(臂间疗效差)**近乎免疫，真风险集中在"限流把某臂 run 打掉"这一条——可测可审，不需一刀切禁并。

## 三、顺带修复：沙箱上下文卫生（run_driver）

发现 checkout 从 cut-optimizer 归档时带入整棵 `research/`（调研引擎存档，含 `"status":429` 抓取噪声），与解题无关却灌进每格 agent 上下文、拖慢、且是本次 429 假象来源。
- 修：`build_sandbox` 增 `SANDBOX_NOISE=('research',)` 在臂挂载前剔除；**不动封卷哈希**（exam.yaml 只锁 hidden-sha256 与 prompt-sha256，无 checkout 哈希）。
- 验证：bats「上下文卫生：沙箱剔除 research/ 但保留解题源码」，e1-run-driver 8/8。
