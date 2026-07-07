from langbot_plugin.api.definition.plugin import BasePlugin

class Plugin(BasePlugin):
    async def initialize(self):
        await super().initialize()

    async def dispose(self):
        await super().dispose()
