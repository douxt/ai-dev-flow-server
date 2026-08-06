"""QQ 表情处理 — face_id→中文名映射 + 消息链 Face 组件识别与替换."""
from langbot_plugin.api.entities.builtin.platform.message import Plain as PlatformPlain

# QQ 经典黄脸表情 face_id → 中文名，napcat 偶尔不提供 face_name 时的 fallback
QQ_FACE_NAME = {
    0:'微笑',1:'撇嘴',2:'色',3:'发呆',4:'得意',5:'流泪',6:'害羞',7:'闭嘴',8:'睡',9:'大哭',
    10:'尴尬',11:'发怒',12:'调皮',13:'呲牙',14:'惊讶',15:'难过',16:'酷',18:'偷笑',19:'可爱',
    20:'白眼',21:'傲慢',22:'饥饿',23:'困',24:'惊恐',25:'流汗',26:'憨笑',27:'大兵',28:'奋斗',
    29:'咒骂',30:'疑问',31:'嘘',32:'晕',33:'折磨',34:'衰',35:'骷髅',36:'敲打',37:'再见',
    38:'擦汗',39:'抠鼻',40:'鼓掌',41:'糗大了',42:'坏笑',43:'左哼哼',44:'右哼哼',45:'哈欠',
    46:'鄙视',47:'委屈',48:'快哭了',49:'阴险',50:'亲亲',51:'吓',52:'可怜',53:'菜刀',54:'西瓜',
    55:'啤酒',56:'篮球',57:'乒乓',58:'咖啡',59:'饭',60:'猪头',61:'玫瑰',62:'凋谢',63:'示爱',
    64:'爱心',65:'心碎',66:'蛋糕',67:'闪电',68:'炸弹',69:'刀',70:'足球',71:'瓢虫',72:'便便',
    73:'月亮',74:'太阳',75:'礼物',76:'拥抱',77:'强',78:'弱',79:'握手',80:'胜利',81:'抱拳',
    82:'勾引',83:'拳头',84:'差劲',85:'爱你',86:'NO',87:'OK',88:'爱情',89:'飞吻',90:'跳跳',
    91:'发抖',92:'怄火',93:'转圈',94:'磕头',95:'回头',96:'跳绳',97:'挥手',98:'激动',99:'街舞',
    100:'献吻',101:'左太极',102:'右太极',103:'双喜',104:'鞭炮',105:'灯笼',106:'发财',107:'K歌',
    108:'购物',109:'邮件',110:'帅',111:'喝彩',112:'祈祷',113:'爆筋',114:'棒棒糖',115:'喝奶',
    116:'下面',117:'香蕉',118:'飞机',119:'开车',120:'高铁左车头',121:'车厢',122:'高铁右车头',
    123:'多云',124:'下雨',125:'钞票',126:'熊猫',127:'灯泡',128:'风车',129:'闹钟',130:'打伞',
    131:'彩球',132:'钻戒',133:'沙发',134:'纸巾',135:'药',136:'手枪',137:'青蛙',
    # napcat 常见但有 face_name 的高频 ID，以防万一
    178:'斜眼笑',264:'捂脸',
}


def is_face_component(c) -> bool:
    """判断组件是否为 QQ 表情（兼容 Unknown 降级 + hasattr face_id）"""
    if c.type == 'Face':
        return True
    if hasattr(c, 'face_id'):
        return True
    # Fallback: LangBot monkey-patch 失效时 Face 降级为 Unknown
    if c.type == 'Unknown' and hasattr(c, 'text'):
        return 'Unknown component type: Face' in (c.text or '')
    return False


def face_to_text(c) -> str:
    """Face/Unknown 组件 → Plain 文本"""
    # 正常 Face 组件
    name = getattr(c, 'face_name', '') or QQ_FACE_NAME.get(getattr(c, 'face_id', 0), '')
    if name:
        return f'[QQ表情:{name}]'
    face_id = getattr(c, 'face_id', None)
    if face_id is not None:
        return f'[QQ表情:{face_id}]'
    # Unknown 降级：face_id 已丢失，只能标为表情
    return '[QQ表情]'


def extract_faces(message_chain) -> str:
    """从 message_chain 提取所有 Face 文本，逗号分隔"""
    if not message_chain:
        return ''
    texts = []
    for c in message_chain:
        if is_face_component(c):
            texts.append(face_to_text(c))
    return ', '.join(texts) if texts else ''


def normalize_face_components(message_chain) -> None:
    """原地替换 message_chain 中的 Face 组件为 Plain（递归处理 Quote.origin）"""
    if message_chain is None:
        return
    for i, c in enumerate(message_chain):
        if is_face_component(c):
            text = face_to_text(c)
            message_chain[i] = PlatformPlain(text=text)
        elif c.type == 'Quote':
            origin = getattr(c, 'origin', None)
            if origin is not None:
                normalize_face_components(origin)
