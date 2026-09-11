# nas/ — NAS 在版脚本镜像（单一事实源）

本目录保存**运行在 NAS 上的脚本的仓库镜像**。方向上：**仓库 → NAS**（`scp` 部署）。NAS 上出现仓库没有的在版文件，必须先回灌入库再谈同步。

## 基线（2026-09-11 部署后，md5 与 NAS 逐字节一致）

| 仓库文件 | NAS 路径 | md5 | 说明 |
|---|---|---|---|
| `health-check.sh` | `/volume1/docker/langbot/health-check.sh` | `8df813471e86be2f4f221ecae9ca20e0` | 五项心跳探针版（7128 B），2026-09-11 10:55 部署 |
| `clean-zombie-ssh.sh` | `/usr/local/bin/clean-zombie-ssh.sh` | `9a76f0a48876ab40294789d0aa1ac216` | cron `*/30`，杀残留 `docker exec` 会话 |
| `check-drift.sh` | （不部署，开发机运行） | — | 比对 NAS 在版文件与仓库 `main` |
| （快照）`../docs/references/nas-crontab-snapshot-20260911.txt` | `/etc/crontab` | `968d261911f372f6c191a4aba7c9cd2b` | 快照于 2026-09-11 |

cron 调度（实测）：`*/5` 跑 `health-check.sh`，`*/30` 跑 `clean-zombie-ssh.sh`。

历史版本（已废弃）：`health-check.sh` 的 2026-08-08 在版版本（3410 B，md5 `3ae8bd85e1aabc198a892034250e92d6`）保存在：
- NAS 备份文件 `/volume1/docker/langbot/health-check.sh.bak.20260911`
- git 历史 commit `56e6d70`（回灌基线）与 `07bdc1a`（修复）

该旧版含严重缺陷，**切勿照抄**：引用 NAS 上从未存在的 `$PROJECT_DIR/tests/test_smoke.py`；`set -e` 使失败计数与自动重启分支永不可达（自愈静默失效 30+ 天）；`docker logs` 跨管道扫描；6 处裸 `docker restart` 无 `timeout`；重启顺序与权威文档相反。详见 [../issues/2026-09-11-nas-health-check-repair.md](../issues/2026-09-11-nas-health-check-repair.md)。

## 漂移对账

```bash
bash nas/check-drift.sh            # 默认 root@nas；只读，无副作用
```

逐项比对 NAS 在版文件的 md5 与**仓库 main 分支**内容，输出 `OK` / `DRIFT` / `DOWN`，有漂移则退出码 1。
（2026-09-11 首次运行：3 项全部一致。）

## 纪律

- 在 NAS 上改任何在版脚本，**当场回灌本目录**并更新上表的 md5
- `scp` 整目录覆盖前先做三向核对（仓库 / NAS 在版 / 容器内生效版）；`docker/langbot/patches/` 同理（见 ADR 010）
- 部署后运行 `bash nas/check-drift.sh` 确认，并记录对应 git commit
- 改完巡检类脚本，先跑 `bash tests/integration/health_check_selftest.sh`（零依赖，38 项）

## 2026-09-11 阶段二（T1）更新

| 仓库文件 | 部署位置 | md5 | 说明 |
|---|---|---|---|
| `health-check.sh`（v2） | NAS `/volume1/docker/langbot/health-check.sh` | `7a9b5bc9ea35811510025a3d72f66f16` | 五项探针 + 登录态双探测（`qq` 状态探针 / `qq-events` 日志扫描）+ `state/alert`（1h 去重）+ 连续 SKIP 告警 |
| `cloud/nas-fetch-alerts.sh` | 阿里云 `/usr/local/bin/nas-fetch-alerts.sh` | 部署于 2026-09-11 | 拉取 NAS `state/alert` → Telegram → 成功后归档 |
| `cloud/nas-alert-send.py` | 阿里云 `/usr/local/bin/nas-alert-send.py` | 同上 | 复用 `/opt/maf-hub/config/telegram.json`（token + Tailscale Clash 代理） |

上表 v1（md5 `8df813471e86be2f4f221ecae9ca20e0`）已备份为 NAS `health-check.sh.bak.20260911-v1`。

**告警链路**：NAS（零外网）写 `state/alert` ← 阿里云 cron `*/5` ssh 拉取（Tailscale）→ Telegram。云服务器公钥（`maf-hub-server`）已加入 NAS `authorized_keys`。

**注意**：`nas/check-drift.sh` 目前只覆盖 NAS 三个文件；云侧两个脚本尚未纳入对账（T5 处理）。

## 2026-09-11 阶段二（T5）更新

| 仓库文件 | 部署位置 | 说明 |
|---|---|---|
| `watchdog.sh` | 开发机（cron 每小时） | 漂移对账 + 巡检心跳新鲜度 + 待发告警积压；异常经云服务器推 Telegram；静默 + 6h 去重 |

安装（沙箱不允许写 crontab，需人工执行一次）：

```bash
( crontab -l 2>/dev/null; echo '0 * * * * /home/dou/dev/ai-dev-flow-server/nas/watchdog.sh' ) | crontab -
```

自检：`WD_FORCE_PROBLEM=1 bash nas/watchdog.sh`（会真实推一条 Telegram）。
