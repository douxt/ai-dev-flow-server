# 接通 vision URL-first 识图（vision-url-enable）

> 2026-08-28 | 前篇 forward-speaker-fix 已合并（main=`a32c90b`，计划归档 docs/plans/）。本计划是其治理中发现的"7 月半成品线路"补完，旧计划文件已被覆盖（归档件在仓库）

## Context

7/25 `c3cca17` 实现过"识图直传图片 URL、免本地下载上传"：插件侧 URL-first（[vision.py](docker/langbot/plugins/silent-observer/service/vision.py) `_describe_one`：`img.url` 存在则 `from_image_url(url)` 交给模型自取，异常**自动回退 base64 路径**——回退链已读码确认）+ 宿主透传补丁 `patch_image_url.py`。但宿主补丁从写入起就是语法坏的（每次启动喷 traceback），从未生效——生产 gate.log 铁证：**url_ok=0 / b64_ok=105**。

昨天补丁体系治理中已把脚本重写为语法正确，并刻意注释停用（当时误判为"可疑历史包袱"）。真相澄清后：这是**未接通的既定 feature**，本计划把它接通并按实证决定去留。

风险边界（已核实）：
- Image(base64=…, url=…) 双字段并存，回退路径 `get_bytes()` 吃内存 base64（现状 get=0.0s），无额外网络依赖
- url 失败仅多付一次模型调用尝试（`asyncio.wait_for(45s)` 封顶）后走现路径
- 真正未知项：**识图模型服务端**能否拉取 QQ 图床外链（`p.qpic.cn` 类签名 url，有效期小时级，vision 在 gate 后秒级触发，过期风险低）

## 改动（零代码——纯启用+观测）

### 1. 启用（NAS + 仓库镜像同步）

- entrypoint：解开 `python3 /patches/patch_image_url.py` 注释（[docker/langbot/entrypoint.sh](docker/langbot/entrypoint.sh) 仓库版 + NAS `/volume1/docker/langbot/entrypoint.sh`，NAS 先备份 `.bak.20260828b`）
- `docker restart langbot`（entrypoint 自动施加；LTM 竞态纪律：healthy 后再看 plugin 无需重启——插件代码未动）

### 2. 每步验证点

| # | 验证 | 命令/判据 | 预期 |
|---|------|----------|------|
| V1 | 补丁施加 | `docker logs langbot --since 2m \| grep IMAGE-URL` + `docker exec langbot grep -c "url=msg" aiocqhttp.py` | applied；计数=2 |
| V2 | 语法/健康 | `docker exec langbot python3 -m py_compile <目标文件>` + 容器 healthy + napcat WS 无断连 | 全过 |
| V3 | 真实回退链 | 测试群发 1 张图 → gate.log vision 行 | 三选一：`url_ok`（接通成功）/ `url failed…fallback` + `b64_ok`（模型不拉外链，线路通但有代价）/ 两条都没有（补丁未生效，回查 V1） |
| V4 | 质量与耗时 | 对比 `url_ok lat=` vs 历史 `b64_ok` lat（均值 ~1s）；desc 内容人工看一条 | url 模式延迟不劣化、描述质量同档 |
| V5 | token 收益 | monitoring_llm_calls（langbot 容器 DB）近 20 条 vision 调用的 tokens：启用前后对比 | 预期显著下降（数百 KB base64 → 一行 url） |
| V6 | 回归面 | 连续发图+引用图+转发含图各 1 次，vision 全链路无新增 fail；`grep -ac 'vision: done ok=0' ` 不升 | 全过 |

### 3. 决策门（验证后二选一，都是 5 分钟内动作）

- **保留**：V3 出 `url_ok` 且 V4/V6 达标 → 更新 patches/README（状态"停用"→"生效，含降级说明"）+ ADR-010 补一行 + 团队记忆 #24 修正"url 透传从未生效"为"已接通"+ 本计划归档
- **回滚**：V3 显示每图都 `url failed` 白等数秒，或 V6 出现识图失败率上升 → entrypoint 重新注释 + `docker cp aiocqhttp.py.orig` 恢复宿主（补丁脚本已自动备份）+ restart + README 记录实证结论（"模型侧不支持 QQ 图床外链，永久停用"——把这次的调查成果钉死，防止未来再考古）

### 4. 提交

- 仓库改动（entrypoint + README/ADR/记忆更新）走 worktree `wt create vision-url-enable`（纪律要求；若最终确认是 NAS-only 配置+文档修改可豁免 worktree，但 entrypoint 属仓库镜像文件，仍走 worktree 保一致）
- V3-V6 由用户在测试群配合发图（真实消息，不用 /sync——/sync 通道无图床 url 链路且合成消息会污染观测）

## 风险

| 风险 | 对策 |
|------|------|
| 模型 API 拒绝外链格式（非 404 而是 400）| 同样走 except → fallback，行为=现状，V3 观测判定 |
| 签名 url 在重试/熔断排队时过期 | 45s 封顶 + 过期即 fallback base64，无用户可见损失 |
| vision 结果进 KB 的文本变化（同图两种描述模型路径）| base64 与 url 喂的是同一视觉模型同一 prompt，仅取图方式不同；V4 人工比对一条 |
| 用户发图频率低导致样本不足 | 最低样本：3 张图（V3/V6 各 1 + 决策前复测 1）；不足则保持启用观察一周（fallback 保底，无恶化风险） |

## 工作量

启用+验证 ~40 分钟（含用户配合发图），决策分支文档收尾 ~15 分钟。
