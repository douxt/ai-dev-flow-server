from __future__ import annotations

from . import handler
from .handlers import chat, command
from .. import entities
from .. import stage
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
import asyncio


@stage.stage_class('MessageProcessor')
class Processor(stage.PipelineStage):
    """请求实际处理阶段

    通过命令处理器和聊天处理器处理消息。

    改写：
        - resp_messages
    """

    cmd_handler: handler.MessageHandler

    chat_handler: handler.MessageHandler

    async def initialize(self, pipeline_config: dict):
        self.cmd_handler = command.CommandHandler(self.ap)
        self.chat_handler = chat.ChatMessageHandler(self.ap)

        await self.cmd_handler.initialize()
        await self.chat_handler.initialize()

    async def process(
        self,
        query: pipeline_query.Query,
        stage_inst_name: str,
    ) -> entities.StageProcessResult:
        """Process"""
        # PATCH: str() on huge message chains (e.g. forwarded chat logs) can
        # block the event loop for >60s, causing websockets keepalive ping
        # timeout. Run the string conversion in a thread executor to keep the
        # event loop free.
        # Upstream issue: https://github.com/langbot-app/langbot/issues/...
        loop = asyncio.get_running_loop()
        message_text = (await loop.run_in_executor(
            None, lambda: str(query.message_chain).strip()
        ))[:500]

        self.ap.logger.info(
            f'Processing request from {query.launcher_type.value}_{query.launcher_id} ({query.query_id}): {message_text}'
        )

        async def generator():
            cmd_prefix = self.ap.instance_config.data['command']['prefix']
            cmd_enable = self.ap.instance_config.data['command'].get('enable', True)

            if cmd_enable and any(message_text.startswith(prefix) for prefix in cmd_prefix):
                handler_to_use = self.cmd_handler
            else:
                handler_to_use = self.chat_handler

            async for result in handler_to_use.handle(query):
                yield result

        return generator()
