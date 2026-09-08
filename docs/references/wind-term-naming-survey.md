# 风力中间档命名调研报告（tiered-research 改名候选）

> 2026-09-08 · L3 档（3 轮，实际止于 R3——收益闸门：R3 新增关键事实 <2 条候选反转，无 R4 必要）
> 场景：效仿 storm 命名家族，找"明显轻于 storm、明显重于 breeze"的风力词作为调研技能名；直接搜索=微风，storm-research-lite=风暴。
> 硬性排除：气象体系外的词；生僻无风力联想的词；撞名须标注。

## 1. 术语对照表（中英）

| 英文 | 中文 | Beaufort | 风速 | 直觉意象 |
|---|---|---|---|---|
| (Light/Gentle) Breeze | 微风 | F2~3 | <19 km/h | 树叶摇动 ←"直接搜一下" |
| Moderate/Fresh/Strong Breeze | 和风/清风/强风 | F4~6 | 20~49 | 举伞困难 |
| Near Gale | 疾风 | F7 | 50~61 | 迎风步行不便 |
| **Gale** | **大风** | **F8** | **62~74** | **树枝折断** ← 正中档 |
| Strong Gale（UK 报"Severe Gale"） | 烈风 | F9 | 75~88 | 屋顶飞瓦（建筑受损起点） |
| Storm | 狂风/风暴 | F10~11 | 89~117 | 树被拔起 ← storm-research |
| Hurricane | 飓风 | F12 | 118+ | 摧毁 |

关键区分：squall/gust=短时阵风**时间轮廓**（非强度档位）；tempest=storm 文学同义词；Beaufort 为 10 分钟平均风速，非阵风。

## 2. 候选对比总表

| 候选 | 档位居中性 | 日常认知度 | 撞名核实 | 判定 |
|---|---|---|---|---|
| **gale** | ✓ F8，教科书答案（breeze 3-6 与 storm 10 之间）；NWS 34-47kt，Beaufort F8-9 | 高（gale-force wind 为英语常用语） | ⚠ Tomorrow.io AI 天气智能体"Gale"(含 Gale API/MCP)；⚠ Cengage 文献库 Gale（调研场景联想碰撞）；◦ 小项目若干(mod manager/GHA executor)，无著名开源 AI 框架 | **推荐** |
| squall | ✗ 非速度轴档位：≥16kt 突增持续数分钟，平均风速常低于 gale | 中（"飑线"联想雷暴） | 干净 | 排除 |
| strong gale / 烈风 | F9，居中但偏 storm 侧 | ✗ "strong"修饰语在日常英语不传递升档（Met Office 弃用改"severe"实证） | 干净 | 排除 |
| near gale / 疾风 | F7，居中偏 breeze 侧 | ✗ 带"near"前缀命名不干脆；疾风 无英文对应传播度 | 干净 | 排除 |
| williwaw | "突然猛烈"=偏强+时间轮廓 | ✗ 大众不识 | 干净 | 排除（趣味不敌可用性） |
| simoom/bora/mistral | ✗ 实测均达飓风级阵风（bora 190mph katabatic 记录） | ✗ 生僻 | — | 排除 |
| zephyr | 对照组：=gentle breeze 本尊（Merriam-Webster 定义） | 高 | — | 证伪（太轻） |
| tempest | =violent storm（Merriam-Webster） | 高但古雅 | 与 storm 同级，不居中 | 证伪 |
| monsoon/typhoon/cyclone/whirlwind/twister | 均 storm 级及以上或季节性系统 | — | — | 排除 |

## 3. 排除清单及原因

- squall：语义轴错误（时程非强度）；调研是持续多轮过程，"几分钟突袭"意象相反
- strong gale/severe gale：F9 已近 storm 侧且语言学升档信号失效（R3 对抗复查实证）
- 地方风名（williwaw/simoom/bora/mistral/chinook）：强度要么失控要么不可知，认知度一票否决
- 热带气旋系（typhoon/hurricane/cyclone/depression）：要么=storm 要么>storm，无中间位
- 中文直名（大风/烈风）：skill 名需 kebab-case 英文，拼音 daifeng 不可读

## 4. 关键技术判断

**分化点**：撞名清单里真正需要权衡的只有 Cengage Gale——它是"研究文献数据库"品牌，与调研技能语义场重叠；但 (a) 本名是个人本地 skill 非公开产品，无商标法域问题；(b) "gale" 词根本身通用描述性弱（气象通用词），品牌方无从主张；(c) 用户心智里技能只在 /斜杠命令 出现，不与 Cengage 检索场景同屏。

**采购前必测项**：改名后跨仓库引用清理完整性（storm description 的路由句、README、symlink、记忆索引）——见 §5 落地清单。

## 5. 推荐结论

**首选 `gale-research`**（/gale 简触发；旧说法"tiered"在 description 保留兼容注记）：
- 家族叙事完整：breeze（随手搜）< **gale-research**（递进调研 L1~L4）< storm-research-lite（多视角风暴）——三档风力精确对应三件工具量级，这正是 storm 命名法的精髓延续
- Beaufort F8 有官方出处的"正中间"；中文对译"大风"略平，但英文 gale 词汇势能好（gale-force=常用强化语）
- L1~L4 档位可顺势改称"风力等级"隐喻（gale force 8 本身就叫 force!）——现有契约表零改动，文案可玩"升档=加风力"双关

**次选（若要零碰撞）`whirlwind`**：习语"whirlwind tour(旋风式考察)"与调研天然契合、认知度高、撞名少；缺点：意象偏"快而广"而非"强"，档位上属龙卷侧不严格居中。

**分场景**：纯个人工具 → gale-research 无悬念；未来可能公开发布 → 可改 gale-force-research 或选 whirlwind 避开 Cengage。

## 6. 来源列表

- Royal Meteorological Society Beaufort 全表：https://www.rmets.org/metmatters/beaufort-wind-scale
- Wikipedia Gale（NWS 34-47kt、F7-10 四档名、词源）：https://en.wikipedia.org/wiki/Gale
- NWS Marine Definitions / Coastal Warning Display：https://www.weather.gov/key/marine_definitions · https://www.weather.gov/marine/cwd
- Met Office（strong gale→severe gale 公关改名实证）：https://weather.metoffice.gov.uk/guides/coast-and-sea/beaufort-scale
- Merriam-Webster tempest/zephyr 定义：https://www.merriam-webster.com/dictionary/tempest · /zephyr
- BOM squall 定义：https://www.bom.gov.au/resources/learn-and-explore/marine-knowledge-centre/wind-gusts-and-squalls
- 中文蒲福风级对照（HKO/深圳台风网/和风天气）：https://www.hko.gov.hk/tc/education/weather/meteorology-basics/00112-beaufort-wind-scale.html · https://tf.121.com.cn/web/wiki/windLevel.html
- 撞名核实：https://support.tomorrow.io/hc/en-us/articles/16557265262868 · https://www.gale.com/ · https://github.com/Kesomannen/gale · https://github.com/aweris/gale
- 社会语言学（大众风力词无标定）：https://pmc.ncbi.nlm.nih.gov/articles/PMC7878797/
