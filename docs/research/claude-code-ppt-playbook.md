# Claude Code 高质量 PPT 实战手册（Playbook）

> 定位：**接到任何 .pptx 生成/改造需求时，读本文件直接上手，不要重新调研。**
> 背景调研见 [claude-code-ppt-research-20260828.md](claude-code-ppt-research-20260828.md)；本手册是 2026-08-28 一次完整实战（说课稿 12 页改造，v1→v7 七轮迭代）沉淀的可执行层。

## 0. 环境状态（已配好，勿重装）

本机（WSL Ubuntu 22.04）已就绪，新会话跑一遍确认即可：

```bash
command -v soffice pdftoppm node python3 && \
python3 -c "import markitdown,pptx,lxml,PIL,defusedxml; print('env OK')" && \
ls ~/.claude/skills/pptx/SKILL.md
```

缺什么补什么：`sudo apt-get install -y libreoffice-impress poppler-utils fonts-noto-cjk`；pip 缺则 `python3 /tmp/get-pip.py --user` 后 `~/.local/bin/pip3 install "markitdown[pptx]" pillow defusedxml lxml python-pptx`。
npm 链：pptxgenjs/react-icons/sharp 等已装在 `~/ppt-jobs/shuoke/node_modules`（新任务在哪个目录用就在哪 `npm i`，秒级）。
GitHub 直连失败走代理：`export https_proxy=http://<ip route show default 拿到的IP>:7897`（Openverse 图库 API 必须走代理）。

## 1. 三件事定方向（开工前问用户/问自己）

1. **任务类型**：新建 / 读取 / **改造现有**（改造走 §3 SOP）
2. **使用场景定档次审美**——同一份内容，场合决定什么是"高级"：
   | 场景 | 评委/受众吃的 | 反感的 |
   |---|---|---|
   | 说课/赛课/教学评审 | 干货密度+逻辑图示+结论式标题（咨询报告风） | 特效、剪贴画、"作秀课件"、内容单薄 |
   | 内部汇报 | 同上 | 花哨装饰 |
   | 技术分享/现场演讲 | HTML 演示（Slidev）动效 | 被要求交付 .pptx 继续编辑时 HTML 路线不可用 |
   | 不确定 | **先对齐再动手**：给用户摆"六谱系"（咨询报告/杂志编辑/苹果极简/国风/科技深色/瑞士网格）+样张试看，指图比语言快十倍 |
3. **约束先问**：页数上限？字号"文字优先还是字大优先"？限不限制新增页面？（本次教训：先做了大留白编辑样张，用户场景其实要咨询报告密度风）

## 2. 档次阶梯（核心认知：档次 = 70% 结构纪律 + 30% 视觉修饰）

**Tier-1 结构纪律（收益最大，优先做）**：
- 硬网格：全片唯一边距/标题恒位恒字号/页码位固定（位置表进代码常量）
- **Action title**：每页标题=完整判断句；全片标题连读成故事（ghost-deck 测试）
- 来源脚注行 + 页码（若用户嫌"来源"碍眼：撤来源行，署名合并封底——CC 义务仍履行）
- 字号三级：标题≥26 / 正文≥14（投影专业线 18，用户可豁免）/ 脚注 9
- 正文左对齐；bullet≤4；禁"每页同款三卡"
**Tier-2 视觉资产**：
- 真实照片 > 一切装饰：Openverse API 搜（`license_type=commercial`，**剔除 by-nd**）→ 联络表选图 → PIL 统一阶调（深 duotone 封面大图 / 轻去饱和内页小图）。**CC BY/BY-SA 必须署名**，封底一行集中致谢=通行合规做法
- 图标：react-icons(Fi 系)→sharp 256px PNG→add_picture；单色=主色；落位卡右上角（不撞文字流）
- 封面质感：PIL 渐变+大圆+点阵+噪点（mix 0.05 防 banding）→ JPEG `quality=92, subsampling=0`（4:2:0 必出横纹）
**Tier-3 编辑手法（场景适配后才用）**：大数字页/色场切分/节分隔页——发布会语境是加分，评审语境是"内容单薄"，慎用。
**中文专属开关**（英文圈没有）：eyebrow/小标签字距加宽（XML `spc` 200-300）；中文达到同等空气感需比英文**更多**留白；微软雅黑标题合成加粗在旧 Office 可能发细。

## 3. 改造现有 PPT SOP（速查版，详见调研文档 §3）

0 备份 → 1 三通道读取（markitdown 文本 / thumbnail.py+pdftoppm 视觉 / 解包结构：masters·themes·clrMap·schemeClr vs srgbClr 占比）→ 2 量化诊断脚本出三级报告 → 3 路线：**换肤**(schemeClr>70%且骨架好) / **原地重组**(<30% 页改动) / **提取重做**(骨架烂/风格错配——最常见) → 4 执行 → 5 渲染复验+真 PowerPoint 终检（中文必查）→ 6 沉淀（DESIGN.md/脚本模板复用）。
**忠实性铁律**：数据与表述 100% 来自原稿，AI 零编造；错别字列出请用户确认后再改；原文压缩为要点时全文回灌 speaker notes（`extract_notes.py` 模式：markitdown dump→清洗中文断词空格→notes.json→逐页挂）。

## 4. 可复用资产（直接抄，别重写）

位置 `~/ppt-jobs/shuoke/`：
| 资产 | 用途 |
|---|---|
| `gen_v7.py` | **咨询报告风脚手架**：硬网格 chrome()/numrow() 编号行/fit_sz 字号自适应/duotone 图片位/notes 挂载——换内容即出下一份 |
| `DESIGN.md` | Warm Terracotta 六要素规范（色板/字体/母题/图表规则/avoid list） |
| `check_geom.py` | 几何 QA：越界+中文溢出估算（LO-Noto 10% 误差内） |
| `prep_images.py` | PIL 统一阶调（deep duotone / soft / cover 压暗三模式） |
| `extract_notes.py` | 原稿→清洗→notes.json |
| `icons.mjs` | react-icons→sharp→PNG（改清单即用） |
| `make_cover.py` | PIL 封面纹理（渐变+圆+点阵+噪点） |
| `img_raw/meta.json` | CC 图片授权台账（署名来源） |
工作流脚本骨架（新任务复制 shuoke 目录改内容）。

## 5. 工程雷区（本会话真实踩过，全部要防）

- **本机 `grep` 被 rtk 代理劫持**：管道统计输出可能是 rtk 帮助文本——统计类一律 python3 正则，grep 结果异常必起疑
- `grep -c` 无匹配**退出码 1**，会把 `&&` 长链掐断——校验计数放链尾独立命令，或 `|| true`
- python-pptx：`PP_ALIGN` 参数不能传 0（抛 enum 错）；自写 `_fix()` 这类 helper 要**返回 run 而非 rPr**（否则 `.text=` 静默失效）；中文字体必须补 `a:ea` 槽且 schema 顺序 latin→ea→cs（`font.name` 只管 latin）
- OOXML XML 改写禁 `xml.etree.ElementTree`（毁包），用 lxml/defusedxml.minidom
- 图片：by-nd 禁改（duotone 即衍生）；4:2:0 JPEG 毁渐变；LibreOffice 无 CJK 字体→豆腐块
- pptx 渲染 QA 链必须 soffice→**pdf**→pdftoppm（`--convert-to png` 只出首页）；改完要重跑全链否则看旧图（本会话犯过：渲染链断裂→对着旧图核查）
- 卡内文字 autoshape 默认**居中**，显式设 alignment；箭头/符号对齐用同框高+MIDDLE 锚
- LibreOffice 字体替换 → 字宽判断不可信，交付说明里必带"真 PowerPoint 终检"提示
- 官方 pptx skill 20 条 pptxgenjs footgun 见其 SKILL.md，动手前先读；skill license=Proprietary，分发进 skills-cache 前查条款

## 6. QA 出口判据（缺一不算完）

① `validate.py` PASSED ② `check_geom.py` 全过 ③ 全页渲染逐张看（或子代理盲审，**结论逐条核实再采纳**——本会话 8 项盲审意见 1 项误判）④ 内容对账：原稿逐段→新稿，零遗漏零编造 ⑤ CC 署名核对 ⑥ 交付附真机终检提醒。

## 7. 与用户协作的节奏（本次有效模式）

诊断报告+路线选择 → 用户拍板 → 小样先行（4 页风格样张试"档次"口味，别全册赌方向）→ 结构纪律铺全册 → 迭代用"报页码+改参数重跑"低成本循环。"微调没感觉"= 触发信号：停止表层修，回 §2 换 Tier 层级动手。
