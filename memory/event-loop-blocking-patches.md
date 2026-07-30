---
created: pre-2026-07
name: event-loop-blocking-patches
description: LangBot 补丁体系——事件循环阻塞防护经验，反思层设计约束
metadata: 
  node_type: memory
  type: lesson
  created: 2026-07-14
  tags: 
    - langbot
    - patches
    - blocking
    - reflection-layer
  originSessionId: 328233bd-f000-40b8-ac3c-375e70ce9d4c
---

# 事件循环阻塞与补丁体系

## 背景

2026-07-13 发现 LangBot 源码存在事件循环阻塞问题：
- `process.py`: `str(query.message_chain)` 大 message_chain 同步递归 >60s → WS ping timeout
- `monitoring_helper.py`: `model_dump()+json.dumps()` 大 message_chain 同步 >60s → WS ping timeout

团队新建补丁体系 `docker/langbot/patches/`，直接 patch LangBot 源码修复。

## 对反思层设计的启示

**约束**: 反思层（及未来评估层）的所有操作必须非阻塞。

**具体做法**:
1. **文件 IO**: 用 `run_in_executor`（已在 vision 识图中验证）
2. **LLM 调用**: 用 `asyncio.create_task` + 超时控制（已在 `_describe_one` 中验证）
3. **大文本处理**: 分片或流式，避免一次性处理超大字符串
4. **阻塞检测**: 监控 `asyncio.get_event_loop().time()` 差值，超阈值告警

**参考**: 补丁体系 README (`docker/langbot/patches/README.md`) 已记录应用步骤和维护流程。

## 教训

- 插件代码看似"小"，但大消息（如 100+ 图片描述、大转发）会触发同步操作阻塞
- 补丁是临时方案，应推动上游修复；但插件层也要做好防御
- 反思层写入 KB 时，若反思文本很大（如长对话总结），必须异步化

## 相关文件

- 补丁: `docker/langbot/patches/process.py`, `monitoring_helper.py`
- 启示来源: 开发日志第 22 章 napcat 大转发卡死根因分析
