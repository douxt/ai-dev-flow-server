---
name: image-base64-strip-vision-block
description: _strip_base64 误清顶层 Image base64 导致 vision 图片下载全失败
metadata: 
  node_type: memory
  created: 2026-07-25
  source: stop-hook
  origin_session: d45c2e4d-a6ae-493e-8747-87a3f477d892
  type: feedback
  originSessionId: d45c2e4d-a6ae-493e-8747-87a3f477d892
---

# _strip_base64 误清顶层 base64 → 图片识别全失败

## 根因

`_strip_base64()` 在 gate handler 中对 message_chain 所有 Image 组件执行 `c.base64 = ''`，
包括用户刚发的图片。NapCat 不提供 `url` 字段 → 后续 `img.get_bytes()` 三个来源全空 →
`ValueError: Can not get bytes from image`。

从 7/20 到 7/25，所有群聊图片识别全部失败，日志累计 10+ 次。

## 修复

`_strip_base64` 增加 `top_level` 参数 → 顶层 Image 保留 base64，
仅 Quote/Forward 嵌套中的 Image 被清除（这些才是 WS 消息膨胀的元凶）。

## 预防

1. strip_base64 的测试必须区分顶层/嵌套场景
2. 新增 vision 功能时注意流程顺序：gate handler 中 `_strip_base64` 先于 `_save_with_vision` 执行
3. NapCat Image 组件不保证 `url` 字段存在，base64 是唯一可靠的数据来源
