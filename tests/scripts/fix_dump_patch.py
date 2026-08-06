#!/usr/bin/env python3
"""Fix litellmchat.py dump — remove broken traceback reference."""
path = "/app/src/langbot/pkg/provider/modelmgr/requesters/litellmchat.py"
with open(path) as f:
    content = f.read()

# 1. Fix import line (remove broken alias)
old_import = "import json as _json, traceback as _tb"
new_import = "import json as _json"
if old_import in content:
    content = content.replace(old_import, new_import)
    print("FIXED import")

# 2. Fix except block (remove traceback reference)
old_except = "_f.write(f'ERR1 {_e}\\n{traceback.format_exc()}')"
new_except = "_f.write(f'ERR1 {_e}')"
if old_except in content:
    content = content.replace(old_except, new_except)
    print("FIXED except")
else:
    print("NOT FOUND except block")
    for i, line in enumerate(content.split('\n')):
        if 'ERR1' in line:
            print(f"  {i}: {line.strip()[:200]}")

with open(path, 'w') as f:
    f.write(content)
print("DONE")
