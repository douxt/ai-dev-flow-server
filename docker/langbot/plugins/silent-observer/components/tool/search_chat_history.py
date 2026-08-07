from __future__ import annotations

import asyncio, json, logging, time
from typing import Any

from langbot_plugin.api.definition.components.tool.tool import Tool
from langbot_plugin.api.entities.builtin.provider import session as provider_session

from store import KBStore

logger = logging.getLogger(__name__)
_DB_PATH = '/app/data/plugins/dou__langbot-silent-observer/chat_index.db'
_API_TIMEOUT = 30


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

        store = KBStore(self.plugin, kb_id, embedding_model_uuid, _DB_PATH)

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

        lt = session.launcher_type
        if hasattr(lt, 'value'):
            lt = lt.value
        session_id = f'{lt}_{session.launcher_id}'

        try:
            with open('/tmp/silent_tool_calls.log', 'a') as f:
                from datetime import datetime, timezone, timedelta
                now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{now}] query={query[:80]} session={session_id} sender={sender_name} days={days}\n")
        except:
            pass

        logger.info(
            "[silent] search_chat_history: query_id=%s session=%s query=%s sender=%s days=%s",
            query_id, session_id, query[:80], sender_name, days,
        )

        # RRF 混合搜索（Vector + Keyword）
        try:
            raw = await asyncio.wait_for(
                store.search_history(
                    [query.strip()], session_name=session_id, top_k=top_k,
                    sender_name=sender_name, days=days or 0,
                ),
                timeout=_API_TIMEOUT,
            )
        except Exception as e:
            logger.error("[silent] search_chat_history RRF error: %s", e)
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
        try:
            with open('/tmp/silent_tool_calls.log', 'a') as f:
                f.write(f"  -> {len(lines)} results\n")
        except:
            pass
        return '\n'.join(lines)
