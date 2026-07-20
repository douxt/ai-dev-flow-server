# CLAUDE.md 最佳实践（社区+官方综合）

## 是什么

CLAUDE.md 是 Claude Code 启动时自动读取的 Markdown 指令文件——相当于给新同事的入职简报。**不需要在 prompt 中引用它**：只要文件存在，Claude 就已经读了。

## 记忆层级（加载顺序）

Claude Code 按五个作用域加载，从广到窄，**拼接不覆盖**：

| 作用域 | 位置 | 共享范围 | 用途 |
|--------|------|---------|------|
| 托管策略 | 企业级部署 | 全组织 | 合规、编码标准 |
| 用户 | `~/.claude/CLAUDE.md` | 仅你（所有项目） | 个人风格、工具偏好 |
| 项目 | `./CLAUDE.md` 或 `./.claude/CLAUDE.md` | 团队（版本控制） | 架构、约定、命令 |
| 本地 | `./CLAUDE.local.md` | 仅你（当前项目） | 个人项目覆盖（**自动 gitignore**） |
| 子目录 | `<subdir>/CLAUDE.md` | 团队 | 惰性加载——仅当触及该目录文件时 |

**加载规则**：
- 祖先目录**始终**在启动时加载（从 CWD 向上走）
- 子目录**惰性**加载（仅当触及其中文件时）
- 同级目录**永不**加载
- HTML 注释 `<!-- ... -->` 注入前被剥离
- **`.claude/rules/` 路径域规则**：加 YAML frontmatter `paths:` 的规则文件只在匹配 glob 的文件被触及时才加载——这是唯一的真正条件加载机制

## 该放什么 / 不该放什么

### ✅ 该放

- **命令**：怎么构建、测试、lint、本地运行（准确性最重要）
- **约定**：命名、格式化、错误处理、文件布局、"我们用 X 不用 Y"
- **架构（约 3 句）**：主要模块及其通信方式
- **硬约束**："所有 API 路由需要 auth 中间件"、"禁止编辑 `generated/`"
- **已知坑**：每个新人都会踩的
- **当前状态**：正在做什么（需频繁更新）

### ❌ 不该放

- 完整 API 文档（Claude 直接读代码）
- Changelog、历史
- 文件树已能看出的信息
- 没人真正遵守的规则
- 密钥、API key、凭证、连接字符串
- 解释 Claude 已知常识（React hooks 是什么、async/await 怎么用）

## 体量与预算

| 指标 | 推荐值 |
|------|--------|
| 单文件行数 | <200 行（最佳 ~100） |
| Token 量 | <2000 token 最佳；>4000 token 出现可测量的遵守度下降 |
| 用户级指令 | ~30-40 条 actionable（60 上限） |
| 项目级指令 | ~50-80 条 actionable（120 上限） |
| 合计加载 | ~80-120 条 actionable（150 上限） |

**行数 ≠ 指令数**。一条 3 行段落可能只有 1 条指令，一行 3 个 bullet 可能含 3 条指令。用 bullet 数量作指令预算的近似锚点。每个 `- ` 开头的 actionable 描述算 1 条指令。

Golden CLAUDE.md 模板将 **≥120 行** 明确列为反模式分类 "Overly Long Files"。

## 反模式清单

| 反模式 | 说明 | 修正 |
|--------|------|------|
| **规则重复** | 同一规则在正文、禁令表、hook 注入中多次出现 | 合并为单一权威出处；已知案例：重复浪费 35-40% 上下文预算 |
| **软语言** | "考虑使用..."、"尽量..."、"建议...""可能..." | 改为祈使句："用 async/await 处理 I/O" |
| **Soft Limits vs Hard Rules** | "建议不超过 3 个"——对模型等于没说 | 要么定硬边界（"最多 3 个，超了 OOM"），要么删除 |
| **模糊量词** | "通常验证输入" | "在 API 边界做输入验证" |
| **关键约束埋中部** | 最核心的安全红线藏在文档深处 | 关键约束放在前 2-3 个 H2 |
| **把 Claude 当 linter** | 指定命名规范、注释格式、空格规则 | 用 ESLint/Ruff/Prettier——永远不要让 LLM 做 linter 的事 |
| **`/init` 不清洗** | 自动生成的 CLAUDE.md 通常重复且臃肿 | 手写精炼，`/init` 产物需人工删减 |
| **装饰性内容** | "欢迎来到本项目！""本项目的背景是..." | 直接删除 |
| **解释已知常识** | "React hooks 让你在函数组件中使用状态..." | 跳过概念讲解，只写你的约定 |
| **过度加粗** | 80% 的行都加粗了，加粗就失去"这是关键的"信号 | 仅给违反即失败的硬约束保留加粗 |
| **喊话/元规则** | "全程保持规则一致""记住以上规则"——模型不会因此更遵守 | 删除，纯浪费 token |

## 进阶模式

### @import（≤4-5 跳递归）

```markdown
See @README for project overview and @package.json for available commands.
- git workflow @docs/git-instructions.md
```

**陷阱**：被导入文件若以 `# 一级标题` 开头，会在拼接后的文档中凭空造一个 H1，打断目录结构。**所有被 @import 的文件必须从 `##`（H2）级别起**。

**注意**：@import 不省 token——它只是把原文逐字拼进来。真正省常驻 token 的方法是**仅写路径引用、不 import**（如"完整流程见 `docs/xxx.md`"），让模型需要时才去读。

### Split 模式（精简入口）

```
~/.claude/
├── CLAUDE.md           ← 30-50 行核心（会话常驻）
└── context/
    ├── system-environment.md
    ├── troubleshooting.md
    └── contacts.md
```

入口只保留每轮对话都需要的规则，详细上下文在子文件中按需引用。

### 分层记忆（T0-T3）

| 层 | 文件 | 何时加载 | 内容 |
|----|------|---------|------|
| T0 | `CLAUDE.md` | 每次会话 | 行为准则、硬约束 |
| T1 | `MEMORY.md`（~40-80 行） | 每次会话 | 长期记忆索引指针 |
| T1.5 | `.claude/rules/` | 文件匹配时 | 路径域阶段规则 |
| T2 | 主题文件（~50 行） | 按需 | 专题上下文 |
| T3 | 归档（不限） | grep 时 | 经验教训、handoff、会话日志 |

## 钩子 > CLAUDE.md > Skill 分工

**核心原则：不要让 LLM 做 linter 的事。**

| 层级 | 适用场景 | 例子 |
|------|---------|------|
| **Hook** | 确定性执行、不可商量、每次强制 | SessionStart 注入安全规则、file-guard 拦截危险写入、bash-firewall 拦截危险命令 |
| **CLAUDE.md** | 行为准则、跨项目偏好、软硬混合约束 | 简洁中文、即时提交、不擅扩范围 |
| **Skill** | 按需激活的领域工作流、专业审查 | gate-*、code-review、grill-with-docs |

能用 hook 硬拦截的（如禁用 `git checkout --`），就不要靠 CLAUDE.md 里的文字去祈求模型遵守。

## CLAUDE.local.md

项目根目录下的 `CLAUDE.local.md`（注意 `.local.` 中间段）会被 **自动加入 .gitignore**，不在版本控制里。适合：

- 你在这个项目的个人调试偏好
- 不想污染团队共享 `CLAUDE.md` 的本地覆盖
- 跨项目但非全局的个人配置（不想放 `~/.claude/CLAUDE.md`）

## 维护策略

- **"会犯错吗"试金石**：对每一行问——"删掉这行，Claude 会因此犯错吗？"答案 No → 删除。这行要么冗余（Claude 已会），要么装饰（只给你看，不改变模型行为）。
- **定期去腐**：每 2-4 周扫一次，删除已被 lint/hook/测试 替代的规则。过时指令比没有指令更危险——stale notes actively misdirect Claude。
- **踩坑触发更新**：当 Claude 犯两次同样错误时，那是缺少规则的信号——追加。不要预先脑补"可能有用"的规则。

## 质量 Checklist

- [ ] 每条指令适用于**每次**会话（普适）
- [ ] 指令数在预算内（bullet 计数 ≤30-40 用户级 / ≤50-80 项目级）
- [ ] 无冗余（钩子做的不在 CLAUDE.md 再写一遍）
- [ ] 无风格强制（留给 linter）
- [ ] 关键约束在文档前 2-3 个 H2
- [ ] 无冲突指令
- [ ] 无软语言（考虑/尽量/建议/可能）
- [ ] 无装饰/喊话/解释已知概念
- [ ] 所有 `@import` 的目标文件从 `##` 起
- [ ] 通过"会犯错吗"试金石（逐行）

## Sources

- 官方 Memory 文档 https://code.claude.com/docs/en/memory
- Anthropic Help Center: CLAUDE.md 指南 https://support.claude.com/en/articles/14553240
- Claude Blog: Using CLAUDE.md Files https://claude.com/blog/using-claude-md-files
- claude-code-ultimate-guide https://github.com/FlorianBruniaux/claude-code-ultimate-guide
- Split-CLAUDE-MD-Pattern https://github.com/danielrosehill/Split-Claude-MD-Pattern
- memory-hygiene（分层记忆 T0-T3） https://github.com/wan-huiyan/memory-hygiene
- claude-code-best-practices / 反模式 https://github.com/MuhammadUsmanGM/claude-code-best-practices
- claude-token-efficient https://github.com/drona23/claude-token-efficient
- golden-CLAUDE.md 反模式 wiki https://github.com/Z-M-Huang/golden-CLAUDE.md/wiki/Anti-Patterns
- golden-CLAUDE.md 规则原理 https://github.com/Z-M-Huang/golden-CLAUDE.md/wiki/Why-These-Rules
- claude-world-examples 反模式 https://github.com/claude-world/claude-world-examples
- morphllm 综合指南 https://www.morphllm.com/claude-md-guide
- steering-claude-code blog https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more
