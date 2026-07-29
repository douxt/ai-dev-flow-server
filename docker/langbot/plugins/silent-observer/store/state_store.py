"""状态持久化 — 单键 JSON + asyncio.Lock，参考 DailyLimitPlugin 模式."""
import asyncio
import json


class StateStore:
    def __init__(self, plugin, key: str = "silent_observer_state"):
        self.plugin = plugin
        self.key = key
        self.lock = asyncio.Lock()

    async def save(self, state: dict) -> None:
        """序列化并写入 plugin storage。调用方负责保证 state 可 JSON 序列化。"""
        async with self.lock:
            data = json.dumps(state, ensure_ascii=False).encode("utf-8")
            await self.plugin.set_plugin_storage(self.key, data)

    async def load(self) -> dict | None:
        """读取并反序列化。损坏/缺失返回 None。"""
        async with self.lock:
            try:
                raw = await self.plugin.get_plugin_storage(self.key)
                if raw:
                    return json.loads(raw.decode("utf-8"))
            except Exception:
                pass
        return None
