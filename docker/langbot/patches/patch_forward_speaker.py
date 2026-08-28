#!/usr/bin/env python3
"""LangBot aiocqhttp.py 补丁：转发/引用消息保留说话人归属。

背景（2026-08-24 事故）：合并转发内容被拍平成无说话人的裸文本，
bot 无法区分"谁说的"；直发合并转发则整体丢弃（pass → 插件只见 Source）。
napcat 配置 parseMultMsg:false → 事件 forward 段无 content，需 get_msg 回取。

幂等：marker 判重，已打则 skip；锚文本缺失（上游改版）则报错 exit 1。
基线：langbot 容器（非 plugin 容器！）/app/src/.../sources/aiocqhttp.py 610 行版。
"""
import shutil
import sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else '/app/src/langbot/pkg/platform/sources/aiocqhttp.py'
MARKER = '[FWD-SPEAKER-PATCH]'
BACKUP = TARGET + '.orig-fwd-speaker'

with open(TARGET) as f:
    content = f.read()

if MARKER in content:
    print(f'{MARKER} already applied, skip')
    sys.exit(0)

# ── 1a: 引用嵌套 forward 展平时插节点归属头（time 在节点顶层，sender 内是 nickname/card）──
OLD_A = """            elif msg_data['type'] == 'forward':  # 这里来应该传入转发消息组，暂时传入Quote
                for forward_msg_datas in msg_data['data']['content']:
                    for forward_msg_data in forward_msg_datas['message']:
                        await process_message_data(forward_msg_data, reply_list)"""

NEW_A = """            elif msg_data['type'] == 'forward':  # [FWD-SPEAKER-PATCH] 保留说话人归属
                for forward_msg_datas in (msg_data['data'].get('content') or []):
                    try:
                        _fs = forward_msg_datas.get('sender') or {}
                        _fnick = (_fs.get('card') or _fs.get('nickname')
                                  or (str(_fs['user_id']) if _fs.get('user_id') else '未知'))
                        _ft = forward_msg_datas.get('time')
                        _fhead = f'[{_fnick}' + (
                            f' {time.strftime("%m-%d %H:%M", time.localtime(int(_ft)))}]'
                            if _ft else ']')
                        reply_list.append(platform_message.Plain(text=_fhead))
                    except Exception:
                        pass
                    for forward_msg_data in forward_msg_datas.get('message', []):
                        await process_message_data(forward_msg_data, reply_list)"""

# ── 1b: 顶层直发合并转发，从 pass 改为构造真 Forward 组件 ──
OLD_B = """            elif msg.type == 'forward':
                # 暂时不太合理
                # msg_datas = await bot.get_msg(message_id=message_id)
                # print(msg_datas)
                # for msg_data in msg_datas["message"]:
                #     await process_message_data(msg_data, yiri_msg_list)
                pass"""

NEW_B = """            elif msg.type == 'forward':
                # [FWD-SPEAKER-PATCH] 直发合并转发不再丢弃；事件无 content
                # （napcat parseMultMsg=false）→ get_msg 回取；失败降级为占位
                try:
                    _fwd_content = (msg.data or {}).get('content')
                    if not _fwd_content:
                        _fwd_datas = await asyncio.wait_for(
                            bot.get_msg(message_id=msg.data['id']), timeout=30)
                        _fwd_content = next(
                            (m.get('data', {}).get('content')
                             for m in _fwd_datas.get('message', [])
                             if m.get('type') == 'forward'), [])
                    _fwd_nodes = []
                    for _fi, _fitem in enumerate(_fwd_content or []):
                        if _fi and _fi % 10 == 0:
                            await asyncio.sleep(0)
                        _snd = _fitem.get('sender') or {}
                        _chain = []
                        for _fm in _fitem.get('message', []):
                            if _fm.get('type') == 'image':
                                _chain.append(platform_message.Plain(text='[图片]'))
                            else:
                                try:
                                    _tmp = []
                                    await process_message_data(_fm, _tmp)
                                    _chain.extend(_tmp)
                                except Exception:
                                    pass
                        _fwd_nodes.append(platform_message.ForwardMessageNode(
                            sender_id=_snd.get('user_id', ''),
                            sender_name=_snd.get('card') or _snd.get('nickname') or '',
                            message_chain=platform_message.MessageChain(_chain)))
                    yiri_msg_list.append(platform_message.Forward(node_list=_fwd_nodes))
                except Exception:
                    yiri_msg_list.append(platform_message.Plain(text='[转发消息解析失败]'))"""

missing = [name for name, old in (('1a-flatten', OLD_A), ('1b-forward', OLD_B)) if old not in content]
if missing:
    print(f'{MARKER} ERROR: anchor not found: {",".join(missing)} (上游改版？人工核对 {TARGET})')
    sys.exit(1)

shutil.copyfile(TARGET, BACKUP)  # 仅首次（marker 在前已 skip，不会覆盖备份）
content = content.replace(OLD_A, NEW_A, 1).replace(OLD_B, NEW_B, 1)
with open(TARGET, 'w') as f:
    f.write(content)
print(f'{MARKER} applied successfully (backup: {BACKUP})')
