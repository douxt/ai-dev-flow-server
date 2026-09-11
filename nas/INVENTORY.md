# NAS 在版脚本清点（T7，2026-09-11）

目的：避免再次出现"仓库与线上脱节"（2026-09-11 发现 health-check.sh 线上 3410B vs 仓库 1486B，照仓库修等于修的不是线上那份）。

清点范围：`/etc/crontab` 引用的全部可执行项（**100% 覆盖**）、`/usr/local/bin`、`/usr/local/sbin`、`/volume1/docker/*/` 顶层脚本。

## 自建脚本（已入库，纳入 `check-drift.sh` 对账）

| NAS 路径 | md5 | 仓库位置 | 说明 |
|---|---|---|---|
| `/volume1/docker/langbot/health-check.sh` | `7a9b5bc9ea35811510025a3d72f66f16` | `nas/health-check.sh` | 五项探针 + 登录态双探测 + 告警 |
| `/volume1/docker/langbot/deep-smoke.sh` | `6f4ea4763af0936ebe4597d415b14ce4` | `nas/deep-smoke.sh` | 每 6h 金丝雀包装 |
| `/volume1/docker/langbot/tests/deep-canary.py` | `c573119ff20b4d4cd0d48419de78d2c7` | `nas/deep-canary.py` | 金丝雀本体 |
| `/volume1/docker/langbot/entrypoint.sh` | `3730cebb4f9b70d1fbf14a1ff2de03a9` | `docker/langbot/entrypoint.sh` | patch 幂等注册（ADR 010） |
| `/volume1/docker/langbot/plugin-entrypoint.sh` | `26e2defd16e8e0e81940ec1aefea3661` | `docker/langbot/plugin-entrypoint.sh` | 等 LangBot 就绪再起插件运行时（**2026-09-11 本次回灌**） |
| `/usr/local/bin/clean-zombie-ssh.sh` | `9a76f0a48876ab40294789d0aa1ac216` | `nas/clean-zombie-ssh.sh` | 清 `docker exec` 僵尸会话 |
| `/etc/crontab` | `b1e7b5e5d84daabee39eed7a0f02ba8e` | `docs/references/nas-crontab-snapshot-20260911.txt` | 混合（DSM 条目 + 自建条目） |

## 系统文件（不入库，判定依据）

| 路径 | 判定 |
|---|---|
| `/usr/local/bin/{docker,dockerd,ctr,containerd*,docker-compose,docker-proxy,auplink}` | 指向 `/var/packages/ContainerManager/target/...` 的符号链接 → DSM 包 |
| `/usr/local/bin/{cifsdd,ldbadd,ldbdel,...}` | 指向 `/var/packages/SMBService/target/...` → DSM 包 |
| `/usr/local/bin/epck` | 指向 `/var/packages/ScsiTarget/target/bin` → DSM 包 |
| `/usr/local/bin/feasibilitycheck/`（2025-01） | DSM 自带目录 |
| `/usr/local/sbin/` | 空 |
| `/usr/sbin/powersched`、`/usr/syno/bin/synoschedtask` | DSM 系统二进制（crontab 引用） |

## 与本仓库无关的个人基础设施（记录在案，不纳入对账）

| 路径 | md5 | 判定 |
|---|---|---|
| `/volume1/docker/n8n/proxy-env.sh` | `80d9c95c8b43fbeab6519294406023aa` | 2025-06 自建的代理环境变量管理脚本，服务 n8n，与本项目无依赖关系 |
| `/volume1/docker/rclone/dual_backup.sh` | `f115a8371d7953b5945fc8a5eb633fed` | 2025-01 自建的 rclone 双备份脚本（本地 → 阿里云盘） |

> 若日后这两个脚本也要版本化，建议单独开仓库或移入 `nas/inventory/`；当前判断是"与本框架/机器人无耦合"，强行入库只会制造无关噪音。
