# ADR-010: LangBot 宿主修改一律走幂等原地 patch + entrypoint 自动重放

## 状态：已采纳

## 日期：2026-08-28

## 背景

silent-observer 插件所在 LangBot 栈需要修改宿主框架源码（上游缺陷/半成品），历史上存在两种形态：

1. **幂等原地 patch 脚本**（patch_mcp_timeout / patch_image_url）：注册在 NAS `/volume1/docker/langbot/entrypoint.sh`，容器每次启动自动施加，marker 判重——但**版本管理分裂**：mcp 脚本只存在于 NAS 未入库；image 脚本 NAS 在版长期语法坏（每次启动喷 traceback，无人发现，其保护实际从未生效）。
2. **整文件替换**（patches/process.py、monitoring_helper.py：大 message_chain 同步 str()/model_dump() 阻塞事件循环的修复）：手工 docker cp，**未进 entrypoint**——2026-08-28 md5 核实：容器重建后补丁已丢失，事件循环保护裸奔数周无告警。

同期 forward-speaker 修复（合并转发丢说话人归属，8/24 事故）需要第三处宿主改动，暴露更多陷阱：
- **基线容器选错**：`langbot` 与 `langbot-plugin` 两容器各有一份 aiocqhttp.py 且**内容分叉**（610 行生效版 vs 682 行死代码副本——Face 组件过不了 WS 序列化，反证不可能在收消息路径上）。第一次计划评审时从错误容器导出基线，行号锚点全部失配。
- 上游镜像自带"暂时不太合理"的半成品分支（forward → pass），补丁锚点文本恰是这种被注释掉的 workaround——升级漂移风险真实存在。

## 决策

1. **宿主源码修改唯一形态 = 幂等原地 patch 脚本**：marker 判重（已打 skip）→ 锚点精确串替换（锚缺失 exit 1，升级漂移变成响的）→ 首次施加自动备份 `.orig-<name>`。禁止整文件替换；patches/process.py、monitoring_helper.py 已转制为 patch_event_loop_blocks.py，原文件降级为 diff 参考。
2. **全部 patch 注册进 entrypoint**（NAS 与仓库镜像归一），容器重建/镜像升级自动重放；`docker logs langbot | grep PATCH` 即审计面。
3. **仓库 `docker/langbot/patches/` 是单一事实源**：NAS 部署方向=仓库→NAS；NAS 上出现仓库没有的在版文件必须先回灌入库（已回灌 patch_mcp_timeout.py、patch_image_url.py）。
4. **基线纪律**：所有宿主锚点只许以 **langbot 容器**（QQ adapter 实际运行处）导出文件为准；`baselines/` 目录保存锚点回归对照物，`test_patches.py` 在副本上验证幂等/编译/锚点/import 完整性，LangBot 升级后先重导基线跑自测再动生产。
5. **补丁间组合性**：同一目标文件的多个 patch（image_url 与 forward_speaker 均改 aiocqhttp.py）锚点区域须互斥，链式双序应用测试纳入自测。

## 后果

- 正面：消灭"重建即丢"类静默失配（本次抓获两起：事件循环补丁丢失、image_url 语法坏）；升级兼容检测自动化（锚缺失即报警）；回滚路径标准化（.orig + entrypoint 注释）。
- 负面：patch 脚本随上游漂移需人工迁移 hunk（test_patches 把发现成本降到一次命令）；entrypoint 启动耗时增加 ~1s。
- 遗留：patch_image_url 处于"已重写但停用"状态——启用会把 vision 取图切到 url 优先路径（历史上从未生效过的行为），需单独验证窗口。
