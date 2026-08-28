---
name: ppt-workflow-ready-playbook
description: 2026-08-28 Claude Code PPT 生成/改造能力已全链路配好并有实战手册——新会话接到 .pptx 需求直接读 playbook 上手，禁止重新调研
created: 2026-08-28
source: stop-hook
origin_session: 8b643298-95db-4533-b9ce-f587acca8fb8
metadata: 
  node_type: memory
  type: project
  originSessionId: 8b643298-95db-4533-b9ce-f587acca8fb8
---

**根因**：一次 PPT 改造 = 两波调研 + 七轮迭代 + 13 处工程试错，不复用则每次从零。
**解决**：下述就绪环境 + 手册 + 脚手架资产，需求开场直接照手册执行。
**预防**：新会话召回本记忆 → 先读手册再动手；同类新经验继续追加进手册（改规则不改产出物）。

**任何 .pptx 生成/改造需求（说课/汇报/deck 提档/改造现有 PPT），先读两份文档再动手，不要重新调研：**

1. 实战手册：`~/dev/ai-dev-flow-server/docs/research/claude-code-ppt-playbook.md`（环境状态/三问定方向/档次阶梯/改造 SOP/可复用资产表/工程雷区/QA 出口）
2. 背景调研：同目录 `claude-code-ppt-research-20260828.md`（技术选型与生态评估）

已就绪不可重复建设的部分：官方 pptx skill 装在 `~/.claude/skills/pptx/`；soffice+poppler+Noto CJK+markitdown/python-pptx/lxml/pillow+pip(user) 全部装好；实战脚手架在 `~/ppt-jobs/shuoke/`（gen_v7.py 咨询报告风模板、check_geom.py、prep_images.py、extract_notes.py、icons.mjs、DESIGN.md 范例）。

本会话最核心的三条认知：
- **档次 70% 靠结构纪律**（硬网格+action title 结论句+脚注页码+字号三级），30% 靠视觉（duotone CC 真图+图标+封面纹理）；"微调无感"= 该升级动手层级而非表层修补
- **改造场景先对口味再铺全册**：4 页风格样张试看优于语言对齐；赛课/评审场景要咨询报告密度风，编辑留白风会被判"内容单薄"
- python-pptx 三雷：中文字体必写 `a:ea` 槽（latin 后插入）、helper 返回 run 非 rPr、`grep` 被 rtk 劫持统计用 python

**Why:** 一次七轮迭代（v1→v7）+ 两波调研的完整成本，用户明确要求沉淀后新会话直接复用。
**How to apply:** 新需求开场即 Read 本手册 §0 环境自检 → §1 三问定方向 → 照 §3/§4 执行；相关 [[claude-code-dual-config-hooks-sync]]。
