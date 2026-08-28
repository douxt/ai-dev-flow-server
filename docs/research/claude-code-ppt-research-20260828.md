# Claude Code 高质量 PPT 生成与改造 — 调研报告（2026-08-28）

> 两波调研：第一波 5 角度并行泛搜（官方方案 / 程序化库 / HTML 框架 / MCP 生态 / 设计方法论），第二波对选定方向深入（PPTAgent 源码精读、改造现有 PPT 路线、dom-to-pptx 验证、官方 pptx skill 一手源码精读）。
> 一手源码位置：`~/dev/references/anthropics-skills/`、`~/dev/references/PPTAgent/`。

## TL;DR — 推荐架构（分层）

| 层 | 选型 | 说明 |
|---|---|---|
| **主力管道** | Anthropic 官方 `pptx` skill | Claude Code 原生，生成/读取/改造三通路 + XSD 校验 + 渲染视觉 QA 闭环，`/plugin marketplace add anthropics/skills` 即装 |
| **设计约束层** | DESIGN.md 六要素 + 两段式大纲闸 + 反 AI-slop 禁令 | 决定"高级感"的是这一层，与管道正交，叠加在官方 skill 之上 |
| **批量/模板复刻**（可选） | PPTAgent (icip-cas) | 独立服务/MCP；唯一强项是"旧 deck→模板→批量出新 deck"+逐页渲染自检；部署重，按需引入 |
| **演讲表现力优先**（可选） | Slidev（官方内嵌 MCP）/ Marp | 视觉上限最高，但导出的 pptx 是图片贴页，交付同事编辑是断点 |

**"高级"的关键不在库，在三个纪律**：① 先大纲后页面（action title + ghost-deck 测试）；② 设计 token 钉死（DESIGN.md）；③ 强制"渲染成图→视觉检查→修→复验"回路——官方 skill 是同类中唯一内置完整闭环的。

---

## 1. 技术地图总览

| 路线 | 代表 | 产物可编辑性 | 视觉上限 | AI 适配 | 结论 |
|---|---|---|---|---|---|
| 原生 OOXML | Anthropic pptx skill（pptxgenjs 新建 + 裸 XML 编辑） | ★★★ 真原生对象 | ★★ | ★★★ | **主力** |
| HTML→转换 | Marp / Slidev / reveal.js → pptx | ✗ 图片贴页（editable 导出保真差） | ★★★ | ★★★ | 演讲/PDF 场合用 |
| HTML→原生转换 | dom-to-pptx | ★★（声称） | ★★★ | ★★ | 观望 |
| 代理式服务 | PPTAgent / Presenton | ★★★ | ★★-★★★ | ★★★（独立管线） | 批量场景引入 |
| COM 自动化 | ppt-mcp 等 | ★★★ | ★★★ | ✗ 仅 Windows 桌面 | 无头环境排除 |

横向评测共识（bulaev 11-skill 实测、r/ClaudeCode 跨工具横评）：Claude + 官方 skill 处于第一梯队；唯一硬判据——**要求"真表格/真图表"时 11 个 skill 只有 2 个产出原生 OOXML 对象**，其余用几十个文本框"画"表格，打开一加行就穿帮。差评集中在设计偏 blocky、大 deck 上下文吃紧。

---

## 2. 主力：Anthropic 官方 pptx skill（一手源码精读）

### 2.1 安装

```
# Claude Code 会话内
/plugin marketplace add anthropics/skills
/plugin install document-skills@anthropic-agent-skills   # 含 pptx/docx/xlsx/pdf
```
或手工：把 `skills/pptx/` 放进 `~/.claude/skills/`（个人）/ `.claude/skills/`（项目）。

⚠️ **license 为 Proprietary**（© 2025 Anthropic, PBC）：本人经 CC 插件通道使用没问题；若要进本仓库 `skills-cache/` 分发到目标项目，先自查条款。

### 2.2 三条路径（按任务分叉）

| 任务 | 做法 |
|---|---|
| **新建** deck | 写 pptxgenjs Node 脚本（约 20 条"corrupts the file"级 footgun 清单，见 SKILL.md） |
| **编辑**现有 deck / 套模板 | `unzip → 改 ppt/slides/slideN.xml → zip`（不走 python-pptx） |
| **读取** | `markitdown deck.pptx`（分 slide 文本块）+ `scripts/thumbnail.py`（带标号缩略图网格，给模型"看"） |

**编辑走裸 XML 的原因**（也是 python-pptx 三大硬伤）：无法复制 slide（唯一入口 `add_slide(layout)`）、`text_frame.text = ...` 会把格式折叠成单 run、无母版/主题级控制。裸 OOXML 是外科手术，天然保留模板其余设计。

### 2.3 捆绑脚本（SKILL.md 238 行 + scripts/ 约 1200 行 Python）

| 脚本 | 作用 |
|---|---|
| `thumbnail.py deck.pptx [prefix]` | 全 slide 缩略图网格（**必传 prefix**，否则两个 deck 互相覆盖） |
| `add_slide.py unpacked/ slide2.xml [--after …]` | 带全套 package 簿记地复制 slide/layout，**永不手工 cp slide 文件** |
| `clean.py unpacked/` | 清理未引用的 slide/media/rels（在 `<p:sldIdLst>` 定稿后跑） |
| `office/validate.py deck.pptx [--original src.pptx]` | XSD + 关系 + content-type + 图表校验；模板 deck 必带 `--original` 基线（防模板自带错误算你头上）；每条失败报修法 |
| `office/soffice.py` | LibreOffice headless 包装（处理沙箱 socket 问题） |
| `office/helpers/pptx_theme.py` | 检测多 master 共享 theme part 的损坏场景 |

### 2.4 强制 QA 闭环（这是"高级感"的工程保障）

```
生成 → markitdown 内容核对 + grep 占位符残留(lorem/TODO/xxx)
     → validate.py 文件级校验
     → soffice 转 PDF → pdftoppm -jpeg -r 150 逐页出图
     → 逐张视觉检查（首遍必有 overlap/overflow，预期内；建议开 subagent 盲审——"盯着生成代码看久了会看到你以为的东西"）
     → 修 → 只重渲染改动页
```

### 2.5 关键 footgun 摘录（新建路径）

- 先设 `pres.layout`：默认画布 10"×5.625" 不是 13.3"，超界内容被写出但不在页面上
- hex 色不带 `#`、禁 8 位带 alpha（**损坏文件**）；option 对象会被原地 mutate 成 EMU，不可复用
- 负 shadow offset 损坏文件；stacked chart `dataLabelPosition: outEnd` 损坏文件；combo 副轴必须同时声明 valAxes+catAxes（否则 PowerPoint 判损坏弃图表）
- `letterSpacing` 静默无效（真名 `charSpacing`）；bullet 用 `bullet:true` 否则双圆点；文本框内边距需 `margin:0` 才能与图形对齐
- XML 转换必须 `defusedxml.minidom`/lxml——`ElementTree` 往返重写命名空间前缀**直接损坏 deck**
- 打包：从 unpacked 目录内 `zip -Xr`，且先 `rm` 旧产物；勿重排 `<p:presentation>` 子元素顺序

### 2.6 美术规则（内置于 SKILL.md 的"设计 token"）

- 10 套主题色板；主色支配 60-70%、单一视觉母题贯穿全 deck
- 显式禁令（AI 味标志）：**标题下装饰强调线、装饰色条/边缘色条、米黄背景、全圆角、正文居中**
- 每页必有视觉元素；正文字号 14-16pt、标题 36-44pt
- 字体安全清单：QA 渲染宽度可靠的只有 Arial/Calibri/Cambria/Times 等；**Aptos 禁用**；非安全字体留 ~10% 富余且不可信 QA 文本拟合——**LibreOffice 字体替换对中文不可信，最终复验必须在真 PowerPoint 环境**

### 2.7 本地依赖清单（当前 WSL 机器实测缺 4 项）

```bash
# 实测现状：node/npm/python3 有；soffice、pdftoppm、python-pptx、markitdown、defusedxml 全部 MISSING
sudo apt-get install -y libreoffice poppler-utils fonts-noto-cjk
pip install "markitdown[pptx]" pillow defusedxml lxml
npm install pptxgenjs   # skill 假设预装，本地首次 require 失败时补装
```

---

## 3. 读取现有 PPT → 改造为高质量（SOP 草案）

> 综合 Anthropic skill、financial-services 三 skill（ppt-template-creator / ib-check-deck / deck-refresh）、pptx-from-layouts-skill、归藏 guizang skill、Brandwares OOXML 换肤篇。
> 标注：【内置】= 官方 pptx skill 已有脚本；【半内置】= 他仓现成件需适配；【自建】= 需自写小脚本。

### Phase 0 · 保全
原件 `.bak`；解包 `python3 -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall('unpacked')" deck.pptx`；legacy `.ppt` 先 soffice 转 pptx【内置】。

### Phase 1 · 全量读取（三通道）
- 文本：`markitdown`【内置】；结构化到 run 级 → `pptx-from-layouts` 的 `edit.py --inventory -o inv.json`【半内置】或 `pptxtojson`
- 视觉：`thumbnail.py`【内置】+ 高清逐页 `soffice→pdf→pdftoppm -r 150`【内置】
- 结构：解包清点——master 数量及 `p:clrMap`、layout 清单、活着的 `themeN.xml`（按 `clrScheme name=` 认）、`charts/_rels` 有无 `themeOverride`【自建 grep】

### Phase 2 · 量化诊断（产出三级报告）
一条 python 脚本扫 inventory+XML【自建 ~100 行】：字体混杂度（**latin 与 a:ea 中文槽分开统计**）、`srgbClr` 硬编码色去重数、**schemeClr 引用占比（>70% 是"换肤可行"先决指标）**、版式利用率、每页字符/shape 数、字号分布（<14pt 预警）、shape 坐标对齐度；跨页数字矛盾用 `ib-check-deck/extract_numbers.py`【半内置】。输出 Critical/Important/Minor。

### Phase 3 · 路线决策（关键分岔）

| 信号 | 路线 | 工作量 |
|---|---|---|
| 骨架好、schemeClr 占比高、只落后品牌规范 | **A 换肤** | 0.5-1 天 |
| 骨架尚可、<30% 页需动 | **B 原地重组** | 1-2 天 |
| 没用 placeholder / 大面积硬编码 / >30% 要动 | **C 提取内容重做** | 2-5 天 |
| 旧 deck 本质是整页图片 | C + 前置 `image-to-editable-ppt-skill` | — |

（30% 分界线来自 pptx-from-layouts：纯文字小修用 inventory/replace，版式级改动必须 regenerate，禁止 edit。）

### Phase 4A · 换肤——只改 `ppt/theme/themeN.xml`（clrScheme 10 槽 + fontScheme），全 deck 生效。**9 大失效场景**（Brandwares + python-pptx issue 核实）：
1. 显式 `<a:srgbClr>`/`<a:latin>` 硬编码不跟主题 → 解包 grep 全量，批量换 schemeClr 或连 hex 一起换
2. master 的 `p:clrMap` 把 bg1/tx1 对调（老 deck 遗留）→ 核每个 master
3. 图表自带 `themeOverride1.xml` → 同步改，或删旧图重画
4. 多 master 多 theme → 按 `clrScheme name=` 确认哪个在用
5. layout 级 `overrideClrMapping` → 一并处理
6. 槽位互换事故 → 借道三步搜替（"bg1"→"tx22"→…），搜索词带属性直引号
7. **中文：`font.name` 只写 latin 槽，改 latin 中文纹丝不动**（python-pptx #768）；须写 `fontScheme` 的 `<a:ea>`，run 级 lxml 插入时 schema 强制子序 latin→ea→cs；有现成包 `pptx-ea-font`
8. LibreOffice 渲染对中文宽度不可信 → 最终复验在真 PowerPoint
9. ElementTree 回写毁包 → defusedxml.minidom/lxml

换肤必炸点（王守义实战复盘）：深浅底翻转后**所有文字对比度、按旧底色调的容器**全要复验——"改规则，不改产出物"，坑要写回 checklist。

### Phase 4B · 原地重组
先结构后内容：`add_slide.py` 复制版式页 → 改 `p:sldIdLst` 重排/删 → `clean.py` 清孤儿 → 编辑各 slideN.xml → `zip -Xr` → `validate.py --original 原件`。硬纪律：模板槽≠内容项（4 人槽 3 人就整组删含配图）；列表一项一个 `<a:p>`；不手打 `•`。

### Phase 4C · 提取重做
① 抽语义内容清单（pptx2md/inventory + markitdown 对账防漏）；② 旧截图素材走"截图再设计"（归藏 screenshot-framing：保真截图只统一画布不重画）；③ 目标格式二选一：交付可编辑 → profile 一个好模板（`pptx-from-layouts` 三步管线：catalog→slides.md 标 [HINT]→generate --validate）或先跑 `ppt-template-creator` 把现有好版式蒸馏成模板 skill；表现力优先 → HTML deck；④ 设计硬约束直接抄官方 skill 的 Design Ideas + Avoid 清单。

### Phase 5 · 复验（不可跳过）
validate.py + 全页渲染图逐页过 QA 清单（溢出第一优先）+ 占位符 grep + 真 PowerPoint 中文终检。

### Phase 6 · 沉淀
确立的版式跑 `ppt-template-creator` 蒸馏成可复用 skill（7 步：分析 placeholder→生成自包含 SKILL.md→示例验证→打包）；踩坑写回 checklist P0-P3。

---

## 4. "高级感"方法论（可执行规则清单）

1. **两段式硬闸**：先出纯文本大纲（每页一行 action title=完整结论句）→ 跑 ghost-deck 测试（只读标题串是否成故事）人工通过 → 才生成页面。绝不一步出片。
2. **DESIGN.md 钉死六件事**：底/面色 hex、双字体配对、一个有"岗位职责"的强调色（每页恰好一次，写明放哪不放哪）、签名母题、图表规则（柱浅灰/关键柱强调色/值直标/去网格线去图例/标题写成 takeaway 句子）、avoid list。所有 deck 引用同一文件（参考 SlideSpeak 70 套免费商用示例）。
3. **禁令比正面形容词有效**：禁渐变大礼包、统一下阴影、无意义图标、Inter/Roboto 默认、标题下装饰线、米黄背景、超过 2 个强调色——写成显式 STRICTLY AVOID。
4. **模板 own 版式，AI own 文案**：有企业模板时填真 placeholder，禁止 AI 新建自由文本框。
5. **可编辑性判据**：交付前点开表格/图表确认真生对象，拒绝 shape 画的假表格。
6. **强制渲染自检回路**：不信任未渲染的输出（所有存活 skill 的共同点；失败最惨的都是信任自己输出的）。
7. **内容密度反均值**：AI 指纹=过度一致性。至少一页只放一句 60pt 的话、一页放密集表格；禁"每页 3 bullet+1 图"均匀分布。修的方向是引入**受控的不规则**。
8. **图表风格 token 化**：matplotlib/echarts 生成时同一色板贯穿全 deck。
9. **文案去 AI 腔**：封杀"赋能/协同"黑话；数据页数字必须来自用户材料，AI 不得编造。
10. **留 20% 人工痕迹**：最后 10 分钟换 2 张真实照片、挑 2-3 页有意破格。

---

## 5. 第三方生态评估

| 候选 | 定位 | 成熟度证据 | 结论 |
|---|---|---|---|
| **PPTAgent** (icip-cas) | 双栈：legacy 编辑型(MCP 可接 CC) + DeepPresenter(HTML 逐页生成+`inspect_slide` 渲染自检+html2pptx 转原生) | 4958★/MIT/push 2026-08-24/EMNLP25+ACL26 | **值得按场景引入**：批量出片、`template_induct.py` 把旧 deck 变模板复刻版式（官方 skill 给不了的克隆能力）。短板：无原位改稿模式；依赖重（Playwright+Node+Docker DooD，WSL 下注意）；每页 inspect 循环 token 大且偶发死循环(#243)；LLM 可配 OpenAI 兼容端点含 Claude。其 `html2pptx/` 是 Anthropic skill 的增强 fork（overflow 校验+CDP 字体探测），可单独偷 |
| **Presenton** | 自托管 HTTP API：prompt/文档→模板→**可编辑** PPTX/PDF，自带编辑器，模型指任意兼容端点 | 9888★/Apache-2.0/push 2026-08-27 | 服务器批量场景备选；重服务，非 CC 内操作 |
| **Slidev** | 开发者 HTML slides，**官方内嵌 MCP server**（8 工具：get/update/insert/move…写回 .md 热重载） | v52.x 极活跃/单人主维护 | 技术演讲+agent 长周期改稿最佳；pptx 导出=图片页 |
| **Marp** | markdown→slides，唯一直出 pptx | 稳定 | pptx 默认图片贴页；`--pptx-editable` 官方自认保真差、维护者反对该方向 → 放弃 |
| **dom-to-pptx** | HTML DOM/CSS→pptxgenjs 原生形状（坐标刮取式） | 338★/月下载 16.6 万（注水：自家 SaaS 驱动）/watchers 仅 4/单人 | **观望**：方向对、代码真实，但保真"逐案例赌博"（中文多栏/transform/伪元素翻车有案），Marp 维护者独立评审"not practical"。硬性"HTML→可编辑 pptx"时可受控试点（装其官方 skill 用 style 白名单），失败页回退整图 |
| GongRzhe PPT MCP | python-pptx 封装 32 工具 | 停更 8 个月，元素重叠官方承认 | **弃** |
| COM 自动化系 MCP | 驱动真 PowerPoint | 仅 Windows 桌面 | 无头/WSL 排除 |
| Kimi/WPS AI | — | Kimi 无公开 PPT API（网传均为假）；WPS 私有化仅商务渠道 | 防踩雷 |
| 商用 REST | AiPPT(open.aippt.cn)、文多多、讯飞、Skywork MCP | 按量付费 | 需要国内合规通道时的备选 |
| 归藏 guizang-ppt-skill | 单文件 HTML 横向翻页 deck，版式锁定系统（22 具名版式、禁自定义 hex）+ validate 脚本 + P0-P3 checklist | 24.6k★ | 中文表现力路线的**规则样本库**，方法论直接抄 |
| NanoBanana PPT Skills | 图像模型直出整页图（不可编辑） | 3.2k★ | 极端重做路线；风格 md 结构可抄 |

---

## 6. 本环境落地路线

1. **装 skill**：`/plugin marketplace add anthropics/skills` → install document-skills（或把 `~/dev/references/anthropics-skills/skills/pptx/` 拷入 `~/.claude/skills/`；注意 license 条款，进 DevFlow skills-cache 分发前确认）。
2. **补依赖**：见 2.7 清单（LibreOffice+poppler+Noto CJK+pip 三件套）——**没有渲染回环就没有 QA，这条不装齐不如不用**。
3. **建 DESIGN.md**：按第 4 节六要素写一份自己的设计规范，放项目根，生成时引用。
4. **改造旧 deck**：按第 3 节 SOP 走，先用官方 skill 覆盖 A/B 路线与读取；C 路线重做时可参考 pptx-from-layouts 管线。
5. **进阶（按需）**：批量出片/模板复刻→试 `uvx pptagent onboard` + 注册 `pptagent-mcp`；演讲场合→Slidev + `claude mcp add slidev`。
6. **DevFlow 结合**：若要把 PPT 能力装进目标项目，做成 skills-cache 条目 + install.sh 依赖检查（对齐本项目容器依赖文档 `docs/references/container-dependencies.md`）。

## 7. 风险汇总

- 官方 skill Proprietary license——分发/商用嵌入前先读 LICENSE.txt 全文
- LibreOffice ≠ PowerPoint 渲染：字体替换（尤其中文）不可信，交付前必须真机终检
- 大 deck 上下文吃紧（51 页实测爆上下文需重开会话）→ 分段处理、改完只重渲染改动页
- pptxgenjs 图表 XML 偶发触发 PowerPoint"修复"对话框（#1449）→ validate.py 必跑
- PPTAgent 部署链路重且文档与代码有漂移；本地 9B 模型效果被社区劝退，用 API 模型
- 转换类工具（dom-to-pptx/Marp editable）产物是"绝对定位框堆"，同事挪框不联动——编辑性≠版式语义

## 8. 主要来源

- 官方 pptx skill 一手：`anthropics/skills` main@2026-08（本地 `~/dev/references/anthropics-skills/skills/pptx/SKILL.md` 238 行全文）
- `anthropics/financial-services`：ppt-template-creator / ib-check-deck / deck-refresh SKILL.md
- PPTAgent 源码：本地 `~/dev/references/PPTAgent/`（AGENTS.md、deeppresenter/main.py、template_induct.py、html2pptx.js）+ arXiv:2501.03936 / 2602.22839
- bulaev.net《I had 11 AI subagents test every PPTX skill》；r/ClaudeCode 跨工具横评
- Brandwares OOXML Hacking 系列（换肤失效场景）；python-pptx issues #413/#768/#917
- sli.dev/guide/work-with-ai（官方 MCP）；marp-cli README/discussion #82/issue #725
- dom-to-pptx GitHub 源码+issues #45/#59；Presenton/归藏/王守义 substack 等（详见对应小节链接）
- SlideSpeak DESIGN.md 规范；2slides/ChatSlide 反 AI 味分析（注意为厂商营销内容，数字存疑）
