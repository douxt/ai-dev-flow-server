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

        try:
            results = await api.retrieve_knowledge(
                kb_id=kb_id,
                query_text=query.strip(),
                top_k=top_k,
                filters={"$and": filters},
            )
        except Exception as e:
            logger.error("[silent] search_chat_history error: %s", e)
            return f"Error: retrieval failed: {e}"

        if not results:
            return "No matching chat history found."

        lines = []
        for r in results:
            content_parts = []
            for ce in r.get('content', []):
                if isinstance(ce, dict) and ce.get('type') == 'text':
                    content_parts.append(ce.get('text', ''))
            text = ' '.join(content_parts)
            if text:
                meta = r.get('metadata', {})
                ts = meta.get('timestamp', '?')
                sn = meta.get('sender_name', '?')
                lines.append(f"[{ts}] {sn}: {text}")

        logger.info(
            "[silent] search_chat_history done: query_id=%s result_count=%s",
            query_id, len(lines),
        )
        return '\n'.join(lines)
