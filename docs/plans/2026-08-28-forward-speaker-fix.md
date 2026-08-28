# 转发/引用消息说话人归属修复（forward-speaker-fix）v2

> 2026-08-28 | v2：经独立评审+逐条复核修订（3 项 P0 全部证实采纳：基线容器错、事件不带 content、补丁施加机制漂移）

## Context

太空工程师群事故（8/24 02:55–03:26，monitoring DB 实锤）：喵酱引用转发的两人吵架记录（66 条消息）@bot"评价一下此人"，bot 把两人立场张冠李戴，纠正后重评仍错。喵酱定性"把2个人的发言混合在一起判断了"；WZÆ 现场猜中根因方向"名字时间全糊在一起"；douxt 留言"有空查一下bug"——即本计划。

**根因分层（全部容器/DB 实证）**：

| 层 | 事实 |
|----|------|
| napcat（OneBot） | 协议层信息全有：forward 节点 `{time(顶层), sender:{user_id,nickname,card}, message[]}`；但配置 `parseMultMsg:false` → **消息事件的 forward 段只推 `{id}`，无 content**；`get_msg` API 返回才带 content（8/24 的 66 条就是引用路径经 get_msg 到达的） |
| LangBot 适配器（**langbot 容器**内 aiocqhttp.py，610 行版） | ①`process_message_data` forward 分支（:169-172）展平 content 只取 `['message']`，**丢 sender/time** → 66 条裸 Plain；②顶层 `msg.type=='forward'`（:210-216）**直接 pass**（注释掉的就是 get_msg 未完成的 workaround）→ 直发合并转发插件只见 Source（gate.log "forward-only" 实证） |
| SDK 实体 | `ForwardMessageNode(sender_id, sender_name, message_chain, message_id)` 可关键字构造、Forward 序列化注册表齐全（宿主↔插件 WS 双向支持实证）；无 time 字段（时间戳拼文本即可） |
| 插件 timeline.py:48-55 | Forward 分支连现成 `sender_name` 不读，`' '` 拼接 |

**能获取什么的答案**：QQ号 ✅ 昵称/群名片 ✅ 发言时间 ✅——全在 get_msg 返回里，修复后均可用（归属头默认只放昵称+时间，不放 QQ 号）。

**P1.5 观察期联动**：直发转发修复后 `ForwardMessageReceived` handler 将首次收到非 Source-only 链——先查该 handler 的 `forward-only` 早退分支（:366-386 区域）是否会重复处理/双写，作为单测场景。

## 改动

### 1. 宿主补丁 `docker/langbot/patches/patch_forward_speaker.py`（**原地 patch 幂等脚本**，仿 patch_mcp_timeout.py 模式，非整文件替换）

对 langbot 容器 `/app/src/langbot/pkg/platform/sources/aiocqhttp.py`（610 行版）做两处方言式修改，脚本含 marker 判重（grep 补丁标记已打则 skip）：

**1a. forward 展平保留归属（:169-172）**：

```python
elif msg_data['type'] == 'forward':
    for _fnode in (msg_data['data'].get('content') or []):
        # PATCH-fwd-speaker: 节点归属头（time 在节点顶层，sender 无 time）
        try:
            _s = _fnode.get('sender') or {}
            _nick = _s.get('card') or _s.get('nickname') or (_s.get('user_id') and str(_s['user_id']) or '未知')
            _t = _fnode.get('time')
            _head = f'[{_nick}' + (f' {time.strftime("%m-%d %H:%M", time.localtime(int(_t)))}]' if _t else ']')
            reply_list.append(platform_message.Plain(text=_head))
        except Exception:
            pass
        for forward_msg_data in _fnode.get('message', []):
            await process_message_data(forward_msg_data, reply_list)
```

归属头用 **Plain**（Face 不在 SDK 反序列化注册表，会变 Unknown）。文件已有 `import time`（:8），无遮蔽。

**1b. 顶层 forward 构造真组件（:210-216，替换 pass）**：

```python
elif msg.type == 'forward':
    # PATCH-fwd-speaker: 直发合并转发不再丢弃；事件无 content（parseMultMsg=false）→ get_msg 回取
    try:
        _fwd_content = (msg.data or {}).get('content')
        if not _fwd_content:
            _msg_datas = await asyncio.wait_for(bot.get_msg(message_id=msg.data['id']), timeout=30)
            _fwd_content = next((m.get('data', {}).get('content') for m in _msg_datas['message']
                                 if m.get('type') == 'forward'), [])
        _nodes = []
        for _idx, _item in enumerate(_fwd_content or []):
            if _idx and _idx % 10 == 0:
                await asyncio.sleep(0)          # checklist §1 让路
            _s = _item.get('sender') or {}
            _chain = []
            for _m in _item.get('message', []):
                if _m.get('type') == 'image':
                    _chain.append(platform_message.Plain(text='[图片]'))   # 内图不下载，防 getMultiMessages 卡死复发
                else:
                    try:
                        _tmp = []
                        await process_message_data(_m, _tmp)
                        _chain.extend(_tmp)
                    except Exception:
                        pass                     # 单成分坏不炸整条
            _nodes.append(platform_message.ForwardMessageNode(
                sender_id=_s.get('user_id', ''), sender_name=_s.get('card') or _s.get('nickname') or '',
                message_chain=platform_message.MessageChain(_chain)))
        yiri_msg_list.append(platform_message.Forward(node_list=_nodes))
    except Exception as e:
        # 降级=现状：pass
        logger 记 warning（仿文件内既有日志模式）
```

`get_msg` 包 `asyncio.wait_for(30)`（文件 :317/:353 有同款模式）。E2E 回流同走此 fallback，测试即回归。

### 2. 插件 `service/timeline.py` extract_text Forward 分支（~4 行）

```python
elif ctype == 'Forward':
    for node in nodes:
        mc = getattr(node, 'message_chain', None)
        if mc is not None:
            forward_text = await self.extract_text(mc, max_length, image_descriptions, depth + 1)
            if forward_text:
                nick = getattr(node, 'sender_name', '') or str(getattr(node, 'sender_id', '') or '?')
                parts.append(f'\n[{nick}] {forward_text}')
```

（键名 `node_list` 两端一致已核实，插件所有 Forward 分支均用 node_list。）

### 3. 部署体系治理（评审 P0-3，本次必修）

现状：entrypoint.sh（NAS bind 挂载，幂等模式）只打 `patch_mcp_timeout.py` + `patch_image_url.py`；**process.py / monitoring_helper.py 两个整文件补丁未在容器生效**（md5 不符 + `run_in_executor` 0 命中——事件循环阻塞保护当前裸奔，容器重建时丢了）。

- `patch_forward_speaker.py` 注册进 entrypoint（NAS `/volume1/docker/langbot/entrypoint.sh` + 仓库同步一份）
- **process/monitoring 整文件补丁改为幂等原地 patch 脚本**（`patch_event_loop_blocks.py`：to_thread/日志截断两处 marker patch），消除"重建即丢"模式；旧整文件保留在仓库 patches/ 作 diff 参考，README 标注废弃
- **仓库 patches/ 与 NAS /volume1/docker/langbot/patches/ 先做三向核对**（NAS 的 patch_image_url 比仓库多"PR version skip"逻辑——以容器生效版回灌仓库）
- README 清单补齐：patch_mcp_timeout.py（仓库本就没有）、patch_image_url（已在用未登记）、新增两个 patch 行

### 4. 测试

**插件单测** `tests/test_forward_speaker.py`（~10 用例，仿 conftest FakePlain 造 FakeForwardNode(sender_name=..., message_chain=[...])）：
1-2. extract_text 单/多节点 → 归属前缀 `[怪异的萌]`、独立分行
3. sender_name 空 → 回落 sender_id → '?'
4. 嵌套 Forward 归属保留
5. 单 Plain 消息路径回归（`\n` 前缀不破坏 join）
6. **P1.5 联动**：ForwardMessageReceived handler 收 Source+Forward 链 → forward-only 早退分支不误伤、无双写
7-10. 引用场景回归 + 现有 quote/timeline 测试全绿

**补丁脚本测试**（bats 或 python 冒烟）：对临时副本文件跑 patch 两遍 → 幂等（marker 判重）；patch 后 `py_compile` 通过；关键行断言（get_msg fallback、Plain 归属头、ForwardMessageNode 构造）——仿 patch_mcp_timeout 既有测试模式（若无则新建 tests/patches/ 最小 bats）。

**宿主 E2E（NAS，唯一可靠验证——行号在真实文件上）**：
- `docker cp patch_forward_speaker.py langbot:/patches/` + 手动执行 + `docker restart langbot`（healthy 后再 restart plugin，LTM 竞态教训）
- **真实复现验证**：查 chat_index.db 8/24 02:55 记录（message_id 1962097114）经新路径能否取到 content（napcat 历史消息若已过期则 SKIP 此步，直接进合成回放）
- 合成回放 `tests/scripts/verify_forward_speaker.py`：调 napcat onebot HTTP（`0.0.0.0:5700`，token 在 onebot11 配置）`send_group_forward_msg` 向测试群 1104330614 发 2-node 转发（"甲:我车不烧机油 / 乙:EA888必修"，`reportSelfMessage:true` 回流）→ 断言 gate.log RAW PROMPT 含 `[甲]`/`[乙]`（覆盖 1b get_msg fallback）→ 再补一条引用该转发的消息断言 1a 路径
- **生产复验**：请喵酱真实引用一次 → monitoring 查回复人物归属

### 5. 回滚

entrypoint 摘除 patch 调用 + 容器内从 `.orig`（patch 脚本施加时自动备份）恢复 aiocqhttp.py + 重启；插件 `.bak` 恢复。

## 改动清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `docker/langbot/patches/patch_forward_speaker.py`（新） | 1a 归属头 + 1b get_msg fallback 构造 Forward |
| 2 | `docker/langbot/patches/patch_event_loop_blocks.py`（新） | process/monitoring 整文件补丁 → 幂等原地 patch |
| 3 | NAS entrypoint.sh + 仓库镜像 + patches/README | 注册 3 个 patch + 清单漂移修复 + 三向核对回灌 |
| 4 | `service/timeline.py` | Forward 分支归属前缀 ~4 行 |
| 5 | `tests/test_forward_speaker.py`（新） | ~10 用例（含 P1.5 联动） |
| 6 | `tests/scripts/verify_forward_speaker.py`（新） | napcat 合成转发 E2E |
| 7 | patch 脚本幂等测试 | 双跑不重复 + py_compile |

## 风险

| 风险 | 对策 |
|------|------|
| 上游升级重打：整文件替换会被镜像更新覆盖，**原地 patch 脚本 marker 判重**天然兼容"已升级"检测（锚文本变了即 skip+报警） | patch 脚本 anchor 找不到时 exit 非 0，entrypoint 日志可见 |
| 1b get_msg 慢（大转发） | wait_for(30s) + 内图占位 + sleep(0)；失败降级=现状 pass |
| `[nick]` 头改变模型输入 | 与归档行 `[时间] 昵称:` 同构；E2E 目检 |
| 直发 forward 修复后 P1.5/压缩/KB 路径行为变化面 | 单测 6 覆盖 forward-only 早退联动；一周观察期正好同时盯此项 |
| 隐私 | 归属头 card>nickname>QQ号回落，默认不输出裸 QQ 号；转发内容本就群内公开 |
| monitoring 体积 | 内图占位不入 base64；归属头 KB 级（评审已核算） |

## 工作量

补丁脚本+单测 ~2.5h，部署治理 ~1h，NAS 部署+E2E ~1h。与 P1.5 一周观察期并行（不碰反思/注入路径）。
