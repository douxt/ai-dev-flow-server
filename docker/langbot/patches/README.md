# LangBot 补丁

对 LangBot 框架源码的修改。**全部为幂等原地 patch 脚本**（marker 判重、锚缺失即报错），由容器 entrypoint 每次启动自动施加——容器重建/镜像升级不再丢失。

NAS 部署位置：`/volume1/docker/langbot/patches/` + `/volume1/docker/langbot/entrypoint.sh`（bind mount 进 langbot 容器 `/patches`、`/entrypoint.sh`）。本目录是仓库镜像，**以本目录为准 scp 到 NAS**。⚠️ 补丁只打 `langbot` 容器——`langbot-plugin` 容器里的同名源码是死代码副本，不要以它为基线。

## 补丁清单

| 补丁 | 目标文件 | 原因 | 状态 |
|------|---------|------|------|
| [patch_mcp_timeout.py](patch_mcp_timeout.py) | `pkg/provider/tools/loaders/mcp.py` | MCP call_tool 无超时 → session 死锁 | 生效 |
| [patch_image_url.py](patch_image_url.py) | `pkg/platform/sources/aiocqhttp.py` | Image 构造保留平台 CDN url | 当前镜像为 PR 版（自带 url=）→ 脚本自动 skip；NAS 版比仓库旧版多 PR 检测，已回灌（2026-08-28） |
| [patch_event_loop_blocks.py](patch_event_loop_blocks.py) | `pkg/pipeline/process/process.py` + `pkg/pipeline/monitoring_helper.py` | 大 message_chain 的 str()/model_dump() 同步阻塞事件循环 → WS ping timeout | **转制自 process.py / monitoring_helper.py 整文件补丁**——旧整文件版未进 entrypoint，容器重建后已丢失（2026-08-28 md5 核实），本脚本为唯一现役形态 |
| [patch_forward_speaker.py](patch_forward_speaker.py) | `pkg/platform/sources/aiocqhttp.py` | 合并转发丢说话人归属（8/24 事故）+ 直发 forward 被 `pass` 整体丢弃；napcat `parseMultMsg:false` 需 get_msg 回取。**同时把 reply 分支裸 `get_msg` 包上 wait_for(30)**——adapter 收消息路径上无超时的外部调用曾致单群静默 | 2026-08-28 新增 |

## 测试

```bash
python3 test_patches.py          # 在 baselines/ 副本上验证幂等/编译/锚点/import
```

`baselines/` 为容器导出基线（锚点回归的对照物，LangBot 升级后先重导出再跑测试）：

```bash
docker exec langbot cat /app/src/langbot/pkg/platform/sources/aiocqhttp.py > baselines/aiocqhttp.py
docker exec langbot cat /app/src/langbot/pkg/pipeline/process/process.py > baselines/process.py
docker exec langbot cat /app/src/langbot/pkg/pipeline/monitoring_helper.py > baselines/monitoring_helper.py
```

## 部署 / 回滚

```bash
# 部署（NAS）：scp 改动文件到 /volume1/docker/langbot/patches/，然后
docker restart langbot        # entrypoint 自动施加全部 patch；docker logs langbot | grep PATCH 确认
# 回滚（示例 forward 补丁）：
docker exec langbot cp /app/src/langbot/pkg/platform/sources/aiocqhttp.py.orig-fwd-speaker \
  /app/src/langbot/pkg/platform/sources/aiocqhttp.py
# （.orig-evl 同理）→ entrypoint 注释对应行 → docker restart langbot
```

## LangBot 升级流程

1. 重导 baselines → `git diff` 看上游改动
2. `python3 test_patches.py` → 锚点缺失即需人工迁移对应 hunk
3. 镜像重建后 entrypoint 自动重放

## 废弃文件（保留作 diff 参考，勿再部署）

- `process.py`、`monitoring_helper.py`：整文件替换旧形态，职责已被 patch_event_loop_blocks.py 接管
