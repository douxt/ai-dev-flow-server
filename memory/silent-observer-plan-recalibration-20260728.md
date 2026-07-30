---
name: silent-observer-plan-recalibration-20260728
description: 对照 1352 行 default.py + 14 测试文件重新校准地基重构计划
metadata: 
  node_type: memory
  type: project
  originSessionId: 328233bd-f000-40b8-ac3c-375e70ce9d4c
---

对照当前代码（`docker/langbot/plugins/silent-observer/`）重新校准 7 步地基计划。

## 关键发现

1. **测试基础设施 80% 完成**：14 测试文件 + conftest.py 完整 SDK mock 树已就位（比原始计划假设大超前）
2. **main.py 已是薄封装**：8 行，`BasePlugin` 子类
3. **manifest.yaml 缺 7 配置项（P0 紧急）**：`vision_enabled`/`vision_model_uuid` 等不在 manifest 中，用户在 UI 看不到
4. **default.py 1352 行**：比计划的 1085 行更多（新增 URL-first vision、熔断器、worker pool、Face 全链路）
5. **状态仍零持久化**：`_vision_daily_count` 等重启即丢失（P0#1 未修复）
6. **硬编码维度仍存在**：keyword 通道 `[0.0]*384`（P0#2 未修复）
7. **无分层抽取**：store/service/util 仍未拆分

## 新增步骤 0.5

manifest 补齐 7 个缺失配置项为最紧急任务（在重构前先做）。

**Why:** manifest 缺配置项导致 vision 功能在 UI 中不可见/不可操作，属于用户可感知的功能缺失。
**How to apply:** 在地基重构计划中新增步骤 0.5，优先级最高，改动量最小（仅 yaml）。
