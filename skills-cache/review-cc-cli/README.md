# review-cc-cli

独立上下文的 `claude -p` 子进程代码/文档评审 skill。多轮复用同一 session 以降本。

## 核心特性

- **独立子进程审查** — 子进程独立上下文，不受当前对话影响
- **多轮会话复用** — 第 2 轮起利用 prompt cache 大幅降本
- **Rubric 驱动** — 按路径自动匹配审查标准（8 个 rubric）
- **模型选择** — `--opus`(默认) `--sonnet` `--haiku` 或 `--model <ID>`
- **Loop 自动收敛** — `--loop` 多轮独立评审，3 轮无新发现自动停止
- **并行评审** — `--parallel` 多 agent 按维度同时审查
- **范围灵活** — 当前 diff、指定文件、目录、git 范围、scope 限定均可

## 安装

```bash
npx skills add douxt/skills -g -a claude-code -y
cd ~/.claude/skills/review-cc-cli && bash scripts/install.sh
```

`install.sh` 部署 settings-review.json + rubrics 到 `~/.claude/`。若目标已是 symlink（如三层部署模式），脚本自动跳过，加 `--force` 强制覆盖。

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
/review-cc-cli --help                 # 完整参数说明
```

## 参数速查

| 参数 | 分类 | 说明 |
|------|------|------|
| `<文件\|目录\|git范围>` | 范围 | 指定审查对象，默认未提交改动 |
| `--opus` | 模型 | 最强模型（默认） |
| `--sonnet` | 模型 | 平衡模型 |
| `--haiku` | 模型 | 快速评审 |
| `--model <ID>` | 模型 | 自定义模型 |
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
│   └── settings-review.json    # 子进程权限配置
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
