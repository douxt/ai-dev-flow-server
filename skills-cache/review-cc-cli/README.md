# review-cc-cli

独立上下文的 `claude -p` 子进程代码/文档评审 skill。多轮复用同一 session 以降本。

## 核心特性

- **独立子进程审查** — 子进程独立上下文，不受当前对话影响
- **多轮会话复用** — 第 2 轮起利用 prompt cache 大幅降本
- **Rubric 驱动** — 按路径自动匹配审查标准（8 个 rubric）
- **模型选择** — `--opus`(默认) `--sonnet` `--haiku` 或 `--model <ID>`
- **多端点 Provider** — `--provider <名称>` 或自然语言（「用 deepseek 评审」），子进程端点/密钥/模型由独立 profile 控制，与当前会话网关解耦
- **异构双层评审** — `--hetero`：单实例内主模型（lead）带子代理（pack）分维并行 + 主模型综合评审；如 deepseek-v4-pro 指挥 deepseek-v4-flash，`modelUsage` 账本硬核对防模型泄漏
- **Loop 自动收敛** — `--loop` 多轮独立评审，3 轮无新发现自动停止
- **并行评审** — `--parallel` 多 agent 按维度同时审查
- **范围灵活** — 当前 diff、指定文件、目录、git 范围、scope 限定均可

## 安装

```bash
npx skills add douxt/skills -g -a claude-code -y
cd ~/.claude/skills/review-cc-cli && bash scripts/install.sh
```

`install.sh` 部署 settings-review.json + rubrics 到 `~/.claude/`。若目标已是 symlink（如三层部署模式），脚本自动跳过，加 `--force` 强制覆盖。

`review-providers.json` 仅在 `~/.claude/` 下不存在时从模板种入（`~/.claude/secrets/` 目录一并创建，700 权限），**已存在永不覆盖，`--force` 也不例外**——用户 provider 配置优先。

### 更新

```bash
npx skills update review-cc-cli          # 更新 SKILL.md
cd ~/.claude/skills/review-cc-cli && bash scripts/install.sh   # 同步配置
```

`install.sh` 内置版本追踪（`.review-cc-cli-version`），同版本自动跳过。SKILL.md 与配置版本不一致时会提示。

## 使用

```bash
/review-cc-cli                        # 审查未提交改动
/review-cc-cli src/                   # 审查指定目录
/review-cc-cli --rubric security src/auth/  # 用安全标准审查
/review-cc-cli --explore src/         # 探索式审查（深入读相关文件）
/review-cc-cli HEAD~3                 # 审查最近 3 个 commit
/review-cc-cli --quick                # 快速模式，跳过主进程评估
/review-cc-cli --loop docs/plan.md    # 循环评审直到收敛
/review-cc-cli --parallel             # 并行 4 维评审（设计中）
/review-cc-cli --rubric prd prd.md    # PRD 评审
/review-cc-cli --scope "第一批" --with spec.md src/
/review-cc-cli --provider deepseek    # 用 DeepSeek 端点评审
/review-cc-cli --hetero --provider deepseek   # pro 指挥官带 flash 兵异构评审
用 deepseek pro 带 flash 评审这次改动    # 自然语言等效上一条（需含 provider 线索+模式词；裸说"pro带flash"若同时命中多 profile 会询问）
用 deepseek 评审这次改动               # 自然语言等效 --provider deepseek
/review-cc-cli --help                 # 完整参数说明
```

## Provider 多端点配置

profile 文件 `~/.claude/review-providers.json`（首次 install.sh 自动从模板种入）：

- `providers.<名称>`：`base_url`（须 Anthropic 协议端点）+ `token_file`（密钥放 `~/.claude/secrets/*.key`，600）+ `model`（默认模型）+ `aliases`（自然语言匹配）
- **profile 文件不放密钥明文**，只放路径；密钥仅在子进程 env 展开瞬间存在，不进 prompt/transcript/日志
- 顶层 `default` 键非 null 时，省略 `--provider` 也会启用该 profile —— **设置即全局改变默认评审端点，确认后再配**；模板默认 null（不改变旧行为）
- 自然语言输入解析后强制回显 `已解析 provider/model/base_url/来源`；歧义必询问，不猜
- **零配置兜底**：不要求 provider（裸调用 / `--parallel` / `--loop`）时 provider 体系完全透明，无 profile 文件也走旧行为（继承会话 env），不报错；一旦**显式要求** provider（含自然语言命中、`--hetero` 走 profile 链）而 profile/密钥缺失则硬失败给指引，**不静默回退**（防止"以为换了模型实际没换"）
- ⚠️ 仅适用于个人独占机器：token 会进入子进程 env，同机进程可读 `/proc/<pid>/environ`

## 异构双层评审（--hetero）

单实例内**指挥官（lead）并行派发子代理（pack）分维评审 + 亲自综合评审**，聚合一份上报。与 `--parallel` 的选择：大 diff、需独立 verifier 硬隔离 → `--parallel`；异构模型组合、外层省心、中小范围 → `--hetero`。省的是外层上下文，不是 token。

- 零参数可用：裸 `--hetero` = 当前网关最强模型带最便宜模型；配 profile `model`/`pack_model` 后即「pro 带 flash」
- 默认链：lead = `--lead` > profile.model > opus 别名；pack = `--pack` > profile.pack_model > haiku 别名（provider 激活且缺 pack_model 时 pack:=lead 并警告，**绝不跨端点回退**）
- **防模型泄漏**：命令模板五路 env 全覆盖（BASE_URL/TOKEN/ANTHROPIC_MODEL/三别名/SUBAGENT）；返回 JSON 的 `modelUsage` 键集合必须恰好 = {lead, pack}，混入第三方键 = 整单失败不采信
- **防敷衍**：聚合 JSON 强制含 5 个来源键（4 维度 + lead_review），各模型 inputTokens>0 才作数
- 权限事实（实测）：评审实例的子代理**不继承**主会话的文件守卫/防火墙钩子——防护为**指挥官与子代理 prompt 层的软约束**（拒发/拒做写执行、子代理只读句硬性植入、禁孙代理嵌套），**非钩子级硬拦截**，理论上可被高强度注入绕过——评审目标按不可信输入设计，但仍勿用于评审你完全不信的来源
- 同质归一化：lead==pack 判定剥离 `[1m]` 后缀比较；同质继续时账本断言退化为单键 == {lead}
- `--hetero` 与 `--parallel`/`--loop` 互斥；超时默认 900s，外层后台启动

## 参数速查

| 参数 | 分类 | 说明 |
|------|------|------|
| `<文件\|目录\|git范围>` | 范围 | 指定审查对象，默认未提交改动 |
| `--opus` | 模型 | 最强模型（默认） |
| `--sonnet` | 模型 | 平衡模型 |
| `--haiku` | 模型 | 快速评审 |
| `--model <ID>` | 模型 | 自定义模型 |
| `--provider <名称>` | 模型 | 使用 review-providers.json 中的端点 profile；自然语言提及同样命中 |
| `--hetero` | 模式 | 异构双层：单实例 lead 主模型并行派 pack 子代理 + 综合评审；与 parallel/loop 互斥 |
| `--lead <ID>` | 模型 | hetero 指挥官模型（完整默认链见「异构双层评审」节，含跨端点回退禁令） |
| `--pack <ID>` | 模型 | hetero 子代理模型（同上；缺 pack_model 时 :=lead 并同质警告） |
| `--shallow` | 上下文 | 只看 diff，不读额外文件 |
| `--explore` | 上下文 | 允许 grep/读相关文件 |
| `--rubric <名称>` | 标准 | 指定评审标准（可多个，逗号分隔） |
| `--scope <描述>` | 标准 | 限定评审范围，超出标记 deferred |
| `--with <路径>` | 标准 | 绑定参考文档（可多次指定） |
| `--quick` | 模式 | 跳过主进程评估，直接输出子进程结果 |
| `--loop` | 模式 | 自动收敛循环，3 轮空转停止 |
| `--loop-rounds <N>` | 模式 | 最大轮次（默认 10） |
| `--loop-budget <tokens>` | 模式 | token 预算上限 |
| `--parallel [维度]` | 模式 | 多 agent 并行分维评审 |
| `--timeout <秒>` | 控制 | 子进程超时（默认 300） |
| `--help` | — | 显示完整使用说明 |

`--loop` 与 `--quick` 互斥。

## Rubric 自动匹配

| 路径特征 | 自动匹配 rubric |
|----------|---------------|
| `auth/`、`login`、`password`、`token` | default + security |
| `test/`、`spec/`、`*.test.*` | default + testing |
| `*.md`、`plan`、`方案`、`docs/` | default + plan |
| `*.yml`、`*.yaml`、`Dockerfile` | default + config |
| `benchmark`、`perf`、`慢查询` | default + performance |
| PRD、需求文档 | default + prd |
| 以上都不匹配 | default |

显式 `--rubric` > 路径自动匹配 > default。

## 结构

```
review-cc-cli/
├── SKILL.md                    # 技能定义
├── README.md                   # 本文件
├── scripts/
│   └── install.sh              # 部署配置 + rubrics
├── config/
│   ├── settings-review.json    # 子进程权限配置
│   └── review-providers.example.json  # provider 模板（install.sh 种入 ~/.claude/）
├── rubrics/                    # 审查标准（8 个）
│   ├── default.md              # 可维护性与风格
│   ├── correctness.md          # 逻辑正确性与错误处理
│   ├── security.md             # 安全漏洞
│   ├── performance.md          # 性能问题
│   ├── plan.md                 # 计划/方案评审
│   ├── prd.md                  # PRD 需求文档评审
│   ├── config.md               # 配置文件评审
│   └── testing.md              # 测试质量评审
└── docs/                       # 设计文档
    ├── parallel-review-design.md
    └── best-practices-dev-workflow.md
├── tests/                       # 测试 fixture
│   └── fixtures/
│       ├── fixture-bugs.js      # 植入 bug 文件
│       └── README.md            # 验收标准
```

## Rubric 部署结构

```
skills/review-cc-cli/rubrics/   ← 唯一源码
        │  install.sh
        ▼
claude-config/review-rubrics/   ← 个人配置仓库
        │  symlink
        ▼
~/.claude/review-rubrics/       ← 运行时（全部 symlink）
```

## License

MIT
