"""共享 fixtures：SDK mock 树 + Fake 消息组件 + DefaultEventListener 实例"""
import sys, types
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace

import pytest

# ============================================================
# Fake 消息组件（鸭子类型，模拟 LangBot message_chain 组件）
# ============================================================

class FakePlain(SimpleNamespace):
    def __init__(self, text=''): super().__init__(type='Plain', text=text)

class FakeAt(SimpleNamespace):
    def __init__(self, target='123', display=None):
        super().__init__(type='At', target=target, display=display)

class FakeFace(SimpleNamespace):
    def __init__(self, face_id=0, face_name=''):
        super().__init__(type='Face', face_id=face_id, face_name=face_name)

class FakeUnknown(SimpleNamespace):
    """napcat 偶发将 Face 降级为 Unknown 类型（仍有 face_id 属性）"""
    def __init__(self, face_id=0, face_name=''):
        super().__init__(type='Unknown', face_id=face_id, face_name=face_name)

class FakeImage(SimpleNamespace):
    def __init__(self, url='https://x.com/i.png', base64=''):
        super().__init__(type='Image', url=url, base64=base64)

class FakeQuote(SimpleNamespace):
    def __init__(self, origin=None):
        super().__init__(type='Quote', origin=origin)

class FakeForward(SimpleNamespace):
    def __init__(self, node_list=None):
        super().__init__(type='Forward', node_list=node_list or [])

class FakeForwardNode(SimpleNamespace):
    def __init__(self, message_chain=None, sender_name='', sender_id='', user_id=''):
        super().__init__(message_chain=message_chain, sender_name=sender_name,
                         sender_id=sender_id, user_id=user_id)

# ============================================================
# langbot_plugin SDK mock 树
# ============================================================

def _build_sdk_mock():
    """构建 langbot_plugin.api 的 mock 模块树。只覆盖 default.py 实际导入的路径。"""
    MockEventListener = type('EventListener', (), {
        'initialize': AsyncMock(),
        'handler': MagicMock(return_value=lambda f: f),
    })

    MockMessageChain = MagicMock()
    MockMessageChain._get_component_types = MagicMock()
    MockMessageChain._get_component_types.__func__ = MagicMock(return_value={})

    MockLangBotFace = type('LangBotFace', (), {})

    def _pkg(name, **attrs):
        """创建 package（含 __path__），支持 from-import 链"""
        m = types.ModuleType(name)
        m.__path__ = []
        m.__package__ = name
        for k, v in attrs.items():
            setattr(m, k, v)
        return m

    # langbot_plugin.api.entities.builtin.platform.message
    platform_msg = _pkg('langbot_plugin.api.entities.builtin.platform.message',
        Plain=type('Plain', (SimpleNamespace,), {}),
        MessageChain=MockMessageChain,
        Face=MockLangBotFace)

    # langbot_plugin.api.entities.builtin.provider.message
    provider_msg = _pkg('langbot_plugin.api.entities.builtin.provider.message',
        Message=SimpleNamespace,
        ContentElement=SimpleNamespace)

    # langbot_plugin.api.entities.builtin.platform
    platform = _pkg('langbot_plugin.api.entities.builtin.platform', message=platform_msg)

    # langbot_plugin.api.entities.builtin.provider
    provider_pkg = _pkg('langbot_plugin.api.entities.builtin.provider', message=provider_msg)

    # langbot_plugin.api.entities.builtin
    builtin = _pkg('langbot_plugin.api.entities.builtin', platform=platform, provider=provider_pkg)

    # langbot_plugin.api.entities
    entities = _pkg('langbot_plugin.api.entities',
        events=SimpleNamespace(GroupMessageReceived='group_message',
                               NormalMessageResponded='normal_message_responded',
                               PersonNormalMessageReceived='person_normal'),
        context=SimpleNamespace(EventContext=SimpleNamespace),
        builtin=builtin)

    # langbot_plugin.api.proxies.query_based_api
    qapi = _pkg('langbot_plugin.api.proxies.query_based_api',
        QueryBasedAPIProxy=type('QueryBasedAPIProxy', (), {}))

    # langbot_plugin.api.proxies
    proxies = _pkg('langbot_plugin.api.proxies', query_based_api=qapi)

    # langbot_plugin.api.definition.components.common.event_listener
    event_listener = _pkg('langbot_plugin.api.definition.components.common.event_listener',
        EventListener=MockEventListener)

    # langbot_plugin.api.definition.components.common
    common = _pkg('langbot_plugin.api.definition.components.common', event_listener=event_listener)

    # langbot_plugin.api.definition.components
    components = _pkg('langbot_plugin.api.definition.components', common=common)

    # langbot_plugin.api.definition.plugin
    plugin_mod = _pkg('langbot_plugin.api.definition.plugin',
        BasePlugin=type('BasePlugin', (), {
            'initialize': AsyncMock(), 'dispose': AsyncMock(),
            'get_config': MagicMock(return_value={}),
            'list_llm_models': AsyncMock(return_value=[]),
        }))

    # langbot_plugin.api.definition
    definition = _pkg('langbot_plugin.api.definition',
        components=components, plugin=plugin_mod)

    # langbot_plugin.api
    api = _pkg('langbot_plugin.api',
        entities=entities, definition=definition, proxies=proxies)

    # langbot_plugin (root)
    root = _pkg('langbot_plugin', api=api)

    return root


@pytest.fixture(autouse=True)
def patch_sdk():
    """每个测试前注入 mock langbot_plugin 到 sys.modules"""
    mock_root = _build_sdk_mock()

    def register(m, prefix=''):
        """递归注册模块树中的所有子模块到 sys.modules"""
        name = getattr(m, '__package__', '') or getattr(m, '__name__', '')
        if name:
            sys.modules[name] = m
        for k in dir(m):
            if k.startswith('_'):
                continue
            v = getattr(m, k)
            if isinstance(v, types.ModuleType):
                register(v)

    register(mock_root)
    # 确保顶级 langbot_plugin 也被注册
    sys.modules['langbot_plugin'] = mock_root

    yield
    # 清理所有 mock 模块
    to_pop = [k for k in sys.modules if k.startswith('langbot_plugin')]
    for k in to_pop:
        sys.modules.pop(k, None)


@pytest.fixture
def listener(monkeypatch):
    """返回已构造但未 initialize 的 DefaultEventListener 实例"""
    import importlib
    # 重载模块以确保干净的 sys.modules 状态
    if 'components.event_listener.default' in sys.modules:
        del sys.modules['components.event_listener.default']
    # 添加 tests 的父目录到 sys.path
    sys.path.insert(0, '/home/dou/dev/ai-dev-flow-server/.claude/worktrees/test-suite/docker/langbot/plugins/silent-observer')
    from components.event_listener.default import DefaultEventListener
    obj = DefaultEventListener.__new__(DefaultEventListener)
    obj.bot_qq = '3228649756'
    obj.prob = 0.01
    obj.kb_enabled = False
    obj.vision_enabled = False
    obj.vision_daily_limit = 0
    obj._vision_daily_count = 0
    obj._vision_daily_date = None
    obj._vision_fail_streak = 0
    obj._vision_circuit_open_until = None
    obj._vision_stats = {'total': 0, 'success': 0, 'fail': 0, 'total_tokens': 0}
    obj._bg_queue = None
    obj._bg_workers = []
    obj._last_trigger = {}
    obj._lock_set_ts = {}
    obj._reply_ts = {}
    obj._reply_pending = {}
    obj._reply_tasks = {}
    obj._face_cache = {}
    obj._image_cache = {}
    obj._last_msg_ts = {}
    obj.timeline_max_chars = 2000
    obj.vision_max_images = 5
    obj.history_count = 20
    obj.debug_dump = False
    obj.vision_all_messages = False
    obj._gate_hits = 0
    obj._gate_misses = 0
    obj._lock_skips = 0
    obj._inject_random = 0
    obj._inject_at = 0
    obj._stats_start = 0
    return obj
