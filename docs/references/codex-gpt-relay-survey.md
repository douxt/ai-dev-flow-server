# Codex + GPT 中转站选型与 Windows/VSCode/WSL 落地调研报告

> 2026-09-13 · 方法：gale-research L4（R1 广度 → R2 深挖 → R3 终裁 → R4 缺口递归，全部跑完；实际用量 ~22 搜 / ~16 抓）
> 场景：在中国大陆通过 API 中转站使用 Codex CLI + GPT 系模型；宿主 Windows + VSCode，CLI 装在 WSL，希望有 UI 插件形态。
> 硬性排除：官方直连（不可达才找中转）、合租/共享账号池、不支持 Responses 协议的站。

## 1. 术语对照表

| 中文 | 英文 | 说明 |
|---|---|---|
| 中转站 | API relay / relay station | 转发端点，`base_url` 指向它即可调 OpenAI/Claude/Gemini 等；≠ 镜像站（镜像站是代理聊天 Web UI） |
| 聚合网关 | aggregator / LLM gateway | OpenRouter 类授权聚合；LiteLLM/new-api 类自托管网关 |
| Responses API | `/v1/responses` | OpenAI 新协议，**Codex 唯一可用协议**（chat/completions 支持已于 2026-02 硬删除） |
| 长会话压缩 | `/responses/compact`（remote compaction） | Responses 家族的可选端点，由 provider 能力决定走不走 |
| 降智 / 换芯 | model substitution | 付费模型被偷换成廉价模型；CISPA 审计 28 家端点 45.83% 身份不符 |
| Codex IDE 扩展 | `openai.chatgpt`（VS Code Marketplace） | 官方 UI 插件形态，与 CLI/App 共享 `~/.codex/config.toml` |

## 2. 候选对比总表

每格仅填有官方文档或独立来源可指认的事实；「需核实」= 无公开一手证据。

| 候选 | Responses 原生 | Codex 官方教程 | /responses/compact | 定价 vs 官方 | 大陆支付 | 独立性证据 | 判定 |
|---|---|---|---|---|---|---|---|
| **AiHubMix** | ✅ 文档明示（`base_url=https://aihubmix.com/v1` + `wire_api="responses"`） | ✅ 专页（更新 2026-06-25，含 model_catalog_json 多模型切换） | 自定义 provider 名 → 自动本地压缩，不踩 | ≈官方价 −10%（Claude 除外），按量无月费 | ✅ | 公司化运营多年、500+ 模型、透明度较高 | **存活·首推** |
| **CloseAI** | ✅ 官方教程（`base_url=https://api.openai-proxy.org/v1`） | ✅ 专页 | 同上安全 | 官方倍率、企业定位 | ✅ 支付宝/**可开票** | awesome 目录 🟢 active + 注册主体 | **存活·企业备选** |
| **Fenno (api.fenno.ai)** | ✅ 站方文档（`https://api.fenno.ai/v1`） | ✅ 专页 | 站方配置 `requires_openai_auth=true` 需实测 | <1 折（9.9 元≈$150 额度宣传） | ✅ 支付宝/微信 | Veridrop 独立 17 次实测中位 82/100「通过」；但技术栈为 Sub2API 通用模板、主体境外 CHANGXU LIMITED | **存活·低价试水，禁大额** |
| **OpenRouter** | ✅ 官方博客教程（2026-06-17） | ✅ | 自定义 provider → 本地压缩 | 官方价 +5.5% 充值费，无加价 | 支付宝✅（但见下） | 授权聚合商、已被 Stripe 收购（2026-08） | **降级**：2026 起账号级地域风控，国内账单地址+支付方式账号调用 GPT/Claude/Gemini 被屏蔽（HN #47702048、X @techeconomyana、港用户 threads 实测）。仅当有海外账单主体时可选 |
| 云雾 API | ⚠️ 自称"完全兼容 OpenAI 协议"，无 responses 专页 | ❌ | 需核实 | "与官方同步" | ✅ | 🟢 active canary、3 年口碑 | 备选（接 Codex 前需验 responses 实测） |
| LaoZhang | 模型表含 gpt-5.x-codex 但按"分组"浮动 | 部分 | 需核实 | — | ✅ | 🟡 分组/线路变动频繁 | 排除出首推（账号级不确定性大） |
| 非线智能 NoneLinear | ⚠️ 仅软文/SEO 来源称支持 responses | — | — | — | ✅ | 无独立验真记录进入视野 | 降为"需实测" |
| 神马中转/rcouyi/DMXAPI 等 | ⚠️ | — | — | — | ✅ | 目录标 🟡 unverified 或 operator-self | 排除（证据不足） |
| SEO 软文"夺冠站"（词元无忧、造梦者、千聚等） | 不作数 | — | — | — | — | 同批软文互推 | **排除（广告非评测）** |
| **自建 new-api / Sub2API** | 取决于你挂的上游 | ✅ 教程生态 | 可配 | 成本=你的上游 | — | 开源，数十家转站的底座 | **结构性方案**（有 Plus/Pro 账号者见 §6） |

## 3. 排除清单及原因

1. **官方 API 直连**——OpenAI 自 2024-07 起封锁中国大陆 API 访问，注册/支付/封号三重门槛（用户前提即排除）。
2. **共享账号池/合租**——违反硬性排除；且 OpenAI 对非官方客户端流量有主动限制（CLIProxyAPI #3937），体验无保障。
3. **仅 Chat Completions 的站**——Codex 0.80+/2026-02 起 `wire_api="chat"` 启动即报错，接不上（openai/codex discussion #7782）。
4. **OpenRouter（对国内账单主体）**——R4 闭合：账号级风控 = 账单地址+支付方式+IP 交叉判定，命中即屏蔽 OpenAI/Anthropic/Google 三家模型，甚至发封号邮件；支付宝能充值≠能调用。
5. **LaoZhang**——"当前账号可调用"与"厂商已发布"分离、按令牌分组浮动，无法从公开文档给出可证伪承诺。

## 4. 关键技术判断

**分化点（决定成败的三行配置）**：

1. **协议硬闸**：`wire_api = "responses"`。Codex 新增长这样：
   ```toml
   # ~/.codex/config.toml —— 必须用户级，项目级 .codex/config.toml 会忽略 model_provider
   model = "gpt-5.6-terra"              # 专用 codex 模型大多已退役，GPT-5.6 家族为当前默认
   model_provider = "relay"

   [model_providers.relay]
   name = "My Relay"                    # ⚠️ 千万别写 "OpenAI"，见第 3 条
   base_url = "https://aihubmix.com/v1" # 按站方文档给完整前缀（含 /v1），以文档示例原样为准
   wire_api = "responses"
   env_key = "AIHUBMIX_API_KEY"         # 或 experimental_bearer_token = "sk-..."（见 §6 扩展场景）
   ```
2. **保留 ID 雷区**：`openai`/`ollama`/`lmstudio` 是保留 provider ID，不能用覆写内置 `openai` 的方式接中转——必须新建自定义 ID（官方 Advanced Configuration 页明示）。
3. **compact 陷阱（已官方证实）**：remote compaction 能力由 `name == "OpenAI"` 严格判定的（codex-cli 0.152.1 源码，issue #42313 open 中）。自定义名 → 自动走本地压缩，**永远不要把中转站的 name 写成 "OpenAI"**——xairouter 等教程示例恰踩此雷，若该站缺 `/responses/compact` 会打出 502 长会话崩。
4. **采购前必测三项**：① 同一 prompt 指纹对比官方端点（veridrop.org 免费检测 / relay-radar）；② 流式 + 工具调用完整性（发一轮多 tool-call 任务看截断）；③ 小额充值跑一周看高峰 429 率。
5. **行业级风险底色**（选型时必须接受的前提）：CISPA《Deceptive Model Claims in Shadow APIs》审计 17–28 家，45.83% 端点模型身份不符；2026-06 中方（国家安全部/科技日报）公开发文警示中转站数据泄露与后门风险。**纪律：只小额多次充值、代码里留双站 fallback、敏感仓库数据不走中转。**

**WSL + VSCode 集成判断（用户场景核心）**：

- 扩展与 CLI **共享同一套 `~/.codex/` 配置**，但注意双份现实：扩展跑在哪侧，哪侧的 `~/.codex` 才生效。官方支持开关 `chatgpt.runCodexInWindowsSubsystemForLinux = true`（VSCode settings.json）→ 扩展的 Codex 运行时进 WSL，读 **WSL 内** `~/.codex/config.toml`——与 CLI 完全统一，配置一次全端生效。
- 扩展自定义模型选择器有历史 bug（#6963/#4558/#27695，桌面端 #19694/#15138）：`/model` 列表可能不显示自定义模型。**绕过法**：`config.toml` 写死 `model = "..."`，实际请求即按它走（去站方日志验证真实 model_id，勿信"你是哪个模型"）。
- 网络路径：AiHubMix/Fenno 这类站域名**大陆可直连，WSL 内无需任何代理**——这正是中转站方案对 WSL 用户的最大红利。只有走 ChatGPT OAuth 登录或 OpenRouter 才需要代理链；届时的已验证解法：`.wslconfig` 开 `networkingMode=mirrored`（Win11 22H2+），或 VSCode `http.proxy` 指 Windows 宿主 Clash（7897）——注意 User 栏与 Remote[WSL] 栏不能同时设不同代理，冲突即无限 Reconnecting（#8814 官方定性为网络配置问题并关闭）。
- 验证链：WSL 内 `curl -s <站>/v1/responses -H "Authorization: Bearer $KEY" ...` 200 → `codex "reply only yes"` → VSCode 新会话（改配置后须 Reload Window 或全退重启，扩展不热加载 config）。

## 5. 缺口裁决表（L4）

| # | 待证问题 | 裁决 | 证据 |
|---|---|---|---|
| G1 | OpenRouter 对大陆账号的地域风控 | **已闭合（坐实，降级）** | HN #47702048「account-level regional restrictions」；X @techeconomyana 支付方式风控；港用户账单地址审核 threads；reddit 俄用户封禁邮件 |
| G2 | VSCode 扩展 WSL 模式用 custom provider 是否现行可用 | **仍存疑→给出现方案** | xairouter 指南（2026-03）与 bettertoken 文档（当前版）均给出可用配置；但官方从未公告修复 #6963，属"第三方一手可用、官方口径未确认"——列为采购前必测项 |
| G3 | Fenno 低价档真实限制（限速/限模型/周额度） | **未闭合** | 未取得条款原文；仅有 realNyarime 一手转述「9.9 体验包=30 天每周 $38」。处置：1.99 美元试用档实测，不升订阅 |
| G4 | AiHubMix 模型验真成绩 | **未闭合** | Veridrop 总榜（付费认证制）未见其名；无负面记录。处置：注册后用 veridrop 免费检测自测一次 |
| G5 | provider `name` 误触发 remote compaction | **已闭合（方向反转为安全）** | #22042 官方答复 + #42313（open）源码定位：非 "OpenAI" 名 → 本地压缩。规避规则唯一且确定 |

R4 后未闭合 2 条（G3/G4）<3，且均为"小额试用即可自证"性质，**不触发 R5**。

## 6. 推荐结论

**分场景选型**：

| 场景 | 推荐 | 理由 |
|---|---|---|
| **主力（默认推荐）** | **AiHubMix** | 官方 Codex 教程最全、Responses 原生、≈官方价−10% 按量付费不逼囤款、公司化多年 |
| 低价试水 | Fenno（api.fenno.ai） | 独立验真 82/100 通过 + 阮一峰背书，但**只用 $1.99/9.9 元档验证，月上限控制在损失可接受额** |
| 企业/报销 | CloseAI | 注册主体 + 发票，合规叙事最好 |
| 有海外账单主体 | OpenRouter | 模型最全 + failover + Stripe 背书，费用透明（5.5% 手续费） |
| 已有 ChatGPT Plus/Pro | 自建 **Sub2API/new-api**（VPS 上转 `/v1/responses`） | 零充值风险、订阅额度复用；自担账号封禁风险，教程生态成熟（linux.do、awesome 目录） |
| 结构兜底 | 任意两站 + `profiles` 热切 | Codex 原生支持 `codex --profile xxx`，主站故障一条命令切换 |

**落地清单（Windows + VSCode + WSL CLI + UI 插件，推荐形态）**：

1. WSL 内装 CLI：`npm install -g @openai/codex`（Node≥18；项目放 `~/`  ext4 侧，勿放 `/mnt/c`）。
2. VSCode 设置：`{ "chatgpt.runCodexInWindowsSubsystemForLinux": true }` → 扩展运行时统一进 WSL。
3. 从 WSL 开 VSCode：`code .`（左下角确认 `WSL:` 绿标）。
4. WSL 内 `~/.codex/config.toml` 按 §4 模板配 AiHubMix（根键写在 `[model_providers.*]` 表之前——TOML 硬规则）；`~/.bashrc` 里 `export AIHUBMIX_API_KEY=...`。
5. 全退 VSCode 重开 → 侧边栏 Codex 图标（不出现就命令面板 `Codex: Open Codex Sidebar`）→ 发一条任务 → **AiHubMix 控制台日志页核对 model_id**（唯一可信验证点）。
6. 网络：以上全程无需代理；若某站域名被墙，第一反应是换站而非配代理链——中转的初衷就是免翻墙。
7. 安全纪律：小额充值、敏感仓不用、留第二站 key、月度跑一次验真。

## 7. 来源列表

**协议/配置一手**
- https://learn.chatgpt.com/docs/config-file/config-advanced （自定义 provider/保留 ID/auth 命令）
- https://learn.chatgpt.com/docs/codex/ide （扩展官方页）
- https://github.com/openai/codex/discussions/7782 （chat 协议退役）
- https://github.com/openai/codex/issues/22042 （compact 降级，官方答复）
- https://github.com/openai/codex/issues/42313 （name 判定 compaction，open）
- https://github.com/openai/codex/issues/6963 / #4558 / #27695 （扩展×custom model 历史）
- https://github.com/openai/codex/issues/8814 （WSL Reconnecting=代理配置，closed）
- https://github.com/openai/codex/discussions/5471 （WSL 支持测试帖）

**站点官方**
- https://docs.aihubmix.com/cn/api/Codex-CLI · https://docs.aihubmix.com/cn/api/Responses-API
- https://doc.closeai-asia.com/tutorial/integrations/codex-cli.html
- https://api.fenno.ai/ · https://developer.cloud.tencent.com/article/2713760
- https://yunwu.ai/ · https://docs.laozhang.ai/api-capabilities/model-info
- https://openrouter.ai/blog/tutorials/codex-cli-openrouter/ · https://openrouter.ai/docs/faq
- https://xairouter.com/en/blog/vscode-codex-plugin-windows-macos-guide/ · https://docs.bettertoken.ai/en/ai-tools/codex-vscode

**中立目录/验真/风险**
- https://github.com/howardpen9/awesome-ai-api-proxy （信任标记+周度价格快照）
- https://veridrop.org/leaderboard · https://veridrop.org/leaderboard/api.fenno.ai
- https://arxiv.org/html/2603.01919v1 （CISPA shadow API 欺诈审计）
- https://news.ycombinator.com/item?id=47702048 （OpenRouter 账号级地域限制）
- https://www.stdaily.com/web/gdxw/2026-06/08/content_528897.html · https://wap.eastmoney.com/a/202605123734319957.html （官方风险警示/起底报道）
- https://github.com/zzsting88/relayAPI · https://www.aiapipk.com/
- https://github.com/QuantumNous/new-api · https://github.com/Wei-Shaw/sub2api （自建）
