# ADR-003: settings 文件 env 段优先级高于进程 env——`--setting-sources user` 断源

## 状态：已采纳（修订 ADR-002 决策 3 的前提）
## 日期：2026-09-15

## 背景

2026-09-15 用 `--hetero --provider deepseek` 评审时连续三次故障（白烧 ~$6.9）：
1. profile 模型名 `deepseek-v4.1-flash` 被上游弃用 → 400（端点响应体点名 supported 仅 `deepseek-flash, deepseek-v4-pro`）
2. **核心**：四个分维子代理三次派发全 400，泄漏值 = `qwen3.8-flash`。根因：项目 `.claude/settings.local.json` 的 env 段（`CLAUDE_CODE_SUBAGENT_MODEL`/`ANTHROPIC_DEFAULT_*`=qwen 值）在 CLI 加载时**覆盖命令行注入的进程 env**——实测优先级链 **settings 文件 env 段 > 进程继承 env**。ADR-002 决策 3"五路 env 封死别名解析"的前提（进程 env 最高优先）在配了项目 settings.env 的机器上不成立
3. 子代理全灭后指挥官自行代跑，报告以近正常形态返回，$1.83 花完才靠 `modelUsage` 账本规模（271K vs 79K）识破

## 决策

1. provider/hetero 全部 `claude -p` 调用点（含预检）标准模板追加 **`--setting-sources user`**：切断 project/local 设置层加载，进程注入 env 成为唯一真源。**双通道缺一不可**——五路 env 封"别名解析路径"，此参数封"settings.env 覆盖路径"
2. 标准模板尾部统一 `< /dev/null`（headless 子调用缺 stdin 重定向吃 CLI 3s 交互警告，组内先例）
3. 新增 **⓪-pre 启动预检**（provider/hetero 激活时硬性）：模型名 smoke（拦上游改名，400 时提取 supported 列表回写 profile + `last_verified` 字段固化）+ env 污染哨兵（子进程回显 `ANTHROPIC_MODEL` ≠ 注入值即报污染源）
4. **兵失败禁代跑**规约入指挥官 prompt 模板：子代理失败一律入 `missing_dimensions`，外层据此强制 verdict=BLOCKED，并核对总 inputTokens 单/双层量级（代跑照妖镜）
5. 错误处置路径中的配置读取**只报键名与模型值，TOKEN/KEY 一律脱敏**（同日 ali token 明文入 transcript 事故的直接反制）

## 后果

- **副作用如实记录（双刃）**：`--setting-sources user` 切断 project/local 两层 settings 文件加载——其 permissions / hooks（含 env 段）/ MCP 配置对评审子进程不可见（项目层 CLAUDE.md 是否受此参数影响**未实测，不做声明**）。评审是只读子任务，属预期收紧；但未来若有项目依赖项目层配置供给评审能力（非本设计路径），会静默失效，由预检②哨兵兜底报警。注意 user 层 settings 不受该参数影响，其 env 段理论上仍可覆盖注入值（本机无该段未实测）——由预检②侦测，不武断归因
- CLI 版本依赖：`--setting-sources` 实测下限 2.1.158（shell CLI 二进制；注意 VSCode 插件自带 2.1.196 为不同二进制）；错误表加"400 且参数已生效 → 判版本兼容，记录 version 降级 --parallel"
- 同质时效（deepseek 当前 pro 名被静默路由至 flash）按分层原则处理：profile 数据层 `homogeneous_ack` 字段承载，SKILL 只定义通用规则，公共文档不焊时效事实
- ADR-002 决策 3 的"五路 env 全覆盖"仍必要（无项目 settings.env 的机器上是唯一防线）但不充分——本 ADR 修订其前提，非废弃

## 拒绝的方案

- **改用户项目 settings 删 env 段**：那是用户网关运行配置，评审 skill 无权也没理由要求环境适配自己
- **在注入前 `unset` 污染键**：子进程仍会加载 settings.env 覆盖，unset 进程变量无效于 settings 通道；且手工清单式 unset 会漏新键
- **检测到劫持才加 `--setting-sources user`（条件式）**：预检②能报，但标准模板恒带更简单、行为确定，代价仅是项目层配置可见性（评审不需要）
- **把"deepseek 当前单档"写进 SKILL 规范**（反馈原案 §1f）：产品文档混入上游时效 + 个人批准事实，ack 移 profile 数据层
