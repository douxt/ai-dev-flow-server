import sys, asyncio, inspect, traceback
sys.path.insert(0, '/app/data/plugins/dou__langbot-silent-observer')

# STEP1: import
try:
    from components.event_listener.default import DefaultEventListener
    print('STEP1: import OK')
except Exception as e:
    print(f'STEP1: import FAILED: {e}')
    traceback.print_exc()
    sys.exit(1)

# STEP2: check initialize source
try:
    src = inspect.getsource(DefaultEventListener.initialize)
    print(f'STEP2: initialize source {len(src)} chars')
except Exception as e:
    print(f'STEP2: {e}')

# STEP3: check _migrate_buffer_if_needed
try:
    src = inspect.getsource(DefaultEventListener._migrate_buffer_if_needed)
    print(f'STEP3: _migrate_buffer_if_needed source {len(src)} chars')
except Exception as e:
    print(f'STEP3: {e}')

# STEP4: check tool
try:
    from components.tool.search_chat_history import SearchChatHistory
    print('STEP4: tool import OK')
except Exception as e:
    print(f'STEP4: tool import FAILED: {e}')

print('ALL CHECKS DONE')
