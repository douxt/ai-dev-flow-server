---
name: lazy-trigger-waterline-pattern
description: 懒触发水位线——"开始工作"作为后台扫描触发事件，非墙钟
created: 2026-07-18
source: offline-scan
origin_session: dfa6089a-1cfa-410b-b935-2f9ca706fa7f
---

**根因**：cron/systemd timer 依赖机器一直开着。用户关机下班，当天的定时任务就漏了。需要一种机制保证"无论机器什么时候开，永远不会因为关机错过任务"。

**解决**：SessionStart 检查水位标记文件（`last-scan`），距上次扫描 >24h 则 nohup 后台启动扫描。扫描范围 = 自上次水位后的增量。关机场景自动兜底：周五关机→周一开机一次补扫三天增量。核心是"开始工作"这个必然事件代替墙钟作为触发器，水位线锚定位置而非时间。

**预防**：
- 任何"每天一次"的后台维护任务优先考虑懒触发+水位线，而不是 cron
- 水位文件本身不放 /tmp（见 [[wsl-tmp-not-persistent]]）
- 扫描任务必须幂等：同水位重跑产出 0 条新结果
- 后台化后注意 hook 的 5s 超时预算，用 nohup 脱钩

