# 平台反馈路线图 v1.0

> 全局长期方案——平台级租户反馈的唯一持久归口，不被任务级计划覆盖。
> 配套：测试质量路线图 [06-testing-quality-roadmap.md](06-testing-quality-roadmap.md)（测试门禁专属，本文件管平台其余反馈）。
> 上次更新：2026-09-12（UMES3 三轮交接单往来 + 五份 L4 调研入线，见阶段四）

## 文档定位

DevFlow 平台改进反馈的**唯一持久路线图**。租户反馈（`docs/devflow-platform-feedback.md` 类）在此归口：

```
租户反馈包 → 验证真实性 → 归类到阶段 N / Inbox → 实施 → 标记完成
```

每次新反馈追加到 Inbox，定期归类；阶段可无限追加，编号不覆盖。

## Inbox：待处理反馈

| 反馈 | 来源 | 主题 | 状态 |
|------|------|------|------|
| FEEDBACK-002 | go-vue-scaffold | stacks 技术栈知识保鲜机制 | 🔄 M0 已落地（v3.5），M1/M2 待排（见阶段二） |
| FEEDBACK-004 | go-vue-scaffold | DSH hooks 自动门禁沉淀 | ⏳ 待审 go-vue 试点脚本质量 |
| DEFECT-001 | UMES3 配置体检 | 修复版三门禁依赖 `grep -oP`（GNU），busybox 环境静默失效 | ⏳ 跨平台兼容改造待评估（stdin 测试已限 ubuntu 镜像） |
| 遗留 | go-vue FEEDBACK-001 | 漏洞扫描检查类别（govulncheck / npm audit 按 tags 路由） | ⏳ 待排 |
| DEFECT-003 | v3.5 回归对照 | **基线既有测试失败**：base 1c150a6 上 ubuntu 39 挂 / alpine 34 挂（migrate 系 13、rollback 系 6、hook 链 4、install mode/--home/--no-config 系 7、stage-tickets 系 8、escape/CLAUDE.md 路由表 2、verify 1）——非 v3.4/v3.5 引入，疑与同期 stage-tracker/install 改动或环境依赖有关 | ⏳ 待排（修前以 detached worktree 基线对照为准，参照记忆 bats-baseline-detached-worktree） |
| DEFECT-004 | T3 传播暴露 | install.sh update 段 `chmod +x "$CLAUDE_HOME/.claude/hooks"/*.sh` 对 symlink **穿透改目标文件 mode**——claude-config 纳管环境下 4 个 644 hook 源文件被 +x（git mode 污染，已宿主手动还原）。修法：`[ -L ] || chmod +x` 或 find `! -type l`；同段 skills 轮换对同名 skill 的 mv 覆盖同理需 symlink 检查 | 🔄 chmod 三处已修（v3.5 merge-dedup 分支）；**skills mv/cp 穿透检查遗留待排** |
| DEFECT-005 | cut-optimizer 接入 | `--tech-stack python` 只写 config `language:` 不写 `tags:` → fresh 段 stacks 知识**静默不部署**（install.sh L821；L1084 读 tags 为空即跳）——需二次 --update 才补上。修法：模板写 `tags: ${TECH_STACK}` 或参数化多 tags | ⏳ 待排 |
| DEFECT-006 | cut-optimizer 接入 | 仓级钩子无 owner 通道 + `.devflow/knowledge/*.bak` 混进拦截清单 | 🔄 前半已修（v3.6 角色门，含双评审实锤的 HEAD:master 绕过洞与 zero-SHA 误放新建洞）；**bak 拦截清单半项拆 DEFECT-013** |
| DEFECT-007 | cut-optimizer 接入 | `check_constitution.py --batch issues/` 误扫安装产物 `test-plan-template.md`（3 ❌ 全来自模板非真票）——batch 模式应排除 `TEMPLATE.md`/`*-template.md`，或 install 不落地到 issues/ | ⏳ 待排 |
| FEEDBACK-005 | cut-optimizer | python 栈缺 greenfield/FastAPI 服务类知识（现仅 legacy-characterization，与新仓 TDD 场景错配）；项目级纪律该仓自迁 `docs/`+CLAUDE.md 指针（其转正记忆已反哺平台目录约定，见 gate-checklists/README.md） | ⏳ M2 反哺素材（含空仓过门禁 V2 观察：G2.4 ruff WARN 属预期，全链无崩溃） |
| DEFECT-008 | cut-optimizer 会话（用户纠正） | 平台退役技能无清理通道：v3.0 退役 gate-* 但 `~/.claude/workflows/wf-gate-*.js`（meta.name 被会话注册进 available skills 列表，与真技能无异）+ 6 件套旧 skills 永驻租户环境——模型据此引用已退役 `/gate-2-prd` 误导用户 | ✅ 本机已清残备份（skill-backups/）+ `RETIRED.txt`/`prune_retired()` 通道 + 4 bats；**边界**：项目级 .claude/skills 残留（UMES3 WSL 树 3 链 + Win 树 6 链及 .agents 实体）通道不覆盖，须 UMES3 会话按其流程清，项目级扫描留通道 M1 迭代 |
| DEFECT-009 | 本次清理中发现 | T1 复活的 file-guard 自保护分支含 `chmod a-w` 冻结受害文件——真实拦截 settings.json 后把它冻成 444，妨碍 owner 合法维护（本次 python 编辑 PermissionError 实锤）。冻结对** routinely 编辑的配置文件**是误伤设计。修法：保护分支只拦截不 chmod，或 chmod 后在拦截消息中告知解冻命令 | ⏳ 待排（**勘误：仅 claude-config 单侧**——模板版 file-guard 无 chmod 分支且 deploy_file 遇 symlink skip，评审核实） |
| DEFECT-010 | 反馈五·补（cut-optimizer 拆票实证） | check_constitution.py 三缺陷：①规则 10 `scan_ac_levels` 主路径返回 (level,ac) 元组列表而判定比字符串——`[auto]` 正确标注必误报 warning（我方 seed 时 1 warn 即此，互证）；②规则 16 检测端只认 `来源:`，模板/惯例书写 `来源=`，模板过不了自身机检（改 `[:：=]` 三态）；③规则 8 "hash" 一词误命中 crypto 域（词表加边界） | ⏳ 待排（三处小修可并一 commit+bats） |
| DEFECT-011 | v3.6 评审 | cut-optimizer 13:14:18 repo 级 hooksPath 写入者未定位（与 auto-worktree 时间戳吻合属嫌疑）；盲区=`git config` 类命令不落 file-audit。SessionStart 防线漂移检测为候选方案 | ⏳ 观察项待排 |
| DEFECT-014 | cut-optimizer 记忆整理时发现 | install update 段（L609-611）把平台内部 ADR 全集 10 份复制进每个租户 `docs/decisions/`，与租户自有 ADR 编号冲突（cut-optimizer 曾同存平台 001-plugin-directory 与自有 ADR-001-independent-repo，语义撞车）；已代删租户侧 12 件残留 | ⏳ 修法待定：该段本意（平台决策供租户参考？）先考古再改——疑应改为不复制或只复制标注"平台通用"子集 |
| DEFECT-012 | v3.6 评审 | 全局 `~/.git-hooks/` 不在任何 git 纳管（pre-commit/post-commit 散养无版本）；新 pre-push 已有平台源档 templates/global-git-hooks/（sha256 留档），余两文件纳管 claude-config 需另行授权 | ⏳ 待排 |
| DEFECT-015 | UMES3 交接单 P0-1（三轮共认实锤） | stage 前置门禁票面粒度缺陷：`.devflow/stage` git 跟踪单调递增无重置 → 首个 ticket 后 RED 前置失效，GREEN 反作弊连带退化为"自愿前提上的可选项"（对不守流程 agent 两层同失效——**约束力从确定性滑向自觉**，UMES3 二轮修正我方一轮"仍有效"澄清，接受）。修法绑定 FEEDBACK-007 决策：保留→worktree 本地化+事件日志（G5 范式）；替换→整条退役 | ⏳ **待 FEEDBACK-007 决策**（阶段四 E0/E1） |
| DEFECT-016 | UMES3 交接单 P0-2 | 项目级 `.claude/skills/` 残留清理通道：44 个 `.bak-*`（91 条 transcript 证据确被加载）平台 install 从不管理该路径（部署目标 $CLAUDE_HOME）；`--update` 永不带走。并入 DEFECT-008 边界做项目级扫描通道 M1；本轮泄漏已停（rotate_skill_bak 上位修复生效），本条只管存量清理 | ⏳ 通道待排；UMES3 存量其自清 |
| DEFECT-017 | UMES3 交接单 P2-2（后半条成立） | workflow-gate route 全局化+TTL 决策无文档：CHANGELOG:56 仍记旧行为"绑定 session_id"，现码已是全局单文件 + `WORKFLOW_GATE_TTL` 默认 4h——副作用"同 TTL 窗口跨 .devflow 项目不再重拦"未声明。修法：CHANGELOG 补更正条目 + knowledge/07 记取舍边界 | ⏳ 纯文档小修待排 |
| DEFECT-018 | UMES3 二轮复核（催生，我方一轮漏判认账） | `templates/CLAUDE.md.base.append` 停留 2026-07-24：`:22 [C1-C5]`（实况 C0–C7）、`:25 S1-S10`（实况 S1-S13）——**而它是 `--update`/角色切换传播的唯一通道**，所有租户 marker 段每次更新被"正确地"刷回旧文案。修法与 FEEDBACK-006（append 瘦身）合并决策：改文案或整段下沉 | ⏳ 与 006 并案待排 |
| DEFECT-019 | UMES3 二轮 §5.2 | 正文模板 `CLAUDE.md:39` 写 `S1-S12` 而 spec-checklist 实含 S1–S13（S13 于 851f7f1 引入当天正文更新即漏）——**根因：清单文件与描述它的文档之间无机械一致性校验**。修法：selftest 或 bats 加断言"清单实际编号 ⊆ 文档声明编号"（防再漏，比逐处修字更根本） | ⏳ 待排（小改+bats） |
| DEFECT-020 | 三轮核实（我方回执二自身再纠错） | **正文模板 `config-templates/default/CLAUDE.md` 是死通道**：穷举 install 全流程，项目级 `.claude/CLAUDE.md` 正文区**无任何写入点**（update 只 sed 重拼 marker 段、fresh 只幂等追加），用户级落点又被 claude-config symlink 守卫 skip——193 行模板全机无有效分发目标，各租户正文区皆为历史快照。影响：①DEFECT-019 的"S1-S12 笔误"实际从未伤害过任何租户（没人收到它）②新租户拿不到正文模板任何更新。修法待定：正文化为只读参考文档（承认死通道）或增"项目级正文区可选项刷新"通道（破坏 fresh-only 承诺，慎） | ⏳ 待排（先定方向） |
| FEEDBACK-006 | UMES3 交接单 P1-1（判定修正后仍成立半条） | 流程注入的 89 行 base.append 含过程性内容（完整路径图/阶段机/关键路径表），Anthropic 建议 CLAUDE.md 只留事实——瘦身下沉为 skill/指针。与 DEFECT-018 同文件同案 | ⏳ 待排 |
| FEEDBACK-007 | UMES3 交接单 P1-3 + 两轮 L4 调研 | **TDD 必经 → 结果导向**决策项。证据状态：方向四份独立同向（Böckeler/agentic-dev-team/arXiv 2602/TDAD：强制 test-first 无质量收益、结构维度负收益、成本+；deepseek 系高写测试组强制边际收益最低），但强度不足以单方拍板（greenfield/单模型/小样本/形态不同构，且门禁效应仅 2pp 级者测不出）。**更锐利的框架**：机制隔离实证"收益来自 refactor 步而非 test-first 序"——我们的门禁恰只管顺序不管 refactor。决策前置 = 阶段四本机对照实验 | 🔴 **待用户决策 + 待 E1 实验** |

## 已处理反馈

| 反馈 | 主题 | 落地 | 提交 |
|------|------|------|------|
| FEEDBACK-001 | lint_command 死配置修复 + 漏洞扫描建议 | ✅ G2.4 消费 config.yaml lint_command（lint 失败阻断、无配置跳过）；漏洞扫描（govulncheck/npm audit）留 Inbox 待评估；`download-qqmail-invoices.py` 已清理 | 71ae6b1 |
| FEEDBACK-003 | Spec 宪法第 10 条扩展——外部项目引用须声明来源/借鉴/差异 | ✅ 宪法文字扩展 + `check_constitution.py` 16.external_ref（warning 档）+ 数字涟漪 15→16 同步 | 411f514 |
| DEFECT-20260827 | UMES3 缺陷报告：三门禁 hook 静默失效（P0）+ file-guard 自保护死代码（P0）+ skills .bak 洪水（P1）+ 文档失实（P2） | ✅ 三门禁吸收 UMES3 修复版 + file-guard 重写（自保护前置/exit 2/stdin 取参）+ hooks 执行位 + 安装后 hook 自检（selftest_hooks）+ stdin 协议 bats 19 用例（含对照实验）；.bak 移出扫描根 + 同级只留 1 + 统计；CLAUDE.md 网关档位注 + Git 约束对齐 wt 实践。详见 `issues/2026-08-27-*.md` 处理记录 | gate-hooks-bak-fix 分支 |
| DEFECT-002 | UMES3 配置体检 | 旧 bats 触碰真实 `$HOME`（workflow-gate.bats teardown/touch 删改 `.emergency-bypass`；本会话扩展发现 test_plan_backup.bats `rm -rf $HOME/.claude/plans/.git-backup`） | ✅ 两文件 setup 中 HOME 沙箱化（mktemp），真实文件哨兵验证存活 | v3.5 |
| FEEDBACK-002-M0 | go-vue-scaffold | stacks 保鲜元数据 + 过期 gate 提示 | ✅ 12 模板文件 `reviewed_at`/`status` 占位符 + install 部署刷当天 + green-gate G2.5（90 天 warning，busybox 降级跳过，env 可覆盖阈值）+ stacks-freshness.bats 6 用例双镜像 | v3.5 |
| 问题五 | UMES3 8/28 补记 | merge-settings hooks 三胞胎重复注册（同 matcher 3 组 × Edit/Write 链） | ✅ 真根因=1999ff6 只聚合 existing 侧、模板/自定义同名多组短路折叠——两侧聚合+每 matcher 单组修复；真实数据 3 组→1 组 + 4 bats 用例 + Dockerfile 补 python3。**勘误**：8/28 首次回执"重跑即折叠"为单组 fixture 假阳性，教训=幂等测试须用真实环境数据形态 | merge-dedup-chmod-symlink 分支 |

## 阶段二：stacks 知识保鲜机制（FEEDBACK-002）

> 调研：2026-08-21 多源并行调研（Metabase/Atender/conduit-ui/Medium/Atlan 等）。
> 结论：元数据 + 过期可见为共识核心；事件触发（依赖大版本升级）优于纯时间触发；stale 不自动删除只标记降权。

### M0：元数据 + 过期 gate 提示（~1 天，核心）✅ 已落地 v3.5（2026-08-28）

- stacks 文件头统一加元数据注释行（实测为 `>` 引用块风格，非 frontmatter）：`reviewed_at: YYYY-MM-DD` / `status: current|stale`（source 已有）
- install.sh 部署时注入 `reviewed_at`（首次部署 = 当天）
- green-gate 加扫描段：grep 头注释 `reviewed_at`，超 90 天 → warning"相关栈知识待重审"（不引入 yaml 依赖，与现有 grep 式检查一致）
- 平台 5 栈 ~20 文件标注来源时间

### M1：依赖大版本升级触发标 stale（+0.5-1 天）

- 检测 `go list -m -u` / `npm outdated` major 跃迁 → 对应栈文件 `status: stale`
- 前置设计：依赖 ↔ 栈文件映射规则（主要设计成本，M0 落地后观察真实数据再定）

### M2：重审回馈闭环（+0.5 天）

- 文档化回馈流程：租户调研更新 → 通用部分提平台 PR
- 重审后 `reviewed_at` 刷新 + status 恢复 current

## 阶段三：DSH hooks 自动门禁沉淀（FEEDBACK-004）

### 前置审查（未做，M0/M1/M2 之后）

- 审 go-vue-scaffold 的 `.codex/hooks.json`（dsh-hooks-codex 桥接）+ `hook-gate.sh` + `hook-trace.sh` 质量与通用化程度
- 决定：脚本通用化纳入平台 scripts/ + install 按需部署（dsh 桥接配置 cordis.patch.yml 属 DSH 安装环境，平台只提供参考配置）
- 评估：DSH/Codex 类 agent 的 hooks 订阅能力差异（仅支持 PreToolUse/PostToolUse/SessionStart/UserPromptSubmit/Stop 五事件，PreToolUse 仅 block 语义）

## 阶段三·五：UMES3 三轮交接单往来（2026-09-12 闭环记录）

七条判定全部收敛：P0-1 ✅（含 UMES3 二轮"约束力归属"修正我方一轮澄清）、P0-2 ✅ 残渣、P1-1 ⚠️ 半条、P1-2 ❌ 打回（UMES3 认错：记忆≠实测；但反向催生 DEFECT-018/019 真缺陷——其记忆描述的对象写错了，故障本身真实存在）、P1-3 ✅ 方向+强度下调、P2-1/2 各半条。三方文件：`devflow-v32-issues-handoff.md` → `…-reply.md` → `…-followup.md` → `…-consensus-reply.md`（UMES3 docs/references/，均其自提交）。我方两处漏判（未核 base.append / 虚构正文重写点）已在回执二/三中认账并转化为 018/020 登记。

## 阶段四：门禁改造对照实验（FEEDBACK-007 的决策前置）

> 输入：[agent-gate-tdd-vs-outcome-survey.md](../references/agent-gate-tdd-vs-outcome-survey.md)（证据面 L4）+ [agent-ab-experiment-design-survey.md](../references/agent-ab-experiment-design-survey.md)（方法面 L4）+ [agent-tdd-gate-community-pulse-survey.md](../references/agent-tdd-gate-community-pulse-survey.md)（社区动向面 L4——含 E1 协议修正：B 臂改为"宣称修正"形态、g0 异步窄域化、强制层下沉 git hooks）
> + [model-scale-harness-tdd-survey.md](../references/model-scale-harness-tdd-survey.md)（模型规模×harness L4）：**五条模型无关规律**（逆缩放/规则预算乘法/结构外置>指令内联/验证可替代性/harness 漂移主效应），E0 修正——判死的是 prompt 层流程指令，粗粒度 hook 层 RED 门禁反被增援；**E1 改三臂**（现状/去 prompt 指令留 hook/全去换 g0）× 双模型档，并先跑 hook 遵从基线审计、实验期冻结 harness 版本。FEEDBACK-006 从"体验"改判"机制"（CLAUDE.md 瘦身=门禁有效性前置）
> + [flash-model-generation-harness-impact-survey.md](../references/flash-model-generation-harness-impact-survey.md)（模型换代冲击面 L4）：换代爆炸半径三层=协议面→默认面→能力面（V4.1-Flash / Qwen3.8-Next 官方一手）；社区已命名应对模式 **Scaffold Ablation on Model Upgrade**（组件贴假设标签→逐个摘除跑 eval→policy/安全类豁免）。**紧急项独立于 E0**：9/14 起 `deepseek-v4-pro` 静默路由至 V4.1-Flash——需全租户 model 引用审计 + 用 E1 固定子集在 V4.1-Flash 上跑一轮影子评估（即换代回归套件首次实战，DEFECT-011 正解）。
> 结论先行：外部证据方向可信但不可外推到本模型+本门禁形态；能测 ≥2pp 效应，1pp 级不可判定；推断单位=ticket，主检验=BCa 分层 bootstrap（朴素检验 p 值可膨胀 10–1000×）。

### E0：决策门（半天，人工）

用户在三选项上拍板框架：**A** 保留强制 TDD（修 015 走 worktree 本地化+事件日志）/ **B** 直接换结果门禁（g0 升必过，015 随门禁退役）/ **C** 先实验后决策（默认推荐）。选 C 则继续 E1–E3；选 A/B 则 E2 仍要做（g0 升门禁是两条路的公共资产），E1/E3 作废登记理由。

### E1：H1 两臂最小对照（~1 天墙钟，AFK 可分夜跑）

- **假说 H1**：RED  commit 前置对①隐藏验收通过率②g0 kill rate 无显著影响，但显著增加 token/墙钟。
- **设计**：6–8 真实 ticket × {A=现状门禁, B=关 stage 前置} × 3 重复（KTH 功效公式代入 σ1.5–1.8pp：2pp 效应需 7–13 独立观测/臂）。配对按 ticket 内比较。
- **隐藏验收**：从已合并 PR 反向重建（self-bench 路径：变更前 commit 起点 + 原 PR 测试扣下 + 验证无解必败/原实现必过）；协议哈希冻结 YAML，缺哈希拒算分。
- **隔离**（mdredd 清单）：每 run 独立沙箱 worktree、隐藏宿主 `.git` 历史、屏蔽项目 auto-memory、排除项目 `.claude/` skill 遮蔽；变体交替 + 顺序签名检验。
- **记分**：主终点 = 隐藏验收 pass + kill rate；次 = 四类 token 分开计价（缓存折扣可砍 61% 账面，禁比总额）、墙钟、回归率。分析 evalstats 两层嵌套 bootstrap。
- **预注册**：假设/主终点/停止规则落盘时间戳在先（抄 agentic-dev-team Exp02 格式），禁止跑后改口径。

### E2：g0-inject 升格必过门禁（~0.5 天，与 E1 并行可先行）

g0 从 test-checklist 预检项 → green-gate/`exit 2` 必过项（F22 事故的对症资产，无论 FEEDBACK-007 怎么决都要做）。**门禁自身体检**：seed recall（注入已知故障被抓比例，目标 ≈100%）+ clean 假阳性率（好补丁误拒，目标 <5%）——先过体检再上岗，防"不能通过的检查不是检查"翻面（误拦杀流程）。

### E3：H2 机制对照（E1 出结果后排期）

三臂 {无门禁, RED 前置, **refactor 提交前置**}：机制隔离证据（tdd-no-refactor ≈ test-after，refactor 臂才低）指向"门禁该管的是回头整理结构，不是写测试顺序"。E1 若支持 H1，E3 回答"换成管什么"。产出直接进 ADR（门禁形态终案）。

### 完成判据

E0 决策落 ADR；E1 报告含 CI 区间且如实标注"不可判定"区段；E2 体检两指标达标记录在案；E3 结论进 FEEDBACK-007 归档行。

## 变更历史

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-09-13 | v1.5 | 阶段四输入补至五份 L4：新增模型规模面（五条通用规律，E1 改三臂×双档+遵从基线审计+harness 冻结）与换代冲击面（Scaffold Ablation 模式、三层爆炸半径）；**新紧急项（独立于 E0）**：9/14 `deepseek-v4-pro` 静默路由至 V4.1-Flash → 全租户 model 引用审计 + V4.1-Flash 影子评估（换代回归套件首战，DEFECT-011 正解） |
| 2026-09-12 | v1.4 | UMES3 v3.2 交接单三轮往来闭环：新登 DEFECT-015~020 + FEEDBACK-006/007；新增阶段三·五（往来记录）与阶段四（门禁改造对照实验 E0–E3，输入=两份 L4 调研）；我方两处漏判认账转化为 018/020 |
| 2026-09-03 | v1.3 | v3.6 钩子角色门+全局串联落地；DEFECT-006 拆分（010 归 check_constitution 三缺陷）、新登 011/012 |
| 2026-08-28 | v1.2 | M0 落地（stacks 元数据+G2.5）+ DEFECT-002 修复（bats HOME 沙箱，含 test_plan_backup.bats 扩展） |
| 2026-08-27 | v1.1 | UMES3 缺陷报告 4 项归口处理（三门禁/file-guard/.bak/文档）；新入 DEFECT-001（grep -oP 跨平台）、DEFECT-002（旧测试删真实 bypass）、漏洞扫描遗留 |
| 2026-08-21 | v1.0 | 初始版本——4 张 go-vue 反馈归口：001/003 完成标记，002 调研分层（M0/M1/M2），004 待审 |
