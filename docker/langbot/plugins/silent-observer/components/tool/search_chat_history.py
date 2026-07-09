from __future__ import annotations

import json, logging, time
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.proxies.query_based_api import QueryBasedAPIProxy

logger = logging.getLogger(__name__)


class SearchChatHistory(Tool):
    async def call(
        self,
        params: dict[str, Any],
        session: provider_session.Session,
        query_id: int,
    ) -> str:
        kb_id = self.plugin.config.get('kb_id', '')
        embedding_model_uuid = self.plugin.config.get('embedding_model_uuid', '')
        if not kb_id or not embedding_model_uuid:
            return "Error: kb_id and embedding_model_uuid must be configured in plugin settings."

        api = QueryBasedAPIProxy(
            query_id=query_id,
            plugin_runtime_handler=self.plugin.plugin_runtime_handler,
        )

        query = params.get('query', '')
        if not isinstance(query, str) or not query.strip():
            return "Error: query is required (a non-empty string)."

        top_k = params.get('top_k', 5)
        if not isinstance(top_k, int) or top_k <= 0:
            return "Error: top_k must be a positive integer."

        sender_name = params.get('sender_name', '')
        if sender_name is None:
            sender_name = ''
        if not isinstance(sender_name, str):
            return "Error: sender_name must be a string."

        days = params.get('days')
        if days is not None:
            if not isinstance(days, int) or days <= 0:
                return "Error: days must be a positive integer."

        # 会话隔离：从 session 构造 session_id
        lt = session.launcher_type
        if hasattr(lt, 'value'):
            lt = lt.value
        session_id = f'{lt}_{session.launcher_id}'

        filters: list[dict] = [
            {"session_id": session_id},
            {"type": "chat_history"},
        ]
        if sender_name:
            filters.append({"sender_name": sender_name})
        if days:
            from_time = time.time() - days * 86400
            filters.append({"timestamp_unix": {"$gte": from_time}})

        logger.info(
            "[silent] search_chat_history: query_id=%s session=%s query=%s sender=%s days=%s",
            query_id, session_id, query[:80], sender_name, days,
        )

        # 对标 LTM：invoke_embedding + vector_search 直连 ChromaDB
        try:
            vectors = await self.plugin.invoke_embedding(embedding_model_uuid, [query.strip()])
            qv = vectors[0]
            import math
            norm = math.sqrt(sum(v*v for v in qv))
            if norm > 0:
                qv = [v / norm for v in qv]
            raw = await self.plugin.vector_search(
                collection_id=kb_id,
                query_vector=qv,
                top_k=top_k,
                filters={"$and": filters},
            )
        except Exception as e:
            logger.error("[silent] search_chat_history error: %s", e)
            return f"Error: retrieval failed: {e}"

        if not raw:
            return "No matching chat history found."

        lines = []
        for r in raw:
            meta = r.get('metadata', {})
            ts = meta.get('timestamp', '?')
            sn = meta.get('sender_name', '?')
            doc_text = meta.get('text', '') or r.get('document', '')
            if doc_text:
                lines.append(f"[{ts}] {sn}: {doc_text}")

        logger.info(
            "[silent] search_chat_history done: query_id=%s result_count=%s",
            query_id, len(lines),
        )
        return '\n'.join(lines)
