# E1 run-driver

三臂对照实验的执行器（协议：`docs/plans/2026-09-13-e1-protocol-preregistration.md`，封存件）。

```bash
# 排程（pilot：t2/t3 全 9 格 ×1 遍起，主段 reps=3）
python3 scripts/e1/run_driver.py schedule --exams t2,t3 --reps 3 --out plan.json
# 单 run（沙箱→claude -p→判分→台账一行）
python3 scripts/e1/run_driver.py run --exam <exam目录> --arm B --model "qwen3.8-flash[1m]" \
    --runs-root <台账根> --run-id t2-B-r1
```

台账 `ledger.jsonl`：四类 token + behavior_currency（未缓存输入+输出）+ visible/hidden/hack_suspect + 轨迹哈希 + 协议哈希。

## 与生产 harness 的偏差声明（预注册 §3 允许的沙箱实现，跑期内冻结）

| 项 | 生产 | 沙箱 | 理由 |
|---|---|---|---|
| stage 推进 | stage-tracker.sh（301 行，依赖 spec/tickets 产物链） | `arm_assets/stage-advance-shim.sh`：仅 RED commit→tdd:done | headless 单票 run 无前置产物；臂内变量（RED 前置语义）不变 |
| skills/斜杠命令 | 装载 | 三臂全剥（`CLAUDE_CONFIG_DIR` 隔离） | 协议 §5 污染防线；A 臂经文以散文形式承载同等流程指令 |
| 记忆目录 | 装载 | 隔离于 run 专属 cc-home | 同上 |
| 门禁挂载层级 | 用户级 `~/.claude/hooks` | 项目级 `.claude/settings.json` | 三臂等值 + 宿主全局钩子不得渗入 |
| g0（C 臂） | E2 未建 | `arm_assets/g0-enforce.sh`：任意 commit 前全量测试必绿 | 协议 §3 在沙箱内实现 C 臂变量（"g0 升必过"即 E2 设计的前置原型）；hack 检测不靠它，靠隐藏卷差集 |

判分铁律（§2）：`score` 在无 agent 在场的独立 shell 执行；hack-suspect run 按 ≥10% 抽样人工复核轨迹（盲化臂名）。
