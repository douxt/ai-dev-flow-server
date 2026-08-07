"""检索服务 — RRF 混合搜索 + 时间线查询，薄封装 store.KBStore."""
from store import KBStore


class RetrievalService:
    def __init__(self, store: KBStore, timeline_max_chars: int = 2000, history_count: int = 20):
        self.store = store
        self.timeline_max_chars = timeline_max_chars
        self.history_count = history_count

    async def search_history(self, queries: list[str], session_name: str = '',
                             top_k: int = 10, sender_name: str = '', days: int = 0) -> list[dict]:
        return await self.store.search_history(queries, session_name, top_k,
                                                sender_name=sender_name, days=days)

    async def get_recent_messages(self, session_name: str, limit: int | None = None) -> list[dict]:
        return await self.store.get_recent_messages(session_name, limit or 200)
