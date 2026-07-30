"""反思生成与注入 — 独立 LLM 生成结构化反思 + 模板化注入防 prompt injection."""
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta

from service.correction import CorrectionSignal
from util.logs import safe_log

BJT = timezone(timedelta(hours=8))
_LLM_TIMEOUT = 60

ERROR_TYPES = [
    "假设过多", "信息滞后", "答非所问", "事实错误", "理解偏差",
    "过度泛化", "遗漏关键", "逻辑错误", "指令偏离",
]

GENERATE_PROMPT = """你是一个反思记录生成器。根据以下用户纠正，生成一条结构化反思记录。

用户纠正: {correction_text}
Bot 上次回复: {bot_reply}

请输出 JSON（不要 markdown 代码块）:
{{
  "scenario": "群聊中的情景描述（1-2句话）",
  "error_type": "错误类型，从以下选择：{error_types}",
  "mistake": "bot 具体做错了什么",
  "correct_approach": "正确做法是什么（必须具体可执行，至少20字）",
  "how_to_avoid": "未来如何避免（至少10字）",
  "verifiable_test": "如何检验下次是否改对了（至少10字）",
  "domain": "话题领域（如 electrical/software/mechanical/general）",
  "entities": ["核心概念1", "核心概念2"],
  "trigger_keywords": ["触发关键词1", "触发关键词2"]
}}

要求：
- correct_approach 必须包含具体的步骤或判断条件
- verifiable_test 必须是可以事后检验的标准
- 不要输出"下次注意"这种模糊建议"""

# ⚠️ 模板化注入——字段填充，不拼接原始反思文本（防 prompt injection）
INJECT_TEMPLATE = """[先前经验]
场景：{scenario}
曾犯错误：{mistake}
正确做法：{correct_approach}
{confidence_note}"""


class ReflectionGenerator:
    """使用独立 LLM 生成结构化反思."""

    def __init__(self, plugin, ref_llm_model_uuid: str):
        self._plugin = plugin
        self.ref_llm_model_uuid = ref_llm_model_uuid

    async def generate(self, signal: CorrectionSignal) -> dict | None:
        """生成反思，返回结构化 dict 或 None（生成失败/验证不通过）."""
        prompt = GENERATE_PROMPT.format(
            correction_text=signal.user_text[:800],
            bot_reply=signal.bot_last_reply[:500],
            error_types=", ".join(ERROR_TYPES),
        )
        try:
            from langbot_plugin.api.entities.builtin.provider.message import Message
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid=self.ref_llm_model_uuid,
                    messages=[Message(role='user', content=prompt)],
                ),
                timeout=_LLM_TIMEOUT,
            )
            raw_text = self._extract_llm_text(resp)
            reflection = self._parse_json(raw_text)
            if not reflection:
                safe_log('reflection', 'generate: JSON parse failed')
                return None
            if not self.validate_schema(reflection):
                safe_log('reflection', 'generate: schema validation failed')
                return None
            return self._enrich(reflection, signal)
        except asyncio.TimeoutError:
            safe_log('reflection', 'generate: LLM timeout')
            return None
        except Exception as e:
            safe_log('reflection', f'generate error: {type(e).__name__}: {str(e)[:120]}')
            return None

    def validate_schema(self, reflection: dict) -> bool:
        """验证必须字段完整且满足最低质量标准."""
        required = ["scenario", "error_type", "mistake", "correct_approach", "verifiable_test"]
        for field in required:
            val = reflection.get(field, '')
            if not val or not isinstance(val, str) or not val.strip():
                return False
        if len(reflection.get("correct_approach", "").strip()) < 20:
            return False
        if len(reflection.get("verifiable_test", "").strip()) < 10:
            return False
        if reflection.get("error_type", "") not in ERROR_TYPES:
            return False
        return True

    @staticmethod
    def _extract_llm_text(resp) -> str:
        if isinstance(resp, str):
            return resp
        if isinstance(resp, dict):
            return resp.get('content', '') or resp.get('text', '') or str(resp)
        if hasattr(resp, 'content'):
            return resp.content or ''
        if hasattr(resp, 'text'):
            return resp.text or ''
        return str(resp)

    @staticmethod
    def _parse_json(raw: str) -> dict | None:
        """从 LLM 回复中提取 JSON，兼容 markdown 代码块包裹."""
        if not raw:
            return None
        # 尝试提取 ```json ... ``` 或 ``` ... ```
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
        if m:
            raw = m.group(1)
        # 尝试提取 { ... }
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            raw = m.group(0)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _enrich(raw: dict, signal: CorrectionSignal) -> dict:
        """补充系统字段."""
        raw["confirm_count"] = 1
        raw["importance"] = "low"
        raw["source_msg_ids"] = [signal.source_msg_id] if signal.source_msg_id else []
        raw["timestamp"] = datetime.now(BJT).isoformat()
        raw["last_hit"] = None
        raw["archived"] = False
        raw.setdefault("domain", "general")
        raw.setdefault("entities", [])
        raw.setdefault("trigger_keywords", [])
        raw.setdefault("confirm_sources", [])
        return raw


class ReflectionInjector:
    """模板化反思注入——防 prompt injection."""

    @staticmethod
    def build_reflection_prompt(reflections: list[dict]) -> str | None:
        """构建反思注入段。模板化填充，不拼接原始 LLM 输出."""
        if not reflections:
            return None
        lines = []
        for ref in reflections:
            meta = ref.get('metadata', {}) if isinstance(ref, dict) else ref
            confirm = meta.get('confirm_count', 1)
            confidence_note = ""
            if confirm < 3:
                confidence_note = "(此经验尚未充分确认，仅供参考)"
            lines.append(INJECT_TEMPLATE.format(
                scenario=meta.get('scenario', '未知场景'),
                mistake=meta.get('mistake', ''),
                correct_approach=meta.get('correct_approach', ''),
                confidence_note=confidence_note,
            ))
        return "\n".join(lines)
