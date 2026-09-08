# 技能开源命名实践调研报告（gale-research / storm-research 定名）

> 2026-09-08 · L2 档（R1 广度 6 路 → R2 官方核实，未升 L3：R2 后新增可证伪事实 <2 条，收益闸门生效）
> 场景：两技能拟开源，问 (a) 社区命名实践 (b) 直接叫 gale-research 是否合适 (c) storm-research-lite 去掉 -lite 是否合适。
> 硬性排除：纯商标法律分析。

## 1. 术语对照表

| 术语 | 含义 |
|---|---|
| gerund 命名式 | Anthropic 最佳实践建议 `<动作ing>-<对象>`（如 reviewing-prs） |
| -lite 歧义 | 作者义=lightweight（轻量实现），社区读义=crippled（功能阉割的付费诱饵） |
| CE/PE/EE 阶梯 | 开源界版本命名：Community→Professional→Enterprise |
| name==目录 | Agent Skills 规范：SKILL.md name 字段必须等于目录名，且即 /斜杠命令 slug |
| marketplace 预留 | `^(claude|anthropic)-?` 开头名被 Anthropic 官方保留（供应链安全控制） |

## 2. 候选对比总表

| 实践 | 出处 | 对本例的裁决 |
|---|---|---|
| skill name 硬规则：≤64 字符、小写字母数字连字符、不以连字符开头结尾、禁 anthropic/claude | agentskills.io/specification（官方规范，已抓原文）+ platform.claude.com best-practices | gale-research、storm-research 均合规 ✓ |
| gerund 优先风格 | Anthropic 工程博客 + 32页指南 | 生态现实反例充分（deep-research 等名词式占主流），家族一致性优先 → 不采纳 |
| "-lite"=功能阉割读法 | Wikipedia Software bloat 固化表述；uBlock Origin Lite 被社区称 "weaker, crippled"；HN PGLite 论战（作者称轻量、读者读阉割） | **支持去 -lite** ✓ |
| -lite 也有正当用法（lightweight 同物不同部署） | Datasette Lite（WASM 浏览器内跑全功能）、AXI4-Lite（简化但完整的接口变体） | 不适用——storm-research-lite 的 lite 本义恰是"STORM 大方法论的精简落地版"，与阉割读法只一线之隔 |
| DBeaver 反转先例：Lite 是付费档、Community 才是开源 | dbeaver.com/docs/Lite-Edition | 佐证 -lite 语义已漂移不可靠 |
| 版本阶梯惯例 CE/PE/EE | GitLab/Couchbase/ntopng/Plane；VCV Rack 社区投票弃 lite 选 "Rack Free" | 若未来出收费版再引入阶梯，现名无需预留 |
| 撞名实体 | storm-research：Storm Research Ltd（英国**日股证券研究公司**，stormresearch.co.uk，FCA 注册）、stormresearch.com（美国气象咨询）、TORRO（Tornado and Storm Research Organisation）；gale-research：Tomorrow.io Gale、Kore.ai GALE、Cengage Gale | 全部在 dev-tool 域外；skill 经 git 仓库分发无注册表抢占压力，仅 SEO 混淆 |
| 注册表抢占（npm/PyPI/crates first-come-first-served、slopsquatting） | PyPI Name Retention/PEP 541、crates.io 讨论 | **对 skill 本体不适用**；仅当未来封装 CLI 包时需预查 |

## 3. 排除清单及原因

- 改 gerund 式（researching-with-gale）：官方软建议与 AI 研究命名生态（deep-research 名词系）冲突，家族可辨识性损失大于合规收益；规范硬规则并不要求 gerund（已核 spec 原文）。
- 因 stormresearch.co.uk 存在而弃 storm-research：该公司为金融域、无软件商标冲突证据，"storm research" 是气象通用描述词组；排除此顾虑，但见 §4 SEO 注记。
- 保留 -lite：三重证伪——(1) 社区读义=阉割；(2) 引擎现有 fast/standard/deep 三档，"lite" 已名不副实；(3) storm 一词本身的量级叙事靠 -lite 被自我拆台。

## 4. 关键技术判断

**决定分化的字段 = 分发渠道。** Claude 技能经 git 仓库/marketplace 安装，名称不是注册表键、无先到先得抢占；上述商业撞名全部落在 dev-tool 域外，风险仅剩"搜索 'storm research' 首屏被金融公司占据"。缓解成本极低：README 与 description 首句锚定 "Claude Code skill"。

采购前必测项（开源发布前）：
1. GitHub 全局搜 repo 名 `gale-research`/`storm-research` 占位情况（发布时若被占，org 前缀目录名 `douxt/gale-research` 天然区分）；
2. 若未来封装 npm/PyPI CLI：发布前用 socket.dev package search 查 `gale-research`/`storm-research` 及规范化变体（大小写/-/_ 折叠规则）；
3. marketplace 预留词自检：两名均不匹配 `^(claude|anthropic)-?` ✓（已核）。

## 5. 推荐结论

- **短期（开源定名）**：`gale-research` + `storm-research` 双名直接用，去 -lite，保留 -research 后缀维持 deep-research 家族可检索性。两词均通过 spec 硬规则，撞名实体均在域外。
- **中期（打包策略）**：两技能放同一仓库成"风力研究套件"（目录即 name，天然满足 name==目录规范），README 用 breeze<gale<storm 三档叙事——故事完整是这个命名最大的传播资产。
- **长期（若出变体）**：出现收费/扩展版时才引入 CE/Pro 阶梯；不再使用 -lite/-mini/-nano 类后缀（语义已不可靠）。
- **一句话回答用户**：合适，且"去 lite"恰好与社区证据同向——storm-research 全家桶本来就该是唯一正式版，fast/standard/deep 三档已由 --tier 承担量级职责，-lite 冗余且自贬。

## 6. 来源列表

- https://agentskills.io/specification
- https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- https://code.claude.com/docs/en/plugin-marketplaces · https://github.com/anthropics/claude-code/issues/46786
- https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- https://en.wikipedia.org/wiki/Software_bloat
- https://news.ycombinator.com/item?id=47703805 （PGLite 语义论战）
- https://github.com/sindresorhus/uBlock-Origin-dev-filter 相关讨论经 webbindustries/Reddit 镜像（"crippled Lite" 读法）
- https://simonwillison.net/2022/May/4/datasette-lite/ · https://www.arm.com/architecture/system-architectures/amba/amba-4
- https://dbeaver.com/docs/dbeaver/Lite-Edition/ · https://github.com/orgs/dbeaver/discussions/37592
- https://community.vcvrack.com/t/name-the-free-version-of-vcv-rack-v2/13260
- https://en.wikipedia.org/wiki/Business_models_for_open-source-software · https://news.ycombinator.com/item?id=17229940
- 撞名核实：https://stormresearch.co.uk/ · https://find-and-update.company-information.service.gov.uk/company/06952562 · https://www.stormresearch.com/ · https://www.torro.org.uk/ · https://support.tomorrow.io/hc/en-us/articles/16557265262868 · https://www.gale.com/
- 注册表规则：https://packaging.python.org/en/latest/specifications/name-normalization/ · https://peps.python.org/pep-0541/ · https://docs.socket.dev/docs/package-search
