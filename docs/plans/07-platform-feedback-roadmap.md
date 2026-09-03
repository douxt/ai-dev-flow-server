# 平台反馈路线图 v1.0

> 全局长期方案——平台级租户反馈的唯一持久归口，不被任务级计划覆盖。
> 配套：测试质量路线图 [06-testing-quality-roadmap.md](06-testing-quality-roadmap.md)（测试门禁专属，本文件管平台其余反馈）。
> 上次更新：2026-09-03

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
| FEEDBACK-005 | cut-optimizer | python 栈缺 greenfield/FastAPI 服务类知识（现仅 legacy-characterization，与新仓 TDD 场景错配）；项目级纪律暂由 `.claude/gate-checklists/cutting-stock-discipline.md` 承载 | ⏳ M2 反哺素材（含空仓过门禁 V2 观察：G2.4 ruff WARN 属预期，全链无崩溃） |
| DEFECT-008 | cut-optimizer 会话（用户纠正） | 平台退役技能无清理通道：v3.0 退役 gate-* 但 `~/.claude/workflows/wf-gate-*.js`（meta.name 被会话注册进 available skills 列表，与真技能无异）+ 6 件套旧 skills 永驻租户环境——模型据此引用已退役 `/gate-2-prd` 误导用户 | ✅ 本机已清残备份（skill-backups/）+ `RETIRED.txt`/`prune_retired()` 通道 + 4 bats；**边界**：项目级 .claude/skills 残留（UMES3 WSL 树 3 链 + Win 树 6 链及 .agents 实体）通道不覆盖，须 UMES3 会话按其流程清，项目级扫描留通道 M1 迭代 |
| DEFECT-009 | 本次清理中发现 | T1 复活的 file-guard 自保护分支含 `chmod a-w` 冻结受害文件——真实拦截 settings.json 后把它冻成 444，妨碍 owner 合法维护（本次 python 编辑 PermissionError 实锤）。冻结对** routinely 编辑的配置文件**是误伤设计。修法：保护分支只拦截不 chmod，或 chmod 后在拦截消息中告知解冻命令 | ⏳ 待排（**勘误：仅 claude-config 单侧**——模板版 file-guard 无 chmod 分支且 deploy_file 遇 symlink skip，评审核实） |
| DEFECT-010 | 反馈五·补（cut-optimizer 拆票实证） | check_constitution.py 三缺陷：①规则 10 `scan_ac_levels` 主路径返回 (level,ac) 元组列表而判定比字符串——`[auto]` 正确标注必误报 warning（我方 seed 时 1 warn 即此，互证）；②规则 16 检测端只认 `来源:`，模板/惯例书写 `来源=`，模板过不了自身机检（改 `[:：=]` 三态）；③规则 8 "hash" 一词误命中 crypto 域（词表加边界） | ⏳ 待排（三处小修可并一 commit+bats） |
| DEFECT-011 | v3.6 评审 | cut-optimizer 13:14:18 repo 级 hooksPath 写入者未定位（与 auto-worktree 时间戳吻合属嫌疑）；盲区=`git config` 类命令不落 file-audit。SessionStart 防线漂移检测为候选方案 | ⏳ 观察项待排 |
| DEFECT-012 | v3.6 评审 | 全局 `~/.git-hooks/` 不在任何 git 纳管（pre-commit/post-commit 散养无版本）；新 pre-push 已有平台源档 templates/global-git-hooks/（sha256 留档），余两文件纳管 claude-config 需另行授权 | ⏳ 待排 |

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

## 变更历史

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-09-03 | v1.3 | v3.6 钩子角色门+全局串联落地；DEFECT-006 拆分（010 归 check_constitution 三缺陷）、新登 011/012 |
| 2026-08-28 | v1.2 | M0 落地（stacks 元数据+G2.5）+ DEFECT-002 修复（bats HOME 沙箱，含 test_plan_backup.bats 扩展） |
| 2026-08-27 | v1.1 | UMES3 缺陷报告 4 项归口处理（三门禁/file-guard/.bak/文档）；新入 DEFECT-001（grep -oP 跨平台）、DEFECT-002（旧测试删真实 bypass）、漏洞扫描遗留 |
| 2026-08-21 | v1.0 | 初始版本——4 张 go-vue 反馈归口：001/003 完成标记，002 调研分层（M0/M1/M2），004 待审 |
