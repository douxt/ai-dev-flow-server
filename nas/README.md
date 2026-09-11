# nas/ — NAS 在版脚本镜像（单一事实源）

本目录保存**运行在 NAS 上的脚本的仓库镜像**。方向上：**仓库 → NAS**（`scp` 部署）。NAS 上出现仓库没有的在版文件，必须先回灌入库再谈同步。

## 基线（2026-09-11 回灌，md5 与 NAS 逐字节一致）

| 仓库文件 | NAS 路径 | md5 | 大小 | NAS mtime |
|---|---|---|---|---|
| `health-check.sh` | `/volume1/docker/langbot/health-check.sh` | `3ae8bd85e1aabc198a892034250e92d6` | 3410 B | 2026-08-08 16:51:45 |
| `clean-zombie-ssh.sh` | `/usr/local/bin/clean-zombie-ssh.sh` | `9a76f0a48876ab40294789d0aa1ac216` | 1552 B | 2026-07-11 15:02:03 |
| （快照，不部署）`../docs/references/nas-crontab-snapshot-20260911.txt` | `/etc/crontab` | `968d261911f372f6c191a4aba7c9cd2b` | 490 B | 2026-08-08 19:57:28 |

cron 调度（实测）：`*/5` 跑 `health-check.sh`，`*/30` 跑 `clean-zombie-ssh.sh`。

## ⚠️ 危险提示

`health-check.sh` 当前入库的是 **2026-08-08 的线上回灌版本**，其中已知缺陷（详见 [../issues/2026-09-11-nas-health-check-repair.md](../issues/2026-09-11-nas-health-check-repair.md)）：

1. 引用 `$PROJECT_DIR/tests/test_smoke.py`——该路径在 NAS 上**从未存在**（仓库内该文件 2026-07-28 已移入 `tests/scripts/`）
2. `set -e` 使失败计数与自动重启分支**永不可达**
3. 通道 A 使用 `docker logs … | grep` 管道形态（2026-07-13 僵尸事故同构）
4. 6 处裸 `docker restart`，无 `timeout`
5. 重启顺序与 `docs/bot/container-restart-best-practices.md` §一 相反

**本文件的 md5 必须与 NAS 保持一致**，以便漂移对账（`check-drift.sh`）。修复版本另起 commit，不复用本基线。

## 纪律

- 在 NAS 上改任何在版脚本，**当场回灌本目录**并更新上表的 md5
- `scp` 整目录覆盖前先做三向核对（仓库 / NAS 在版 / 容器内生效版）
- 部署后记录 `md5sum` 与对应 `git` commit，避免再次出现"仓库与线上脱节"
