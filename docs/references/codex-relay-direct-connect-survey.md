# 国内直连中转站选型调研报告（Codex + GPT）

> 2026-09-13 · 方法：gale-research L4（R1 广度 → R2 深挖 → R3 终裁 → R4 缺口递归）；核心判据=**本机 WSL 无代理实测**（DNS + 443 + `/v1/responses` 无钥差分探测），网络快照 2026-09-13，随运营商/时间漂移，选用前复测。
> 场景：大陆网络免代理直连调用 GPT 系模型喂 Codex CLI（承接前报 [codex-gpt-relay-survey.md](codex-gpt-relay-survey.md)，协议门槛/WSL 集成细节不重复）。
> 硬性排除：不可直连的站（含 AiHubMix/云雾）、仅 Chat Completions 协议、共享账号池。

## 1. 术语对照

| 术语 | 含义 |
|---|---|
| 官转 / AZ / 逆向 | 上游渠道三态：OpenAI 官方 Key 转发 / Azure OpenAI / 网页逆向（封号+降智高危）。官转合理价=**原价~8折**，显著低于此即"渠道有鬼"（CSDN/掘金避坑文共识） |
| 倍率 | new-api 体系计费：实际扣费 = 官方价 × 模型倍率 × 分组倍率，≠"官方价的 N 倍"字面义 |
| 无钥差分探测 | 本方法：`POST /v1/responses` 返回 401/403（鉴权闸）=端点存在；404=未实现。对照 `POST /v1/__nope__`=404 排除"全站都 404"假阴性 |
| cheap-trap | 报价 < 聚合基准 50% 的站，多为换芯/引流/跑路前兆（awesome-ai-api-proxy 风险旗标） |

## 2. 候选对比总表（9 家直连存活者 + 对照组）

实测=本机 curl 无代理；探测=响应码见 §1。**全部 9 家 `/v1/responses` 探测通过（401 鉴权闸）**。

| 站点 | 直连 | 首包* | Responses 证据 | 定价口径 | 支付 | 信任信号 | 负面信号 |
|---|---|---|---|---|---|---|---|
| **API易** api.apiyi.com | ✅ | 0.89s | 专文档《Responses API Native Guide》+ 实测披露自家限制 | 官转~85 折宣传 | 支付宝 | **唯一诚实标注实现限制**（store/previous_response_id 不生效、conversations 404）；文档常新 | gpt-5.6-sol 报 $5/$30 ≈ OpenRouter 口径 **2.5×**（口径冲突，购前必测）；Codex 教程页停留旧配置范式 |
| **V-API** api.gpt.ge | ✅ | 0.83s | 探测✅ + 站内 Codex 教程页 | 0.658–0.779 倍（健康官转折扣带） | 支付宝 | 老牌（2023 至今）、ToS 载退款条款、调价公告制、声明不存请求正文、售后 QQ 公开 | 未检索到独立验真记录（也未见投诉实锤）；倍率计费体系需自行换算 |
| **No.1-API** api.rcouyi.com | ✅ | 1.2s | 探测✅ + 官方文档专页《Codex 最佳 API 配置教程》 | 倍率制（页 JS 渲染未取证） | 支付宝/微信 | 🟢 active（目录 canary 2026-05-26）；**国内华为云 IP** | TG 频道曾流传其硬编码泄露 key 配对（勿用分享 key）；无独立验真 |
| **CloseAI** api.openai-proxy.org | ✅ | 1.1s | 探测✅ + 官方 Codex 专页 | 1.25–1.5×（全场最贵） | 支付宝/**发票** | 注册主体、企业客户名单、目录🟢 | linux.do 集中投诉：降智佐证帖多帖、"封下游号"、贵 |
| **非线智能** api.nonelinear.com | ✅ | 0.74s | 探测✅（/v1/models 甚至 200 公开） | 8–9.5 折宣传 | 支付宝 | 背后评测公司实体真实（chinese-llm-benchmark 开源 6k+ stars）、cc-switch 有预设 | 传播几乎全自家博客（SEO），无第三方实测 |
| **Fenno** api.fenno.ai | ✅ | **2.8s 最慢** | 探测✅ + 官方配置文档 | <0.1× | 支付宝/微信 | Veridrop 17 测中位 82/100 | 见前报：境外主体、通用模板、个人背书 |
| **柏拉图** api.bltcy.ai | ✅ | 0.99s | 探测✅ | 1 元≈1 刀额度（≈0.14×） | 支付宝 | 渠道分组（官方/逆向/Azure）公示透明 | **落入 cheap-trap 带**；调价"随行情"公告制=不锁价；无主体信息 |
| **DMXAPI** www.dmxapi.cn | ✅ | **0.43s 最快** | 文档明示 `/v1/responses` + 探测✅ | ~7 折、1 美元起充 | 支付宝 | 阿里云国内 IP（延迟红利）、有运营日志/承诺页 | 目录标 🟡 no-entity；"适配 NewAPI Responses"可能为转换层非原生 |
| 云雾 yunwu.ai / AiHubMix | ❌ | — | — | — | — | — | DNS 污染直连失败（本机），出局 |
| nsmao | ✅站 | — | **探测 404 协议不通** | — | — | — | **排除（协议硬闸）** |

*首包=TCP+TLS+HTTP 往返，静态页量级，只作相对参考。

## 3. 排除清单及原因

| 对象 | 排除原因（可证伪出处） |
|---|---|
| **302.AI** | "国内直连"卖点的最大布道者，**本机实测 302.ai 与 api.302.ai 双双超时**——营销口径被一手证据证伪 |
| OhMyGPT | 直连失败 + 自家公告承认谷歌云渠道折扣退坡回调 9 折（渠道依赖裸露） |
| AICodeMirror | 直连恒 403（CF 拦截）无法程序化使用 + linux.do"粉转黑"售后口碑崩坏 |
| codex789 (island) | GPT-5.6 标 0.05× 倍率 = 官方 0.5 折，远超经济学可行区间，典型 cheap-trap |
| nsmao | `/v1/responses` 探测 404，协议硬闸不过 |
| 云雾 / AiHubMix / OpenRouter | 直连不可达（前两类 DNS 污染）/ 账号级地域风控（OpenRouter，前报 G1） |
| gptapi.us | 易与 gpt.ge 混淆，V2EX 有避雷帖，非本次对象 |

## 4. 关键技术判断

1. **"国内直连"声称 ≈ 必测项**：本次 23 域名探测中，软文头部的 302.AI、OhMyGPT 恰恰直连失败，而被软文冷落的 gpt.ge、apiyi、rcouyi、dmxapi 反而全通。**软文口径与可达性负相关**，一手探测方法：`curl -4 --noproxy '*' https://<域名>/v1/responses -X POST -d '{}'`（401/403=可用闸，404=没做）。
2. **协议≠保真**：探测只证明网关挂了 `/v1/responses` 端点（new-api 系多为协议转换壳）。转换层对 reasoning 项/工具调用流的保真度无法远程审计——**接入后必须 canary 自测**：同一 prompt 对照官方输出指纹、核对 `usage.reasoning_tokens` 是否存在、长对话验证前缀缓存计费命中（缓存读应 ~0.1×）。
3. **倍率价 sanity 区间**：官转健康带 = 原价~8 折（V-API 0.66–0.78×、非线 0.8–0.95×、APIYi~0.85× 在带内）；<0.2×（bltcy 0.14×、codex789 0.05×、Fenno <0.1×）本质是渠道套利或换芯，只能当"可牺牲的低价档"；>1.2×（CloseAI）卖的是合规不是模型。
4. **法律风险置顶**：2026-05 起中转站站长已有**刑拘 37 天/取保候审**案例（帮绕过网络访问限制+非法经营定性），国家安全部公开警示，上游 OpenAI/Anthropic 律师函+封 IP 清洗进行中。"国内直连"四个字本身就是风险来源——**只用于非敏感个人项目，禁止公司数据过站，大额充值=法律+资金双重敞口**。
5. **Codex 配置沿用前报三铁律**：`wire_api="responses"`；provider `name` 勿写 `"OpenAI"`（#42313）；自定义 provider 走本地 compaction 故 `compact` 无需担心。APIYi 文档补充：GPT-5.4+ 在 chat 端点"工具+推理"互报 400，Responses 端点无此限制——Codex 天然走 Responses，不受影响。
6. **国内落地机 IP 是直连红利源**：DMXAPI（阿里云 101.37）、rcouyi（华为云 150.138）走国产云落地，0.4–1.2s；纯 Cloudflare/CloudFront 的站（Fenno 2.8s）能通但慢。**延迟差对 Codex 长 agentic 会话是真金白银**（每回合都付 RTT）。

## 5. 缺口裁决表（L4）

| # | 待证问题 | 裁决 | 证据 |
|---|---|---|---|
| K1 | No.1-API Codex 支持 | **已闭合** | 官方教程页 platform.rcouyi.com/8235761m0 + 探测 401 鉴权闸 |
| K2 | V-API responses 真实实现 | **已闭合（存在性）/保真存疑** | 探测✅；倍率制文档；转换层保真无一手审计 → 转采购前必测 |
| K3 | APIYi 文档时效 | **已闭合** | Responses Native Guide 基于 2026-06/07 官方文档，自曝限制（罕见诚实信号） |
| K4 | bltcy "1元≈1刀"上游实质 | **未闭合→按 cheap-trap 处置** | linux.do 调研帖+目录注记；无渠道构成证据。降级为可牺牲低价档 |
| K5 | DMXAPI 原生 vs 转换 | **仍存疑** | 文档称"适配 NewAPI Responses"（=new-api 转换壳特征），no-entity |
| — | APIYI 价格口径冲突（$5/$30 vs OR $2/$10） | **新发现未闭合** | 两家报价互斥，OpenRouter 为目录基准列 → 充值前以自己实测 token 账单为准 |

未闭合均 <3 条且全属"小额自测即证"，不触发 R5。

## 6. 推荐结论

**分层推荐（直连 + Codex 前提）**：

| 角色 | 选择 | 一句话理由 |
|---|---|---|
| **主力首选** | **API易**（api.apiyi.com） | 直连 0.89s + Responses 文档最透明（诚实自曝限制=最稀缺信号）+ 官转折扣带内；⚠️ 充前用 canary 复核其 5.6 系列实际单价 |
| **次主/寿命备选** | **V-API**（api.gpt.ge） | 老牌 3 年+、0.66–0.78× 健康带、退款条款+调价公告公开；与 APIYi 双站互为 fallback |
| 极限低延迟试点 | DMXAPI（www.dmxapi.cn） | 国产云落地 0.43s、1 美元起充试错成本最低；no-entity 故只放小额 |
| 企业报销 | CloseAI | 唯一发票通道，但为"合规溢价"付 1.25–1.5× 且自担社区降智投诉史 |
| 不推荐主用 | Fenno/bltcy/codex789 | cheap-trap 带或慢（Fenno 可留 $1.99 档玩具位）；codex789 直接放弃 |

**接入动作清单**（WSL，承接前报 §6）：
1. 注册 APIYi + V-API，各小额（$5–10）充值。
2. WSL `~/.codex/config.toml`：
   ```toml
   model = "gpt-5.6-terra"
   model_provider = "apiyi"

   [model_providers.apiyi]
   name = "APIYi"                      # 勿写 "OpenAI"
   base_url = "https://api.apiyi.com/v1"
   wire_api = "responses"
   env_key = "APIYI_API_KEY"
   ```
   同构再配一个 `[model_providers.vapi]`，故障时 `codex -c model_provider="vapi"` 一键切。
3. 验真三板斧（一次性）：① canary prompt 对照已知输出；② 查 `usage` 含 `reasoning_tokens`；③ 连发同前缀长请求看 `cached_tokens` 是否按 0.1× 计——三项全过再升额度。
4. 敏感仓库一律走 `--profile` 隔离到官方通道（若有），中转 profile 只开非敏感项目。
5. 每月复测直连性（§1 探测命令），域名/政策漂移在整治风暴期是常态而非例外。

## 7. 来源列表

**一手实测（本机，2026-09-13）**：§2 全表 DNS/443/responses 探测——命令可复现：`curl -4 --noproxy '*' -m 8 -X POST https://<域名>/v1/responses`

**站点官方**
- APIYi：https://docs.apiyi.com/en/api-capabilities/openai/native · https://help.apiyi.com/codex-cli-apiyi-integration-tutorial.html · https://docs.apiyi.com/zh-Hant/api-capabilities/gpt-6-astra/overview
- V-API：https://api.gpt.ge/help · https://gpt.ge/terms/terms-of-service · https://api-gpt-ge.apifox.cn/
- No.1-API：https://platform.rcouyi.com/8235761m0 · https://api.rcouyi.com/pricing
- CloseAI：https://doc.closeai-asia.com/tutorial/integrations/codex-cli.html · https://www.closeai-asia.com/pricing · https://www.closeai-asia.com/blog/openai-banned-my-1000-dollar-account
- 非线智能：https://nonelinear.com/ · https://blogs.nonelinear.com/（vendor blog，降权）
- Fenno / bltcy / DMXAPI / codex789：https://api.fenno.ai/ · https://wiki.bltcy.ai/node/019830d3-1505-7f28-b300-ef91d7a26734 · https://www.dmxapi.cn/ · https://www.codex789.com/

**独立评测/目录/监控**
- https://github.com/howardpen9/awesome-ai-api-proxy （信任旗标/价格快照基准）· https://github.com/zzsting88/relayAPI · https://www.aiapipk.com/ · https://veridrop.org/leaderboard/api.fenno.ai · https://linux.do/t/topic/189618 · https://linux.do/t/topic/1151079 / 381865 / 272774 / 445072（CloseAI 负面串）· https://x.com/manateelazycat/status/2013658966275010634 · https://v2ex.com/t/1027837

**渠道科普/风险背景**
- https://juejin.cn/post/7506050992095379466 （官转/AZ/逆向辨别）· https://aicoding.csdn.net/6a2a1fc810ee7a33f27ac708.html （2026 大清洗）· https://x.com/mankunlaw/article/2079152196290236865 （站长刑拘法律分析）· https://www.storm.mg/article/11154298 （整治扫荡）· https://news.cctv.com/2026/06/08/ARTI3GCnklsTtGMnYfykzJ75260608.shtml （国家安全部警示）· https://m.36kr.com/p/3807583717416456 · https://zhuanlan.zhihu.com/p/2069804667291296765 （黑灰产价格拆解）· https://linux.do/t/topic/2680943 （直连实践调查）
- Codex 协议链（沿用前报）：learn.chatgpt.com/docs/config-file/config-advanced · openai/codex #22042/#42313/7782
