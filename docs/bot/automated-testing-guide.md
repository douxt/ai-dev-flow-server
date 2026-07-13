# Silent Observer 插件自动化测试指南

> 2026-07-13 | 基于 LangBot v4.10.5 + napcat + OneBot v11

## 一、概述

### 为什么需要自动化测试

Chatbot 插件与普通软件不同：
- LLM 输出的**非确定性**：同一输入可能产生不同回复
- 上下游**多服务依赖**：QQ 协议(napcat) → LangBot 主进程 → 插件运行时 → LLM API
- **静默回归**风险：LangBot/插件升级后功能可能悄然失效
- **手动测试成本高**：每次改代码要在 QQ 群发消息验证，低效且污染聊天记录

本指南覆盖从零到全自动的测试体系建设方案。

### 测试金字塔（适配 Bot 插件）

```
        ┌──────┐
        │ E2E  │  ← HTTP Bot + relay → 真实 QQ 群
       ┌┴──────┴┐
       │ 集成测试 │  ← napcat HTTP API 直接发消息
      ┌┴────────┴┐
      │ 单元测试  │  ← 纯 Python，不依赖外部服务
      └──────────┘
```

| 层级 | 执行速度 | 依赖 | 覆盖范围 |
|------|---------|------|---------|
| 单元测试 | 秒级 | 无 | 映射表、数据转换、纯函数逻辑 |
| 集成测试 | 秒~十秒 | napcat API | 消息发送管道、API 连通性 |
| E2E | 十秒级 | napcat + relay + LLM | 完整链路：消息→gate→inject→LLM→回复→QQ群 |

---

## 二、单元测试

### 原则

- **纯 Python**：不依赖 napcat、LangBot runtime、QQ 协议
- **确定性**：固定输入 → 固定输出，不调 LLM API
- **轻量快速**：秒级跑完，适合 pre-commit hook

### 已有测试

文件：[`docker/langbot/plugins/silent-observer/tests/test_face_unit.py`](../../docker/langbot/plugins/silent-observer/tests/test_face_unit.py)

覆盖范围：
1. `_QQ_FACE_NAME` 映射表正确性（6 个边界 case）
2. Face 组件 → `[QQ表情:xxx]` 文本转换
3. 混合消息链提取（At + Plain + Face）
4. chat_index 历史 Unknown 统计

### 运行方式

```bash
# 本地 → NAS，在插件容器内执行
scp docker/langbot/plugins/silent-observer/tests/test_face_unit.py root@nas:/tmp/
ssh root@nas "timeout 10 \$DOCKER cp /tmp/test_face_unit.py langbot-plugin:/tmp/ && \
  timeout 10 \$DOCKER exec langbot-plugin /app/.venv/bin/python3 /tmp/test_face_unit.py"
```

### 扩展指南

新增单元测试时遵循以下模板：

```python
#!/usr/bin/env python3
"""新功能的单元测试"""
import sys
sys.path.insert(0, '/app/data/plugins/dou__langbot-silent-observer')
from components.event_listener.default import _QQ_FACE_NAME  # 按需导入

def test_xxx():
    """测试描述"""
    # 1. 构造输入
    # 2. 调用被测函数
    # 3. 断言结果
    assert result == expected, f"期望 {expected}，实际 {result}"

if __name__ == '__main__':
    test_xxx()
    print("✅ 全部通过")
```

### 适合单测的场景

- 映射表/配置校验
- 文本格式化、截断、拼接逻辑
- 数据清洗/规范化（如 `_normalize_face_components`）
- 时间窗口计算、去重逻辑
- 消息过滤规则

### 不适合单测的场景

- 依赖 LLM API 的识图/推理
- 依赖 napcat 协议的消息收发
- 依赖 LangBot pipeline 的完整对话流

---

## 三、集成测试（napcat HTTP API）

### 原理

napcat 内置 HTTP API（默认端口 3000），可以直接 `curl` 发送消息到 QQ 群。**限制：只能以 bot 自身身份发消息，无法模拟其他用户。**

### 适用场景

- 验证 napcat ↔ QQ 协议连通性
- 验证 bot 能否正常发送消息（不依赖 LangBot pipeline）
- 快速冒烟测试（bot 是否在线）

### 配置确认

```bash
ssh root@nas "timeout 5 \$DOCKER exec napcat sh -c 'cat /app/napcat/config/onebot11_3228649756.json' | python3 -m json.tool | grep -A8 httpServers"
```

需确认 `httpServers` 中包含 port 3000 的配置。

### 示例

```bash
# 发送纯文本
curl -s -X POST "http://napcat:3000/send_group_msg?access_token=udimc123" \
  -H "Content-Type: application/json" \
  -d '{"group_id":1104330614,"message":[{"type":"text","data":{"text":"测试消息"}}]}'

# 发送表情
curl -s -X POST "http://napcat:3000/send_group_msg?access_token=udimc123" \
  -H "Content-Type: application/json" \
  -d '{"group_id":1104330614,"message":[{"type":"face","data":{"id":"178"}}]}'

# 发送 @bot + 文本 + 表情
curl -s -X POST "http://napcat:3000/send_group_msg?access_token=udimc123" \
  -H "Content-Type: application/json" \
  -d '{"group_id":1104330614,"message":[{"type":"at","data":{"qq":"3228649756"}},{"type":"text","data":{"text":" 测试"}},{"type":"face","data":{"id":"178"}}]}'
```

### 验证方式

发送后观察：
1. 测试群是否出现消息（QQ 客户端确认）
2. langbot pipe 日志：`ssh root@nas "timeout 5 \$DOCKER logs langbot --tail 20"`
3. gate log：`ssh root@nas "timeout 5 \$DOCKER exec langbot-plugin sh -c 'tail -10 /tmp/silent_gate.log'"`

### 局限

napcat API 发送的消息**以 bot 身份**发出，LangBot 的 gate handler 会将其识别为 bot 自己的消息而**跳过处理**（self-message 过滤）。因此无法通过此法触发完整的 gate→inject→LLM 链路。

---

## 四、端到端测试（HTTP Bot + relay）

### 架构

```
测试脚本 ──POST──→ langbot HTTP Bot 适配器 (/bots/<uuid>)
                        │
                        ▼
                  pipeline: gate → inject → LLM
                        │
                        ▼
                  HTTP Bot callback → relay (:8888)
                        │
                        ▼
                  napcat send_group_msg API (:3000)
                        │
                        ▼
                    真实 QQ 群
```

这是**唯一能模拟任意用户、触发完整链路、且在真实 QQ 群看到回复**的方案。

### 组件说明

| 组件 | 位置 | 作用 |
|------|------|------|
| HTTP Bot 适配器 | langbot 容器 | 接收 POST 消息，签名验证，触发 pipeline |
| relay | napcat 容器 `:8888` | 接收 callback，转发到 napcat API |
| 测试脚本 | 任意可访问 langbot:5300 的位置 | 构造签名请求，模拟任意用户 |

### HTTP Bot 配置

langbot DB 中 `bots` 表记录：

| 字段 | 值 |
|------|-----|
| uuid | `dcbe70d9-af11-4624-908a-9928e4a08bdb` |
| name | HTTP测试 |
| adapter | `http_bot` |
| adapter_config | `{"inbound_secret":"udimc123", "outbound_secret":"udimc123", "callback_url":"http://napcat:8888", ...}` |

### relay v2 配置

文件：`/tmp/relay_v2.py`（napcat 容器内），监听 `0.0.0.0:8888`。

特性：基于 LangBot 回调协议的 `(session_id, sequence)` 幂等去重，只转发 `is_final=true` 的最终回复，中间流式 chunk 丢弃。

启动：
```bash
ssh root@nas "timeout 5 \$DOCKER exec -d napcat python3 /tmp/relay_v2.py"
```

验证：
```bash
ssh root@nas "timeout 5 \$DOCKER exec napcat sh -c 'pgrep -f relay_v2'"
```

### 发送测试消息（Python 脚本）

**推荐使用 `/sync` 端点**（同步模式），等待 LLM 完整回复后一次性返回，不产生流式 chunk：

```python
#!/usr/bin/env python3
"""E2E 测试：/sync 模式模拟任意用户，同步获取完整回复"""
import json, hmac, hashlib, time, urllib.request

LANG_BOT = "http://langbot:5300"
BOT_UUID = "dcbe70d9-af11-4624-908a-9928e4a08bdb"
SECRET = b"udimc123"

def send_sync(session_id: str, sender_id: str, sender_name: str,
              message: list, session_type: str = "group"):
    """发送到 /sync 端点，阻塞等待完整回复"""
    body = json.dumps({
        "session_id": session_id,
        "session_type": session_type,
        "sender": {"id": sender_id, "name": sender_name, "group_name": "测试专用"},
        "message": message,
    }).encode()

    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(SECRET, ts.encode() + b"." + body, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        f"{LANG_BOT}/bots/{BOT_UUID}/sync",  # /sync 端点
        data=body,
        headers={"Content-Type": "application/json", "X-LB-Timestamp": ts, "X-LB-Signature": sig},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read())

# --- 测试用例 ---

if __name__ == "__main__":
    # 用例1: 模拟小通豆发 QQ 表情
    r = send_message(
        session_id="1104330614",
        sender_id="370087943",
        sender_name="小通豆",
        message=[
            {"type": "At", "target": "3228649756"},
            {"type": "Plain", "text": " 这个表情什么含义？"},
            {"type": "Face", "face_type": "face", "face_id": 178, "face_name": ""},
        ],
    )
    print("用例1 (Face识别):", r)

    # 用例2: 模拟陌生人首次 @bot
    r = send_message(
        session_id="1104330614",
        sender_id="999999",
        sender_name="路人甲",
        message=[
            {"type": "At", "target": "3228649756"},
            {"type": "Plain", "text": "你好，你是谁？"},
        ],
    )
    print("用例2 (新用户):", r)

    # 用例3: 模拟私聊
    r = send_message(
        session_id="370087943",
        sender_id="370087943",
        sender_name="小通豆",
        message=[{"type": "Plain", "text": "私聊测试"}],
        session_type="person",
    )
    print("用例3 (私聊):", r)
```

### 验证步骤

```bash
# 1. 确认 relay v2 运行中
ssh root@nas "timeout 5 \$DOCKER exec napcat sh -c 'pgrep -f relay_v2'"

# 2. 运行 E2E 脚本（在 napcat 容器内，使用 /sync 端点）
scp tests/test_e2e_sync.py root@nas:/tmp/
ssh root@nas "timeout 5 \$DOCKER cp /tmp/test_e2e_sync.py napcat:/tmp/ && timeout 90 \$DOCKER exec napcat python3 /tmp/test_e2e_sync.py"

# 4. 检查 chat_index 存储
ssh root@nas "timeout 5 \$DOCKER exec langbot-plugin /app/.venv/bin/python3 -c \"
import sqlite3; db=sqlite3.connect('/app/data/plugins/dou__langbot-silent-observer/chat_index.db')
db.row_factory=sqlite3.Row
rows=db.execute('select formatted_text from chat_index where session_id=\\\"group_1104330614\\\" order by timestamp_unix desc limit 3').fetchall()
for r in rows: print(r['formatted_text'][:150])
\""
```

---

## 五、测试流水线设计

### 推荐的 CI 流程

```
代码提交 → 单元测试(秒) → 部署到 NAS → 冒烟测试(napcat ping) → E2E 核心用例(30s) → 报告
```

### 阶段详解

| 阶段 | 触发条件 | 耗时 | 通过标准 |
|------|---------|------|---------|
| **pre-commit** | git commit | <5s | 单元测试全部通过 |
| **smoke** | 部署后 | <5s | napcat online + langbot healthy + relay running |
| **e2e-core** | 按需/定时 | ~30s | Face 识别、gate allowed、reply 到达 QQ 群 |
| **full-suite** | 发版前 | ~2min | 全部用例 + LLM 回复质量人工抽检 |

### 核心用例清单

| # | 场景 | session_type | 消息类型 | 验证点 |
|---|------|-------------|---------|--------|
| 1 | @bot + 纯文本 | group | At+Plain | gate allowed, reply 无异常 |
| 2 | @bot + QQ 表情 | group | At+Plain+Face | chain_type 无 Unknown, reply 含表情名 |
| 3 | @bot + 图片 | group | At+Image | vision 调用成功, OCR/描述正确 |
| 4 | 陌生人首次 @bot | group | At+Plain | 正常回复, 不报错 |
| 5 | 高频率 @bot | group | At+Plain (x5) | 去重/限频生效, 不重复回复 |
| 6 | 私聊 | person | Plain | 私聊通道正常 |

---

## 六、测试工具脚本速查

### 诊断命令

```bash
DOCKER=/volume1/@appstore/ContainerManager/usr/bin/docker

# 容器健康
ssh root@nas "timeout 5 \$DOCKER ps --format '{{.Names}} {{.Status}}'"

# 单元测试
scp tests/test_face_unit.py root@nas:/tmp/ && \
  ssh root@nas "timeout 10 \$DOCKER cp /tmp/test_face_unit.py langbot-plugin:/tmp/ && \
  timeout 10 \$DOCKER exec langbot-plugin /app/.venv/bin/python3 /tmp/test_face_unit.py"

# relay 状态
ssh root@nas "timeout 5 \$DOCKER exec napcat sh -c 'pgrep -f relay_v2 && echo OK || echo DOWN'"

# gate log 最新
ssh root@nas "timeout 5 \$DOCKER exec langbot-plugin sh -c 'tail -15 /tmp/silent_gate.log'"

# 最近 Unknown 计数
ssh root@nas "timeout 5 \$DOCKER exec langbot-plugin /app/.venv/bin/python3 -c \"
import sqlite3; db=sqlite3.connect('/app/data/plugins/dou__langbot-silent-observer/chat_index.db')
cnt=db.execute(\\\"select count(*) from chat_index where formatted_text like '%Unknown%'\\\").fetchone()[0]
print(f'Unknown残留: {cnt}条')
\""

# LLM token 消耗（最近 1 小时）
ssh root@nas "timeout 5 \$DOCKER exec langbot /app/.venv/bin/python3 -c \"
import sqlite3; db=sqlite3.connect('/app/data/langbot.db')
row=db.execute(\\\"select count(*), sum(json_extract(usage,'$.total_tokens')) from monitoring_llm_calls where created_at > datetime('now','-1 hour')\\\").fetchone()
print(f'LLM调用: {row[0]}次, tokens: {row[1]}')
\""
```

### 快捷测试别名

在本地 `~/.bashrc` 或 `.zshrc` 中添加：

```bash
alias bot-test-unit='scp $HOME/dev/ai-dev-flow-server/docker/langbot/plugins/silent-observer/tests/test_face_unit.py root@nas:/tmp/ && ssh root@nas "timeout 10 /volume1/@appstore/ContainerManager/usr/bin/docker cp /tmp/test_face_unit.py langbot-plugin:/tmp/ && timeout 10 /volume1/@appstore/ContainerManager/usr/bin/docker exec langbot-plugin /app/.venv/bin/python3 /tmp/test_face_unit.py"'

alias bot-gate='ssh root@nas "timeout 5 /volume1/@appstore/ContainerManager/usr/bin/docker exec langbot-plugin sh -c \"tail -15 /tmp/silent_gate.log\""'

alias bot-relay='ssh root@nas "timeout 5 /volume1/@appstore/ContainerManager/usr/bin/docker exec napcat sh -c \"pgrep -f relay_v2 && echo OK || echo DOWN\""'
```

---

## 七、常见问题

### 1. relay 挂了 bot 回复不出现？

```bash
# 重启 relay
ssh root@nas "timeout 5 \$DOCKER exec -d napcat python3 /tmp/relay_v2"
```

### 2. HTTP Bot 返回 401 (bad signature)？

- 确认 `SECRET` 与 langbot DB 中 `inbound_secret` 一致
- 确认签名算法：`sha256=` + HMAC-SHA256(secret, timestamp + "." + body)
- 确认 timestamp 在允许窗口内（默认 ±300s）

### 3. 单元测试 import 失败？

`langbot_plugin` 包只在插件容器内可用，单元测试必须在 `langbot-plugin` 容器中运行。本地开发机无法 import。

### 4. 测试污染 chat_index？

测试产生的数据会存入 chat_index 和 KB。建议：
- 定期清理测试数据
- 在测试脚本末尾添加清理逻辑
- 或使用独立的测试群/测试 session

### 5. LLM 回复不稳定怎么验证？

不依赖精确文本匹配，改为**结构化检查**：
- gate log 关键词（`allowed`/`prevented`）
- chain_types 无 `Unknown`
- relay 成功转发（napcat log 含 `[模拟]`）
- chat_index 正确存储（无空值，格式正确）

如需评估 LLM 回复质量，使用 Promptfoo 或 DeepEval 等专用框架，不在本指南范围。

---

## 八、进阶话题

### 8.1 独立测试群

建议创建第二个 QQ 群专门用于自动化测试，避免污染正常群聊。配置方法：
1. 创建新群，拉 bot + 测试账号入群
2. 在测试脚本中使用新群号
3. relay 按 session_id 区分测试群和正式群

### 8.2 CI 集成（GitHub Actions）

```yaml
# .github/workflows/bot-test.yml
name: Bot E2E Test
on: [push]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Unit Test
        run: |
          scp tests/test_face_unit.py ${{ secrets.NAS_HOST }}:/tmp/
          ssh ${{ secrets.NAS_HOST }} 'docker cp /tmp/test_face_unit.py langbot-plugin:/tmp/ && docker exec langbot-plugin python3 /tmp/test_face_unit.py'
      - name: Smoke Test
        run: |
          ssh ${{ secrets.NAS_HOST }} 'docker exec napcat pgrep -f relay_v2 || exit 1'
          ssh ${{ secrets.NAS_HOST }} 'docker exec langbot-plugin cat /tmp/silent_init.log | grep -q "vision_enabled=True"'
      - name: E2E - Face Test
        run: |
          python3 tests/test_e2e_face.py  # 通过 HTTP Bot 发送测试消息
          sleep 15
          ssh ${{ secrets.NAS_HOST }} 'docker exec langbot-plugin sh -c "tail -10 /tmp/silent_gate.log" | grep -q "QQ表情"'
```

### 8.3 压力测试

```bash
# 连续发送 20 条消息，观察 bot 稳定性和限频行为
for i in $(seq 1 20); do
  python3 -c "send_message(...)" &
  sleep 2
done
```

观察指标：
- 成功率（202 accepted 比例）
- relay 队列积压
- LLM 并发错误率
- 容器资源（CPU/内存）

### 8.4 回归测试检查清单

每次修改 `default.py` 后手动执行：

- [ ] `test_face_unit.py` 全部通过
- [ ] `gate log` 无 ERROR
- [ ] `chain_types` 无 Unknown
- [ ] relay 正常转发
- [ ] vision 识图正常（发一张实图测试）
- [ ] 新功能相关的 E2E 用例通过

---

## 九、参考资源

| 资源 | 链接/路径 |
|------|----------|
| LangBot 官方测试指南 | `AGENTS.md` (仓库根目录) |
| ElizaOS 测试工具 | [`@elizaos/test-utils`](https://www.npmjs.com/package/@elizaos/test-utils) |
| LLM 评估框架 | [Promptfoo](https://promptfoo.dev/), [DeepEval](https://docs.confident-ai.com/) |
| napcat 文档 | [NapNeko/NapCatQQ](https://github.com/NapNeko/NapCatQQ) |
| OneBot v11 协议 | [botuniverse/onebot-11](https://github.com/botuniverse/onebot-11) |
| 本项目单元测试 | `docker/langbot/plugins/silent-observer/tests/` |
| 本项目集成测试 | `docker/langbot/plugins/silent-observer/tests/test_face_recognition.sh` |
