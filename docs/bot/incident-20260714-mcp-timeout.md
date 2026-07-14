# 2026-07-14 MCP Timeout 会话锁死事故报告

> 会话卡死 9 小时，根因：MCP 工具调用无超时机制

---

## 一、事件概述

2026-07-14 17:15 发现太空工程师群 bot 无响应。用户 @bot 发消息，bot 完全沉默，无任何回复。

排查发现：会话 131（测试群）从 08:04 开始卡死，`_last_trigger[session_name]` 永远未释放，导致后续所有消息被 `is_locked()` 拦截。

**持续时间**：9 小时 11 分钟（08:04 ~ 17:15）

**影响范围**：测试群、太空工程师群（共用同一个 langbot 实例）

**恢复方式**：手动重启 langbot-plugin 容器，强制清空内存中的 `_last_trigger`

---

## 二、时间线

| 时间 | 事件 | 状态 |
|------|------|------|
| 08:04:49 | 用户发送图片识别请求 | 正常 |
| 08:04:50 | gate handler 触发，doc_id=131 | 正常 |
| 08:04:51 | inject handler 开始执行 | 正常 |
| 08:04:53 | `_save_with_vision()` 调用 `_describe_images()` | **卡死** |
| 08:04:53 ~ 17:15 | `_describe_images()` 等待 MCP 工具返回 | **无超时，永久阻塞** |
| 08:05 ~ 17:14 | 用户多次 @bot，消息被 `is_locked()` 拦截 | **全部丢弃** |
| 17:15 | 用户报告 bot 无响应 | 开始排查 |
| 17:20 | 检查 `_last_trigger` 内存状态 | 发现 session 131 未释放 |
| 17:25 | 重启 langbot-plugin 容器 | 恢复 |

---

## 三、根本原因

### 直接原因：MCP 工具调用无超时机制

`silent-observer` 插件的 `_describe_images()` 方法调用 LangBot 的 MCP 工具（图像识别），但 **LangBot 的 MCP 工具调用本身没有超时机制**。

```python
# docker/langbot/plugins/silent-observer/components/event_listener/default.py:160-170

async def _save_with_vision(self, event, session_name, doc_id):
    """异步识图：调用 MCP 工具识别图片，缓存结果"""
    if not hasattr(self, '_image_cache'):
        self._image_cache = {}
    
    try:
        # 调用 LangBot 的 MCP 工具
        result = await self.api.call_mcp_tool(
            tool_name="describe_image",
            arguments={"image_url": image_url}
        )
        # 如果 MCP 工具永久阻塞，这里永远不会返回
        description = result.get("description", "")
        
        self._image_cache[doc_id] = {
            "status": "done",
            "desc": description,
            "time": time.time()
        }
    except Exception as e:
        self._image_cache[doc_id] = {
            "status": "failed",
            "desc": "[图片(识别失败)]",
            "time": time.time()
        }
```

### 间接原因：会话锁无 TTL 机制

`inject` handler 在开始时设置 `_last_trigger[session_name]`，但 **没有 TTL 机制**。如果 `_save_with_vision()` 永久阻塞，锁永远不会释放。

```python
# docker/langbot/plugins/silent-observer/components/event_listener/default.py:140-150

async def inject(self, ctx):
    """注入上下文到 pipeline"""
    session_name = ctx.event.session_name
    
    # 设置会话锁
    self._last_trigger[session_name] = {
        "doc_id": doc_id,
        "trigger_time": time.time(),
        "status": "processing"
    }
    
    try:
        # 构建时间线
        timeline = await self._build_timeline(ctx)
        
        # 注入到 pipeline
        ctx.event.prompt = timeline
        
    finally:
        # 释放会话锁
        # 如果上面的代码永久阻塞，这里永远不会执行
        if session_name in self._last_trigger:
            del self._last_trigger[session_name]
```

### 触发链路

```
用户发送图片 → gate handler 触发 → inject handler 开始
→ _save_with_vision() 调用 MCP 工具 → MCP 工具永久阻塞
→ inject handler 永久阻塞 → _last_trigger 未释放
→ 后续消息被 is_locked() 拦截 → 会话卡死
```

---

## 四、已暴露的问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | LangBot MCP 工具调用无超时机制 | **致命** | 🔴 未修复 |
| 2 | Silent Observer 会话锁无 TTL 机制 | **致命** | 🔴 未修复 |
| 3 | 无会话卡死监控告警 | 高 | 🟡 待改进 |
| 4 | 无自动恢复机制（如超时自动释放锁） | 高 | 🟡 待改进 |

---

## 五、临时修复措施

### Monkey Patch：给 MCP 工具调用加超时

在 LangBot 主进程的 `mcp.py` 中添加 `asyncio.timeout(30)`：

```python
# docker/langbot/patches/mcp_timeout.patch

# 在 invoke_mcp_tool 方法中
async with asyncio.timeout(30):  # 30秒硬超时
    result = await self.session.call_tool(tool_name, arguments)
```

**验证**：

```bash
# 测试 MCP 工具超时
ssh root@nas "timeout 15 docker exec langbot /app/.venv/bin/python3 -c \"
import asyncio
from langbot.pkg.mcp import call_tool

async def test():
    try:
        result = await call_tool('describe_image', {'image_url': 'http://invalid'})
    except asyncio.TimeoutError:
        print('✅ Timeout working')

asyncio.run(test())
\""
```

---

## 六、改进措施

### 立即执行

1. **Monkey Patch 已部署**：
   - 文件：`docker/langbot/patches/mcp_timeout.patch`
   - 效果：MCP 工具调用 30 秒超时，避免永久阻塞

2. **更新文档**：
   - `docs/bot/langbot-plugin-dev-reference.md`：添加 MCP 工具超时规范
   - `docs/bot/silent-observer-dev-journal.md`：添加第 16 章 MCP 超时防护

### 后续改进（需要上游修复）

3. **向 LangBot 上游提交 Issue**：
   - Issue #2339：`fix(mcp): add timeout to prevent MCP tool calls from hanging indefinitely (v4.10.5)`
   - 要求：在 `invoke_mcp_tool` 中添加 `asyncio.timeout(30)`

4. **Silent Observer 会话锁加 TTL**：
   ```python
   async def inject(self, ctx):
       session_name = ctx.event.session_name
       
       # 设置会话锁 + TTL（5分钟）
       self._last_trigger[session_name] = {
           "doc_id": doc_id,
           "trigger_time": time.time(),
           "status": "processing",
           "ttl": 300  # 5分钟
       }
       
       try:
           # ... 原有逻辑
       finally:
           # 释放会话锁
           if session_name in self._last_trigger:
               del self._last_trigger[session_name]
   
   def is_locked(self, session_name):
       """检查会话是否锁定（带 TTL）"""
       if session_name not in self._last_trigger:
           return False
       
       lock_info = self._last_trigger[session_name]
       trigger_time = lock_info.get("trigger_time", 0)
       ttl = lock_info.get("ttl", 300)
       
       # 超过 TTL 自动释放
       if time.time() - trigger_time > ttl:
           del self._last_trigger[session_name]
           return False
       
       return True
   ```

5. **添加会话卡死监控**：
   ```python
   async def _monitor_session_locks(self):
       """定期检查会话锁状态，超时告警"""
       while True:
           for session_name, lock_info in self._last_trigger.items():
               trigger_time = lock_info.get("trigger_time", 0)
               if time.time() - trigger_time > 300:  # 5分钟
                   print(f"⚠️ 会话 {session_name} 锁定超过 5 分钟")
                   # 可以发送告警通知
           await asyncio.sleep(60)  # 每分钟检查一次
   ```

---

## 七、解决结果

- [x] 手动重启 langbot-plugin 容器，恢复服务
- [x] Monkey patch 已部署：MCP 工具调用 30 秒超时
- [x] 已向 LangBot 上游提交 Issue #2339
- [ ] Silent Observer 会话锁 TTL 机制（待实现）
- [ ] 会话卡死监控告警（待实现）

---

## 八、经验教训

### 1. 外部调用必须加超时

任何外部调用（API、MCP 工具、网络请求）**必须**加超时机制：

```python
# ✅ 正确
async with asyncio.timeout(30):
    result = await external_call()

# ❌ 错误
result = await external_call()  # 可能永久阻塞
```

### 2. 会话锁必须有 TTL

内存中的锁机制**必须**有 TTL（Time To Live），防止永久锁定：

```python
# ✅ 正确
self._locks[session_id] = {
    "time": time.time(),
    "ttl": 300  # 5分钟
}

# ❌ 错误
self._locks[session_id] = time.time()  # 无 TTL
```

### 3. 关键操作需要监控告警

会话卡死、锁超时、MCP 工具失败等关键操作**必须**有监控告警，不能依赖用户报告。

---

## 九、参考资料

- [LangBot Issue #2339](https://github.com/langbot-app/LangBot/issues/2339) - MCP 工具超时问题
- [Asyncio Timeout 文档](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout)
- [Python 并发最佳实践](https://superuser.openinfra.org/articles/10-reasons-to-back-upstream-open-source-contributions/)

---

**报告人**：Claude  
**报告时间**：2026-07-14 17:45  
**最后更新**：2026-07-14 17:45
