# Silent Observer 插件 — 交接文档

> 2026-07-11 | 由会话 28cbfc5c 移交

---

## 一、新会话快速上手

**看这个就能干活：**

1. 当前分支：`main`（最新 `12e8981`）
2. 代码位置：`/home/dou/dev/ai-dev-flow-server/` → `default.py` + `manifest.yaml`
3. 部署到 NAS：Docker 路径是 `/volume1/@appstore/ContainerManager/usr/bin/docker`（不是 `/usr/local/bin/docker`）
4. SSH 前：WSL 里 `sudo tailscale status` 确认已 down（Windows+WSL 双开会卡死）
5. 重启顺序：langbot-plugin → langbot → napcat
6. **所有 docker 命令加 `timeout` 前缀**，防止僵尸会话

---

## 二、当前架构

```
群消息 → gate (GroupMessageReceived)
         ├─ 保存到 KB (ChromaDB Dou KB)
         ├─ 检测图片 → _collect_images 递归收集
         │             → 异步视觉识别 (qwen3.6-flash)
         │             → KB upsert 更新描述
         ├─ 提取引用文本 (_extract_quote)
         └─ @触发 / 随机插话(20%) → inject (PromptPreProcessing)
                                        ├─ 当前时间 (北京时间)
                                        ├─ 时间线 (40条)
                                        ├─ 【转发内容】+ 🖼️ 图N：格式 + 图片状态
                                        ├─ [@模式] / [空@模式] / [随机插话]
                                        └─ 视觉识别结果注入
```

---

## 三、当前配置 (DB plugin_settings)

| 配置项 | 值 |
|--------|-----|
| `bot_qq` | 3228649756 |
| `reply_probability` | 0.2 (20%) |
| `history_count` | 40 |
| `timeline_max_chars` | 2000 |
| `kb_id` | `da7a1cef-f5c3-4b50-9acd-fe0d3bf12cfc` |
| `embedding_model_uuid` | `62e075f9-733f-458c-8ce8-d983c411cad9` (seekdb-local) |
| `vision_enabled` | True |
| `vision_model_uuid` | `61a105e9-6180-45ee-a6f6-a7ec9d713265` (qwen3.6-flash) |
| `vision_all_messages` | True |
| `vision_daily_limit` | 100 |
| `vision_max_images` | 5 |

群聊 session_id：测试群 `group_1104330614`、太空工程师 `group_116381172`

---

## 四、部署流程

```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker

# 1. 上传
scp default.py root@nas:/tmp/silent_default.py

# 2. 清 pycache（必须！）
ssh root@nas "$DOCKER exec langbot-plugin sh -c 'find /app/data/plugins/dou__langbot-silent-observer -name __pycache__ -exec rm -rf {} +'"

# 3. 部署
ssh root@nas "$DOCKER cp /tmp/silent_default.py langbot-plugin:/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py"

# 4. 重启（注意顺序）
ssh root@nas "timeout 15 $DOCKER restart langbot-plugin langbot && sleep 5 && timeout 15 $DOCKER restart napcat"

# 5. 验证
ssh root@nas "$DOCKER exec langbot-plugin cat /tmp/silent_init.log"
# 预期：kb_enabled=True vision_enabled=True prob=0.2
```

**文件对应关系：**
| 本地/工作树 | 容器路径 |
|-------------|---------|
| `default.py` | `/app/data/plugins/dou__langbot-silent-observer/components/event_listener/default.py` |
| `manifest.yaml` | 同上目录 `manifest.yaml` |
| `search_chat_history.py` | 同上 `components/tool/search_chat_history.py` |

---

## 五、日志与调试

```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker

# 插件初始化
ssh root@nas "$DOCKER exec langbot-plugin cat /tmp/silent_init.log"

# gate/inject 全链路
ssh root@nas "$DOCKER exec langbot-plugin sh -c 'tail -20 /tmp/silent_gate.log'"

# QQ 连接状态
ssh root@nas "$DOCKER logs napcat 2>&1 | tail -10"
```

**关键日志行含义：**
```
[silent] gate: allowed (at) doc_id=chat:xxx  ← @触发
[silent] inject START                          ← inject 被调用
[silent] at_text="xxx" sender=小通豆          ← 提取的查询文本
[group_*] quote_text=xxx                       ← 引用提取结果
[] vision: done ok=N fail=N                    ← 视觉识别完成
[] vision: KB upserted, text len=N             ← KB 已更新
[group_*] vision: combined injected (N done, M pending)  ← 注入图片状态
```

---

## 六、系统提示词位置

Prompt 存于 `langbot.db` → `legacy_pipelines.config.ai.local-agent.prompt[0].content`。

查询：
```bash
ssh root@nas "$DOCKER exec langbot /app/.venv/bin/python3 -c \"
import sqlite3, json
db = sqlite3.connect('/app/data/langbot.db')
cur = db.execute('SELECT use_pipeline_uuid FROM bots WHERE enable=1 LIMIT 1')
uuid = cur.fetchone()[0]
cur = db.execute('SELECT config FROM legacy_pipelines WHERE uuid=?', (uuid,))
cfg = json.loads(cur.fetchone()[0])
print(cfg['ai']['local-agent']['prompt'][0]['content'])
\""
```

---

## 七、最近改动 (2026-07-11)

| 改动 | 说明 |
|------|------|
| 图片格式优化 | `🖼️ 图N：xxx / ⏳ 识别中...` + image_descriptions 递归传递 |
| 删除自动语义搜索 | inject 不再自动搜全量 KB，LLM 按需调用 search_chat_history |
| 空 @ 优化 | 区分引用空 @（优先回应引用）和纯空 @（从时间线挑话题），禁止回复状态确认 |
| _image_cache 修复 | 从只存第一张改为存所有图片描述（`|` 拼接） |
| System prompt 更新 | 异步识图机制说明 + 工具使用时机 + 转发引导 |
| 清理 | 14 条 2016 假数据 + 28 条 bot 循环记录 + 11 个旧分支/worktree |
| 运维 | Docker 路径修正、SSH 僵尸清理脚本（cron 每 30 分钟）、Tailscale WSL 诊断 |
| 配置 | vision_all_messages=True, vision_daily_limit=100, reply_probability=0.2 |

---

## 八、待办

| 优先级 | 任务 |
|--------|------|
| 中 | 分群 reply_probability（不同群不同概率） |
| 低 | get_forward_msg API（解析转发结构化内容，NapCat 目前只给截图） |
| 低 | 清理项目根目录旧脚本 |

---

## 九、文档索引

**[README.md](docs/bot/README.md)** 是总索引。关键文档：

| 文档 | 用途 |
|------|------|
| [开发日志](docs/bot/silent-observer-dev-journal.md) | 14 章全链路踩坑（Pipeline 契约、视觉接入、Forward 处理） |
| [容器重启最佳实践](docs/bot/container-restart-best-practices.md) | 重启顺序、SSH 僵尸防护、Tailscale WSL 冲突 |
| [NAS 运维](docs/bot/nas-access-best-practices.md) | SSH/Docker/DB/UUID 速查、Base64 绕过、Tailscale 诊断 |
| [bot.md](docs/bot/bot.md) | 终版 NapCat/LangBot 配置 |
