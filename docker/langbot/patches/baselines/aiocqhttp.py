from __future__ import annotations
import typing
import asyncio
import traceback
import datetime
import json
import time

import aiocqhttp
import pydantic

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
from ...utils import image
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


_GROUP_NAME_CACHE_TTL_SECONDS = 3600
_GROUP_NAME_NEGATIVE_CACHE_TTL_SECONDS = 60
_GROUP_NAME_LOOKUP_TIMEOUT_SECONDS = 2
_GROUP_MEMBER_INFO_CACHE_TTL_SECONDS = 86400
_GROUP_MEMBER_INFO_NEGATIVE_CACHE_TTL_SECONDS = 600
_GROUP_MEMBER_INFO_LOOKUP_TIMEOUT_SECONDS = 2


def _normalize_base64_payload(value: str) -> str:
    if value.startswith('base64://'):
        return value.removeprefix('base64://')
    if value.startswith('data:') and ';base64,' in value:
        return value.split(';base64,', 1)[1]
    return value


def _get_field(data: dict, key: str, default: str = '') -> str:
    value = data.get(key)
    if value is None:
        return default
    return str(value)


def _get_group_member_name(sender: dict) -> str:
    return _get_field(sender, 'card') or _get_field(sender, 'nickname') or _get_field(sender, 'user_id')


def _get_group_name_placeholder(group_id: typing.Union[int, str]) -> str:
    return f'Group {group_id}'


class AiocqhttpMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(
        message_chain: platform_message.MessageChain,
    ) -> typing.Tuple[list, int, datetime.datetime]:
        msg_list = aiocqhttp.Message()

        msg_id = 0
        msg_time = None

        for msg in message_chain:
            if type(msg) is platform_message.Plain:
                msg_list.append(aiocqhttp.MessageSegment.text(msg.text))
            elif type(msg) is platform_message.Source:
                msg_id = msg.id
                msg_time = msg.time
            elif type(msg) is platform_message.Image:
                arg = ''
                if msg.base64:
                    arg = _normalize_base64_payload(msg.base64)
                    msg_list.append(aiocqhttp.MessageSegment.image(f'base64://{arg}'))
                elif msg.url:
                    arg = msg.url
                    msg_list.append(aiocqhttp.MessageSegment.image(arg))
                elif msg.path:
                    arg = msg.path
                    msg_list.append(aiocqhttp.MessageSegment.image(arg))
            elif type(msg) is platform_message.At:
                msg_list.append(aiocqhttp.MessageSegment.at(msg.target))
            elif type(msg) is platform_message.AtAll:
                msg_list.append(aiocqhttp.MessageSegment.at('all'))
            elif type(msg) is platform_message.Voice:
                arg = ''
                if msg.base64:
                    arg = _normalize_base64_payload(msg.base64)
                    msg_list.append(aiocqhttp.MessageSegment.record(f'base64://{arg}'))
                elif msg.url:
                    arg = msg.url
                    msg_list.append(aiocqhttp.MessageSegment.record(arg))
                elif msg.path:
                    arg = msg.path
                    msg_list.append(aiocqhttp.MessageSegment.record(msg.path))
            elif type(msg) is platform_message.Forward:
                for node in msg.node_list:
                    msg_list.extend((await AiocqhttpMessageConverter.yiri2target(node.message_chain))[0])
            elif isinstance(msg, platform_message.File):
                file = msg.url or msg.path
                if not file and msg.base64:
                    file = f'base64://{_normalize_base64_payload(msg.base64)}'
                msg_list.append({'type': 'file', 'data': {'file': file, 'name': msg.name}})
            elif isinstance(msg, platform_message.Face):
                if msg.face_type == 'face':
                    msg_list.append(aiocqhttp.MessageSegment.face(msg.face_id))
                elif msg.face_type == 'rps':
                    msg_list.append(aiocqhttp.MessageSegment.rps())
                elif msg.face_type == 'dice':
                    msg_list.append(aiocqhttp.MessageSegment.dice())

            else:
                msg_list.append(aiocqhttp.MessageSegment.text(str(msg)))

        return msg_list, msg_id, msg_time

    @staticmethod
    async def target2yiri(message: str, message_id: int = -1, bot: aiocqhttp.CQHttp = None):
        message = aiocqhttp.Message(message)

        # ═══ QQ face map (from face_config.json, 282 entries) ═══
        _FACE_MAP = {
        0: "惊讶", 1: "撇嘴", 2: "色", 3: "发呆", 4: "得意", 5: "流泪", 6: "害羞", 7: "闭嘴",
        8: "睡", 9: "大哭", 10: "尴尬", 11: "发怒", 12: "调皮", 13: "呲牙", 14: "微笑", 15: "难过",
        16: "酷", 18: "抓狂", 19: "吐", 20: "偷笑", 21: "可爱", 22: "白眼", 23: "傲慢", 24: "饥饿",
        25: "困", 26: "惊恐", 27: "流汗", 28: "憨笑", 29: "悠闲", 30: "奋斗", 31: "咒骂", 32: "疑问",
        33: "嘘", 34: "晕", 35: "折磨", 36: "衰", 37: "骷髅", 38: "敲打", 39: "再见", 41: "发抖",
        42: "爱情", 43: "跳跳", 46: "猪头", 49: "拥抱", 53: "蛋糕", 55: "炸弹", 56: "刀", 59: "便便",
        60: "咖啡", 63: "玫瑰", 64: "凋谢", 66: "爱心", 67: "心碎", 74: "太阳", 75: "月亮", 76: "赞",
        77: "踩", 78: "握手", 79: "胜利", 85: "飞吻", 86: "怄火", 89: "西瓜", 96: "冷汗", 97: "擦汗",
        98: "抠鼻", 99: "鼓掌", 100: "糗大了", 101: "坏笑", 102: "左哼哼", 103: "右哼哼", 104: "哈欠", 105: "鄙视",
        106: "委屈", 107: "快哭了", 108: "阴险", 109: "左亲亲", 110: "吓", 111: "可怜", 112: "菜刀", 114: "篮球",
        116: "示爱", 118: "抱拳", 119: "勾引", 120: "拳头", 121: "差劲", 122: "爱你", 123: "NO", 124: "OK",
        125: "转圈", 129: "挥手", 137: "鞭炮", 144: "喝彩", 146: "爆筋", 147: "棒棒糖", 148: "喝奶", 169: "手枪",
        171: "茶", 172: "眨眼睛", 173: "泪奔", 174: "无奈", 175: "卖萌", 176: "小纠结", 177: "喷血", 178: "斜眼笑",
        179: "doge", 180: "惊喜", 181: "戳一戳", 182: "笑哭", 183: "我最美", 185: "羊驼", 187: "幽灵", 193: "大笑",
        194: "不开心", 198: "呃", 200: "求求", 201: "点赞", 202: "无聊", 203: "托脸", 204: "吃", 206: "害怕",
        210: "飙泪", 211: "我不看", 212: "托腮", 214: "啵啵", 215: "糊脸", 216: "拍头", 217: "扯一扯", 218: "舔一舔",
        219: "蹭一蹭", 221: "顶呱呱", 222: "抱抱", 223: "暴击", 224: "开枪", 225: "撩一撩", 226: "拍桌", 227: "拍手",
        229: "干杯", 230: "嘲讽", 231: "哼", 232: "佛系", 233: "掐一掐", 235: "颤抖", 237: "偷看", 238: "扇脸",
        239: "原谅", 240: "喷脸", 241: "生日快乐", 243: "甩头", 244: "扔狗", 262: "脑阔疼", 263: "沧桑", 264: "捂脸",
        265: "辣眼睛", 266: "哦哟", 267: "头秃", 268: "问号脸", 269: "暗中观察", 270: "emm", 271: "吃瓜", 272: "呵呵哒",
        273: "我酸了", 277: "汪汪", 278: "汗", 281: "无眼笑", 282: "敬礼", 283: "狂笑", 284: "面无表情", 285: "摸鱼",
        286: "魔鬼笑", 287: "哦", 288: "请", 289: "睁眼", 290: "敲开心", 292: "让我康康", 293: "摸锦鲤", 294: "期待",
        295: "拿到红包", 297: "拜谢", 298: "元宝", 299: "牛啊", 300: "胖三斤", 301: "好闪", 302: "左拜年", 303: "右拜年",
        305: "右亲亲", 306: "牛气冲天", 307: "喵喵", 311: "打call", 312: "变形", 314: "仔细分析", 317: "菜汪", 318: "崇拜",
        319: "比心", 320: "庆祝", 322: "拒绝", 323: "嫌弃", 324: "吃糖", 325: "惊吓", 326: "生气", 332: "举牌牌",
        333: "烟花", 334: "虎虎生威", 336: "豹富", 337: "花朵脸", 338: "我想开了", 339: "舔屏", 341: "打招呼", 342: "酸Q",
        343: "我方了", 344: "大怨种", 345: "红包多多", 346: "你真棒棒", 347: "大展宏兔", 348: "福萝卜", 349: "坚强", 350: "贴贴",
        351: "敲敲", 352: "咦", 353: "拜托", 354: "尊嘟假嘟", 355: "耶", 356: "666", 357: "裂开", 358: "骰子",
        359: "包剪锤", 360: "亲亲", 361: "狗狗笑哭", 362: "好兄弟", 363: "狗狗可怜", 364: "超级赞", 365: "狗狗生气", 366: "芒狗",
        367: "狗狗疑问", 368: "奥特笑哭", 369: "彩虹", 370: "祝贺", 371: "冒泡", 372: "气呼呼", 373: "忙", 374: "波波流泪",
        375: "超级鼓掌", 376: "跺脚", 377: "嗨", 378: "企鹅笑哭", 379: "企鹅流泪", 380: "真棒", 381: "路过", 382: "emo",
        383: "企鹅爱心", 384: "晚安", 385: "太气了", 386: "呜呜呜", 387: "太好笑", 388: "太头疼", 389: "太赞了", 390: "太头秃",
        391: "太沧桑", 392: "龙年快乐", 393: "新年中龙", 394: "新年大龙", 395: "略略略", 396: "狼狗", 397: "抛媚眼", 398: "超级ok",
        399: "tui", 400: "快乐", 401: "超级转圈", 402: "别说话", 403: "出去玩", 404: "闪亮登场", 405: "好运来", 406: "姐是女王",
        407: "我听听", 408: "臭美", 409: "送你花花", 410: "么么哒", 411: "一起嗨", 412: "开心", 413: "摇起来", 415: "划龙舟",
        416: "中龙舟", 417: "大龙舟",
        }

        def get_face_name(face_id):
            return _FACE_MAP.get(int(face_id), '')

        async def process_message_data(msg_data, reply_list):
            if msg_data['type'] == 'image':
                image_base64, image_format = await image.qq_image_url_to_base64(msg_data['data']['url'])
                reply_list.append(platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}'))

            elif msg_data['type'] == 'text':
                reply_list.append(platform_message.Plain(text=msg_data['data']['text']))

            elif msg_data['type'] == 'forward':  # 这里来应该传入转发消息组，暂时传入Quote
                for forward_msg_datas in msg_data['data']['content']:
                    for forward_msg_data in forward_msg_datas['message']:
                        await process_message_data(forward_msg_data, reply_list)

            elif msg_data['type'] == 'at':
                if msg_data['data']['qq'] == 'all':
                    reply_list.append(platform_message.AtAll())
                else:
                    reply_list.append(
                        platform_message.At(
                            target=msg_data['data']['qq'],
                        )
                    )

        yiri_msg_list = []

        yiri_msg_list.append(platform_message.Source(id=message_id, time=datetime.datetime.now()))

        for msg in message:
            reply_list = []
            if msg.type == 'at':
                if msg.data['qq'] == 'all':
                    yiri_msg_list.append(platform_message.AtAll())
                else:
                    yiri_msg_list.append(
                        platform_message.At(
                            target=msg.data['qq'],
                        )
                    )
            elif msg.type == 'text':
                yiri_msg_list.append(platform_message.Plain(text=msg.data['text']))
            elif msg.type == 'image':
                emoji_id = msg.data.get('emoji_package_id', None)
                if emoji_id:
                    face_name = msg.data.get('summary', '') or f'emoji_{emoji_id}'
                    image_msg = platform_message.Plain(text=f'[QQ表情:{face_name}]')
                else:
                    image_base64, image_format = await image.qq_image_url_to_base64(msg.data['url'])
                    image_msg = platform_message.Image(base64=f'data:image/{image_format};base64,{image_base64}')
                yiri_msg_list.append(image_msg)
            elif msg.type == 'forward':
                # 暂时不太合理
                # msg_datas = await bot.get_msg(message_id=message_id)
                # print(msg_datas)
                # for msg_data in msg_datas["message"]:
                #     await process_message_data(msg_data, yiri_msg_list)
                pass

            elif msg.type == 'reply':  # 此处处理引用消息传入Quote
                msg_datas = await bot.get_msg(message_id=msg.data['id'])

                for msg_data in msg_datas['message']:
                    await process_message_data(msg_data, reply_list)

                reply_msg = platform_message.Quote(
                    message_id=msg.data['id'], sender_id=msg_datas['user_id'], origin=reply_list
                )
                yiri_msg_list.append(reply_msg)

            elif msg.type == 'file':
                pass
                # file_name = msg.data['file']
                # file_id = msg.data['file_id']
                # file_data = await bot.get_file(file_id=file_id)
                # file_name = file_data.get('file_name')
                # file_path = file_data.get('file')
                # _ = file_path
                # file_url = file_data.get('file_url')
                # file_size = file_data.get('file_size')
                # yiri_msg_list.append(platform_message.File(id=file_id, name=file_name,url=file_url,size=file_size))
            elif msg.type == 'face':
                face_id = msg.data['id']
                face_name = msg.data.get('raw', {}).get('faceText', '')
                if not face_name:
                    face_name = get_face_name(face_id)
                face_name = face_name.replace('/', '')
                if not face_name:
                    face_name = f'id_{face_id}'
                yiri_msg_list.append(platform_message.Plain(text=f'[QQ表情:{face_name}]'))
            elif msg.type == 'rps':
                yiri_msg_list.append(platform_message.Plain(text='[QQ表情:猜拳]'))
            elif msg.type == 'dice':
                yiri_msg_list.append(platform_message.Plain(text='[QQ表情:骰子]'))
            elif msg.type == 'json':
                try:
                    raw = msg.data.get('data', {})
                    if isinstance(raw, str):
                        raw = json.loads(raw)
                    if isinstance(raw, dict):
                        _meta = raw.get('meta', {}) or {}
                        if isinstance(_meta, dict):
                            _detail = _meta.get('detail_1') or _meta.get('music') or _meta.get('news') or {}
                        else:
                            _detail = {}
                        if isinstance(_detail, dict):
                            preview = _detail.get('preview', '')
                            title = _detail.get('desc', '') or _detail.get('title', '')
                            url = _detail.get('qqdocurl', '') or _detail.get('jumpUrl', '')
                        else:
                            preview = title = url = ''
                        text = ' '.join([f'[{raw.get("app", "")}]', preview, title, url]).strip()
                        yiri_msg_list.append(platform_message.Plain(text=text or '[收到一张JSON卡片]'))
                    else:
                        yiri_msg_list.append(platform_message.Plain(text=str(raw)))
                except Exception:
                    yiri_msg_list.append(platform_message.Plain(text='[收到一张JSON卡片]'))

        # DEBUG: log unhandled message types
        for _msg in message:
            _t = getattr(_msg, 'type', '?')
            if _t not in ('at','text','image','forward','reply','file','face','rps','dice','json'):
                import sys
                keys = list(_msg.data.keys()) if hasattr(_msg, 'data') else []
                print(f'[NAPCAT_UNHANDLED] type={_t} keys={keys}', file=sys.stderr, flush=True)
        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class AiocqhttpEventConverter(abstract_platform_adapter.AbstractEventConverter):
    def __init__(self):
        self._group_name_cache: dict[typing.Union[int, str], tuple[str, float]] = {}
        self._group_name_negative_cache: dict[typing.Union[int, str], float] = {}
        self._group_member_info_cache: dict[
            tuple[typing.Union[int, str], typing.Union[int, str]], tuple[dict, float]
        ] = {}
        self._group_member_info_negative_cache: dict[tuple[typing.Union[int, str], typing.Union[int, str]], float] = {}

    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent, bot_account_id: int):
        return event.source_platform_object

    async def _get_group_name(self, group_id: typing.Union[int, str], bot=None) -> str:
        now = time.monotonic()
        if group_id in self._group_name_cache:
            group_name, expires_at = self._group_name_cache[group_id]
            if expires_at > now:
                return group_name
            del self._group_name_cache[group_id]
        if group_id in self._group_name_negative_cache:
            expires_at = self._group_name_negative_cache[group_id]
            if expires_at > now:
                return ''
            del self._group_name_negative_cache[group_id]
        if bot is None:
            return ''
        try:
            group_info = await asyncio.wait_for(
                bot.get_group_info(group_id=group_id),
                timeout=_GROUP_NAME_LOOKUP_TIMEOUT_SECONDS,
            )
        except Exception:
            self._group_name_negative_cache[group_id] = now + _GROUP_NAME_NEGATIVE_CACHE_TTL_SECONDS
            return ''
        group_name = _get_field(group_info, 'group_name') if isinstance(group_info, dict) else ''
        if group_name:
            self._group_name_cache[group_id] = (group_name, now + _GROUP_NAME_CACHE_TTL_SECONDS)
            self._group_name_negative_cache.pop(group_id, None)
        else:
            self._group_name_negative_cache[group_id] = now + _GROUP_NAME_NEGATIVE_CACHE_TTL_SECONDS
        return group_name

    async def _get_group_member_info(
        self,
        group_id: typing.Union[int, str],
        user_id: typing.Union[int, str],
        bot=None,
    ) -> dict:
        now = time.monotonic()
        cache_key = (group_id, user_id)
        if cache_key in self._group_member_info_cache:
            member_info, expires_at = self._group_member_info_cache[cache_key]
            if expires_at > now:
                return member_info
            del self._group_member_info_cache[cache_key]
        if cache_key in self._group_member_info_negative_cache:
            expires_at = self._group_member_info_negative_cache[cache_key]
            if expires_at > now:
                return {}
            del self._group_member_info_negative_cache[cache_key]
        if bot is None:
            return {}
        try:
            member_info = await asyncio.wait_for(
                bot.get_group_member_info(group_id=group_id, user_id=user_id),
                timeout=_GROUP_MEMBER_INFO_LOOKUP_TIMEOUT_SECONDS,
            )
        except Exception:
            self._group_member_info_negative_cache[cache_key] = now + _GROUP_MEMBER_INFO_NEGATIVE_CACHE_TTL_SECONDS
            return {}
        if isinstance(member_info, dict) and member_info:
            self._group_member_info_cache[cache_key] = (
                member_info,
                now + _GROUP_MEMBER_INFO_CACHE_TTL_SECONDS,
            )
            self._group_member_info_negative_cache.pop(cache_key, None)
            return member_info
        self._group_member_info_negative_cache[cache_key] = now + _GROUP_MEMBER_INFO_NEGATIVE_CACHE_TTL_SECONDS
        return {}

    async def target2yiri(self, event: aiocqhttp.Event, bot=None):
        yiri_chain = await AiocqhttpMessageConverter.target2yiri(event.message, event.message_id, bot)

        if event.message_type == 'group':
            permission = 'MEMBER'
            group_name = await self._get_group_name(event.group_id, bot) or _get_group_name_placeholder(event.group_id)
            special_title = _get_field(event.sender, 'title')
            if not special_title:
                member_info = await self._get_group_member_info(event.group_id, event.sender['user_id'], bot)
                special_title = _get_field(member_info, 'title')

            if 'role' in event.sender:
                if event.sender['role'] == 'admin':
                    permission = 'ADMINISTRATOR'
                elif event.sender['role'] == 'owner':
                    permission = 'OWNER'
            converted_event = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.sender['user_id'],  # message_seq 放哪？
                    member_name=_get_group_member_name(event.sender),
                    permission=permission,
                    group=platform_entities.Group(
                        id=event.group_id,
                        name=group_name,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title=special_title,
                ),
                message_chain=yiri_chain,
                time=event.time,
                source_platform_object=event,
            )
            return converted_event
        elif event.message_type == 'private':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.sender['user_id'],
                    nickname=event.sender['nickname'],
                    remark='',
                ),
                message_chain=yiri_chain,
                time=event.time,
                source_platform_object=event,
            )


class AiocqhttpAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: aiocqhttp.CQHttp = pydantic.Field(exclude=True, default_factory=aiocqhttp.CQHttp)

    message_converter: AiocqhttpMessageConverter = AiocqhttpMessageConverter()
    event_converter: AiocqhttpEventConverter = pydantic.Field(default_factory=AiocqhttpEventConverter)

    on_websocket_connection_event_cache: typing.List[typing.Callable[[aiocqhttp.Event], None]] = []

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        super().__init__(
            config=config,
            logger=logger,
        )

        async def shutdown_trigger_placeholder():
            while True:
                await asyncio.sleep(1)

        self.config['shutdown_trigger'] = shutdown_trigger_placeholder

        self.on_websocket_connection_event_cache = []

        if 'access-token' in config:
            self.bot = aiocqhttp.CQHttp(access_token=config['access-token'])
            del self.config['access-token']
        else:
            self.bot = aiocqhttp.CQHttp()

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        # Check if message contains a Forward component
        forward_msg = message.get_first(platform_message.Forward)
        if forward_msg:
            if target_type == 'group':
                # Send as merged forward message via OneBot API
                await self._send_forward_message(int(target_id), forward_msg)
                return
            else:
                await self.logger.warning(
                    f'Forward message is only supported for group targets, got target_type={target_type}. Falling through to normal send.'
                )

        aiocq_msg = (await AiocqhttpMessageConverter.yiri2target(message))[0]

        if target_type == 'group':
            await self.bot.send_group_msg(group_id=int(target_id), message=aiocq_msg)
        elif target_type == 'person':
            await self.bot.send_private_msg(user_id=int(target_id), message=aiocq_msg)

    async def _send_forward_message(self, group_id: int, forward: platform_message.Forward):
        """Send a merged forward message to a group using NapCat extended API."""
        messages = []

        for node in forward.node_list:
            # Build content for each node
            content = []
            if node.message_chain:
                for component in node.message_chain:
                    if isinstance(component, platform_message.Plain):
                        if component.text:
                            content.append({'type': 'text', 'data': {'text': component.text}})
                    elif isinstance(component, platform_message.Image):
                        img_data = {}
                        if component.base64:
                            b64 = _normalize_base64_payload(component.base64)
                            img_data['file'] = f'base64://{b64}'
                        elif component.url:
                            img_data['file'] = component.url
                        elif component.path:
                            img_data['file'] = str(component.path)

                        if img_data:
                            content.append({'type': 'image', 'data': img_data})

            if not content:
                continue

            # Build node data - use user_id and nickname format for NapCat
            user_id = str(node.sender_id) if node.sender_id else str(self.bot_account_id or '10000')
            node_data = {
                'type': 'node',
                'data': {
                    'user_id': user_id,
                    'nickname': node.sender_name or '未知',
                    'content': content,
                },
            }

            messages.append(node_data)

        if not messages:
            return

        # Build the full message payload for NapCat's send_forward_msg API
        # This matches the format used by GiveMeSetuPlugin
        bot_id = str(self.bot_account_id) if self.bot_account_id else '10000'
        payload = {
            'group_id': group_id,
            'user_id': bot_id,  # Required by NapCat for display
            'messages': messages,
        }

        # Add display settings if available
        if forward.display:
            if forward.display.title:
                payload['news'] = [{'text': forward.display.title}]
            if forward.display.brief:
                payload['prompt'] = forward.display.brief
            if forward.display.summary:
                payload['summary'] = forward.display.summary
            if forward.display.source:
                payload['source'] = forward.display.source

        try:
            # Use send_forward_msg (NapCat extended API) instead of send_group_forward_msg
            await self.logger.info(
                f'Sending forward message to group {group_id} with {len(messages)} nodes, payload keys: {list(payload.keys())}'
            )
            result = await self.bot.call_action('send_forward_msg', **payload)
            await self.logger.info(f'Forward message sent to group {group_id}, result: {result}')
        except Exception as e:
            await self.logger.error(f'Failed to send forward message to group {group_id}: {e}')
            # Fallback: try standard OneBot API with integer group_id
            try:
                await self.logger.info('Trying fallback API send_group_forward_msg')
                await self.bot.call_action('send_group_forward_msg', group_id=group_id, messages=messages)
                await self.logger.info(f'Forward message sent via fallback API to group {group_id}')
            except Exception as e2:
                await self.logger.error(f'Fallback also failed: {e2}')
                raise

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        aiocq_event = await AiocqhttpEventConverter.yiri2target(message_source, self.bot_account_id)
        aiocq_msg = (await AiocqhttpMessageConverter.yiri2target(message))[0]
        if quote_origin:
            aiocq_msg = aiocqhttp.MessageSegment.reply(aiocq_event.message_id) + aiocq_msg

        return await self.bot.send(aiocq_event, aiocq_msg)

    async def is_muted(self, group_id: int) -> bool:
        return False

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: aiocqhttp.Event):
            self.bot_account_id = event.self_id
            try:
                return await callback(await self.event_converter.target2yiri(event, self.bot), self)
            except Exception:
                await self.logger.error(f'Error in on_message: {traceback.format_exc()}')
                traceback.print_exc()

        if event_type == platform_events.GroupMessage:
            self.bot.on_message('group')(on_message)
            # self.bot.on_notice()(on_message)
        elif event_type == platform_events.FriendMessage:
            self.bot.on_message('private')(on_message)
            # self.bot.on_notice()(on_message)
        # print(event_type)

        async def on_websocket_connection(event: aiocqhttp.Event):
            for event in self.on_websocket_connection_event_cache:
                if event.self_id == event.self_id and event.time == event.time:
                    return

            self.on_websocket_connection_event_cache.append(event)
            await self.logger.info(f'WebSocket connection established, bot id: {event.self_id}')

        self.bot.on_websocket_connection(on_websocket_connection)

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    async def run_async(self):
        await self.bot._server_app.run_task(**self.config)

    async def kill(self) -> bool:
        # Current issue: existing connection will not be closed
        # self.should_shutdown = True
        return False
