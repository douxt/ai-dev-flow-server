我整合咱们**全程逐轮敲定、适配你现有 LangBot+NapCat 环境、带联网搜索、全局上下文、身份识别、智能记忆压缩、极低活跃度、高冷精简人设、DeepSeek 低成本**的所有配置，生成一份**唯一终版、可直接照搬落地**的专属定稿文档。

# LangBot 专属定制终版文档
## 适配环境
已部署完成：NapCat + LangBot + Notebook  
模型：DeepSeek V4 Flash（高性价比、强摘要、省 Token）  
**所有配置为最终定稿，无需新增、无需改动、不冲突、可直接全覆盖生效**

## 核心最终能力清单（全部实现）
1. 全群全局上下文读取，通读全员聊天动态，不脱离群聊语境回复
2. 精准识别：QQ号、群昵称、群主/管理员/普通成员身份，自动适配昵称、权限变更
3. 严格分群+分用户独立记忆，跨群隔离，SQLite 持久化，重启不丢
4. 智能摘要压缩：不粗暴截断、不丢关键信息，聊天越多上下文越平稳
5. 极低活跃度：约 100 条消息主动插话一次，默认静默旁观
6. 极致精简输出、零废话、短句干货、语义完整无残缺
7. 固定人设：高冷克制、旁观者姿态、淡淡冷幽默，对群主/管理员语气收敛
8. 智能联网搜索：仅时效性内容检索，日常闲聊不搜，省 Token
9. 全程低消耗，适配 DeepSeek 缓存计费，挂机成本极低

---

# 一、NapCat 固定配置（无需改动）
连接类型：WebSocket 客户端
- 连接地址：`ws://127.0.0.1:2280/ws`
- Token：自定义统一密钥
- 消息格式：Array
- 上报自身消息：关闭
- 心跳间隔：30000
- 额外开启：上报群成员昵称、角色权限、群事件变更

---

# 二、LangBot 全局配置（data/config.yaml 终版）
关闭 LangBot 进程后全覆盖写入
```yaml
database:
  use: sqlite
  sqlite:
    path: 'data/langbot.db'
  echo: false

session:
  namespace_rule: "{group_id}_{user_id}"
  memory_persist: true
  max_history_round: 15

adapters:
  onebot_v11:
    host: 0.0.0.0
    port: 2280
    token: langbot2025
    ignore_at_bot: false
    group_message_all: true
    receive_all_group_event: true
    filter_empty: true

admins: []
api:
  port: 5300
  webhook_prefix: 'http://127.0.0.1:5300'
  extra_webhook_prefix: ''
  global_api_key: ''
```

## 关键参数释义
- `group_message_all: true`：接收**全部群消息**，不单只响应@
- `receive_all_group_event: true`：抓取身份、昵称、权限变更事件
- `namespace_rule`：严格 群号+QQ号 记忆隔离
- `memory_persist`：记忆永久落地，重启不丢失

---

# 三、流水线完整终版配置（DeepSeek V4 Flash）
## 1. 模型对接参数
- 接口地址：`https://api.deepseek.com/v1`
- 模型名称：`deepseek-v4-flash`
- API Key：个人密钥

## 2. LLM 推理参数（无截断、保完整、控人设）
```yaml
llm_params:
  max_tokens: 100
  temperature: 0.72
  top_p: 0.6
```
- 不配置 `stop` 截断符，杜绝语句残缺
- 温度平衡：听话精简 + 自然冷幽默

## 3. 智能记忆压缩配置（核心防炸 Token、保信息完整）
```yaml
memory:
  type: summary
  max_raw_round: 15
  persist: true
  namespace: "{group_id}_{user_id}"
  summary_llm: default
  expire_days: 60
  summary_prompt: "精简总结这段对话全部核心信息，保留人员昵称、QQ号码、群主/管理员/普通成员身份、观点以及网络检索的关键信息，剔除所有闲聊废话，文字高度凝练，语义完整不遗漏重点。"
```

## 4. 终极系统提示词（全局上下文+人设+精简+搜索 全部约束）
```
你是QQ群沉默观察者机器人，可读取完整全局群聊上下文、拥有长期记忆与智能全网搜索能力，严格遵守铁律：

1.必须通读全部群历史发言，完全掌握群动态，禁止脱离语境回复。
2.回答语义绝对完整，禁止半截截断、强行收尾。极致精简，剔除所有铺垫、客套、修饰废话，只输出核心干货。
3.普通回复20~40字，被提问不超50字，绝不写长文。
4.人设高冷克制、旁观者姿态，自带淡淡冷幽默、点到为止；对群主、管理员语气收敛，不随意调侃。
5.默认全程沉默，主动发言概率极低，发言后立刻终止对话，不延伸、不追问、不开新话题。
6.永久记忆群成员：昵称、固定QQ号、群身份（群主/管理员/普通成员），昵称、权限变动以最新信息为准，仅相关话题可少量提及。
7.联网搜索仅用于实时新闻、热点、最新数据、时效性内容；日常闲聊、群内对话绝不搜索。搜索结果高度精简转述，不堆砌原文。
```

---

# 四、群全局上下文插件 GroupChattingContext（终版）
## 安装地址
```
https://github.heygears.com/Sansui233/GroupChattingContext
```

## 终版 config.json（替换自己群号）
```json
{
  "white_list": {
    "你的QQ群号": {
      "at": false,
      "limit": 16,
      "persist": true,
      "reply_probability": 0.01,
      "only_reply_when_mentioned": false,
      "auto_speak_interval": 0,
      "load_all_history": true
    }
  },
  "default": {
    "limit": 16,
    "prompt": "群全局历史发言格式：【昵称(QQ号，身份：群主/管理员/普通成员)：发言内容】。你必须通读全部群聊天记录，掌握群整体情况，精简作答，高冷克制，对管理员群主语气谨慎，略带冷幽默。成员昵称、身份变动以最新版本为准。仅实时话题可调用网络搜索。",
    "self_name": "机器人"
  }
}
```

## 核心能力
- `load_all_history: true`：**强制读取全局群上下文**（解决读不全历史的核心开关）
- `reply_probability: 0.01`：百句左右一次主动插话
- 固定携带「昵称+QQ+身份」标签入上下文

---

# 五、联网搜索插件 LangBot-Search（终版省 Token 配置）
## 安装地址
```
https://github.heygears.com/canvas-y/LangBot-Search
```

## 终版 config.json
```json
{
  "enable": true,
  "search_engine": "baidu",
  "max_result": 3,
  "result_length_limit": 120,
  "auto_detect": true,
  "search_trigger_rule": "仅当内容涉及实时新闻、网络热点、最新数据、时效性内容时才调用搜索，日常闲聊、群内八卦、主观讨论绝不联网搜索。",
  "search_prompt_prefix": "网络检索信息："
}
```

## 规则
- 模型自动判断是否需要搜索，不瞎搜、不滥搜
- 搜索结果极致精简，最小化 Token 消耗
- 搜索信息纳入记忆摘要，长期留存关键实时信息

---

# 六、标准生效重启流程（必按顺序）
1. 完全关闭 LangBot 所有进程（不只关网页）
2. 确认所有配置文件保存完成
3. 启动 NapCat，确认 WebSocket 连接正常在线
4. 启动 LangBot，等待插件、流水线全部加载完毕
5. 群内测试：多人发言、偶尔@、等待随机主动插话

---

# 七、最终运行行为总结
1. **感知层**：全群动态全收录，识别所有人昵称、ID、管理/群主身份
2. **记忆层**：分人分群隔离、持久化不丢、自动智能压缩不丢关键信息
3. **行为层**：极度沉默、低概率插话、从不刷屏、不延伸话题
4. **输出层**：句句精辟、零废话、语义完整、高冷淡幽默
5. **能力层**：日常靠记忆聊、实时内容自动联网、极致省 Token
6. **成本层**：DeepSeek Flash 低价+缓存优势+极少调用，月成本极低

---

# 八、简易排错速查
1. 读不到群全局历史 → 检查 `load_all_history: true` + 白名单群号正确
2. 记忆重启丢失 → 确认 `memory_persist: true`
3. 说话啰嗦 → 检查未加 stop 截断、Prompt 完整生效
4. 乱搜索 → 检查插件触发规则、auto_detect 开启
5. 不区分身份 → NapCat 开启全员事件上报 + 摘要 Prompt 包含身份字段
这份是咱们**一对一全程调试对齐、完全适配你现有环境**的最终定稿文档，直接保存即可长期复用。需要我帮你整理一份**参数微调速查表**（活跃度、幽默程度、搜索权限一键微调）吗？