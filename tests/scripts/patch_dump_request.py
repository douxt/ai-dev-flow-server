#!/usr/bin/env python3
"""在 _build_completion_args 开头加请求 dump。"""
import json, traceback

path = "/app/src/langbot/pkg/provider/modelmgr/requesters/litellmchat.py"
with open(path) as f:
    content = f.read()

old = """    async def _build_completion_args(
        self,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        stream: bool = False,
    ) -> dict:
        \"\"\"Build common completion arguments for invoke_llm and invoke_llm_stream.\"\"\"
        req_messages = self._convert_messages(messages)"""

new = """    async def _build_completion_args(
        self,
        model: requester.RuntimeLLMModel,
        messages: typing.List[provider_message.Message],
        funcs: typing.List[resource_tool.LLMTool] = None,
        extra_args: dict[str, typing.Any] = {},
        stream: bool = False,
    ) -> dict:
        \"\"\"Build common completion arguments for invoke_llm and invoke_llm_stream.\"\"\"
        # PATCH: dump full LLM request to /tmp/llm_full_request.json
        try:
            _dump = {
                'model': model.model_entity.name if hasattr(model, 'model_entity') else str(model),
                'n_messages': len(messages),
                'n_funcs': len(funcs) if funcs else 0,
                'stream': stream,
                'messages': [],
                'func_names': [str(getattr(f, 'name', '?')) for f in (funcs or [])],
            }
            for _m in messages:
                _c = ''
                if hasattr(_m, 'content'):
                    if isinstance(_m.content, list):
                        _c = ' '.join([str(getattr(c, 'text', c)) for c in _m.content])
                    else:
                        _c = str(_m.content)
                _dump['messages'].append({'role': str(getattr(_m, 'role', '?')), 'len': len(_c), 'content': _c})
            with open('/tmp/llm_full_request.json', 'w') as _f:
                json.dump(_dump, _f, ensure_ascii=False, indent=2)
        except Exception as _e:
            with open('/tmp/llm_dump_err.log', 'w') as _f:
                _f.write(f'ERR1 {_e}\\n{traceback.format_exc()}')
        req_messages = self._convert_messages(messages)"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w') as f:
        f.write(content)
    print('PATCHED')
else:
    print('NOT FOUND')
    for i, line in enumerate(content.split('\n')):
        if '_build_completion_args' in line:
            print(f'  {i}: {line.strip()[:120]}')
