# 平台反馈路线图 v1.0

> 全局长期方案——平台级租户反馈的唯一持久归口，不被任务级计划覆盖。
> 配套：测试质量路线图 [06-testing-quality-roadmap.md](06-testing-quality-roadmap.md)（测试门禁专属，本文件管平台其余反馈）。
> 上次更新：2026-08-21

## 文档定位

DevFlow 平台改进反馈的**唯一持久路线图**。租户反馈（`docs/devflow-platform-feedback.md` 类）在此归口：

```
租户反馈包 → 验证真实性 → 归类到阶段 N / Inbox → 实施 → 标记完成
```

每次新反馈追加到 Inbox，定期归类；阶段可无限追加，编号不覆盖。

## Inbox：待处理反馈

| 反馈 | 来源 | 主题 | 状态 |
|------|------|------|------|
| FEEDBACK-002 | go-vue-scaffold | stacks 技术栈知识保鲜机制 | ⏳ 已调研，方案见阶段二（M0/M1/M2） |
| FEEDBACK-004 | go-vue-scaffold | DSH hooks 自动门禁沉淀 | ⏳ 待审 go-vue 试点脚本质量 |

## 已处理反馈

| 反馈 | 主题 | 落地 | 提交 |
|------|------|------|------|
| FEEDBACK-001 | lint_command 死配置修复 + 漏洞扫描建议 | ✅ G2.4 消费 config.yaml lint_command（lint 失败阻断、无配置跳过）；漏洞扫描（govulncheck/npm audit）留 Inbox 待评估；`download-qqmail-invoices.py` 已清理 | 71ae6b1 |
| FEEDBACK-003 | Spec 宪法第 10 条扩展——外部项目引用须声明来源/借鉴/差异 | ✅ 宪法文字扩展 + `check_constitution.py` 16.external_ref（warning 档）+ 数字涟漪 15→16 同步 | 411f514 |

## 阶段二：stacks 知识保鲜机制（FEEDBACK-002）

> 调研：2026-08-21 多源并行调研（Metabase/Atender/conduit-ui/Medium/Atlan 等）。
> 结论：元数据 + 过期可见为共识核心；事件触发（依赖大版本升级）优于纯时间触发；stale 不自动删除只标记降权。

### M0：元数据 + 过期 gate 提示（~1 天，核心）

- stacks 文件头统一加 frontmatter：`reviewed_at: YYYY-MM-DD` / `status: current|stale`（source 已有）
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
| 2026-08-21 | v1.0 | 初始版本——4 张 go-vue 反馈归口：001/003 完成标记，002 调研分层（M0/M1/M2），004 待审 |
