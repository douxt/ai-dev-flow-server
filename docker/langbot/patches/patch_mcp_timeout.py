#!/usr/bin/env python3
"""Monkey-patch LangBot mcp.py: wrap call_tool with asyncio.timeout(30s)"""
import re
import sys

MCP_FILE = '/app/src/langbot/pkg/provider/tools/loaders/mcp.py'
MARKER = '[MCP-TIMEOUT-PATCH]'

with open(MCP_FILE) as f:
    content = f.read()

if MARKER in content:
    print(f'{MARKER} already applied, skip')
    sys.exit(0)

# 精准替换
old = '        result = await self.session.call_tool(tool_name, arguments)'
new = '''        # [MCP-TIMEOUT-PATCH] 30s hard timeout to prevent session hang
        try:
            async with asyncio.timeout(30):
                result = await self.session.call_tool(tool_name, arguments)
        except TimeoutError:
            raise Exception(f'MCP tool {tool_name} timed out after 30s')'''

if old not in content:
    print(f'{MARKER} ERROR: target line not found in {MCP_FILE}')
    sys.exit(1)

new_content = content.replace(old, new, 1)
with open(MCP_FILE, 'w') as f:
    f.write(new_content)

print(f'{MARKER} applied successfully')
