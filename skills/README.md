# skills/ — 本仓库自带的 skill

这些 skill 随仓库分发（`skills-cache/` 是 install.sh 安装到目标项目的离线缓存，两者用途不同）。

| skill | 用途 | 触发场景 |
|---|---|---|
| [nas-ops](nas-ops/SKILL.md) | NAS 运维流程：巡检判读、7 步部署、重启验证清单、QQ 掉线恢复、SSH/Docker 纪律、故障速查 | 查看/修改 NAS 上的 langbot / langbot-plugin / napcat，解读 `/tmp/health_check.log`，处理 `qq-offline` / 脚本漂移 / 收不到告警 |
| [characterize](characterize/SKILL.md) | 为遗留代码补特征测试（characterization tests） | 需要改动没有测试覆盖的旧代码前 |

配套索引：

- 决策背景：[../docs/decisions/011-nas-observability-architecture.md](../docs/decisions/011-nas-observability-architecture.md)
- 踩坑清单：[../memory/nas-observability-lessons-20260911.md](../memory/nas-observability-lessons-20260911.md)
- 在版脚本与基线：[../nas/README.md](../nas/README.md)、[../nas/INVENTORY.md](../nas/INVENTORY.md)
