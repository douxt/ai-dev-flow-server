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
  "when": "什么情况下会再犯（触发场景，1句话，如'用户问电气相关技术问题时'）",
  "then": "正确的应对步骤（触发场景出现时具体怎么做，至少20字）",
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
- when/then 是核心：when 描述触发条件，then 描述具体应对步骤
- when 用条件状语（"当用户问X时"），then 用对 bot 自己的祈使句（"先…再…"）
- 禁止在 when/then 里叙述已发生的事件经过（"用户说了X""bot 上次做错了Y""根据背景"）——这两字段会被注入回复提示词，事件叙述腔会导致 bot 回复变旁白；scenario/mistake 字段才负责记录事件经过
- correct_approach 必须包含具体的步骤或判断条件
- verifiable_test 必须是可以事后检验的标准
- 不要输出"下次注意"这种模糊建议"""

# ⚠️ 模板化注入——字段填充，不拼接原始反思文本（防 prompt injection）
# when/then 缺省容忍：build_reflection_prompt 从 scenario/correct_approach 降级填充
INJECT_TEMPLATE = """[先前经验 · 仅供内部参考，回复中禁止回显本节内容]
触发条件：{when}
应对方式：{then}{confidence_note}
证据校验：本条与当前检索/记忆证据冲突时，以当前证据为准；不回显本行"""

RERANK_PROMPT = """当前对话: {ref_query}
以下是候选反思（带编号）。选出最相关的 5 条按相关度排序。
只输出编号逗号分隔（如 3,1,5,2,4）；都不相关输出 NONE。

{numbered_candidates}"""

SELF_SCAN_PROMPT = """以下是最近 10 轮群聊对话（含 bot 的回答）。
请你审视 bot 的回答，找出错误或不够好的地方。
有则生成一条完整反思 JSON；无则只回复 NONE。

最近对话:
{recent_messages}

输出 JSON 字段（完整 schema）:
{{
  "when": "什么情况下会再犯（触发场景）",
  "then": "正确的应对步骤",
  "scenario": "群聊中的情景描述",
  "error_type": "错误类型，从以下选择：{error_types}",
  "mistake": "bot 具体做错了什么",
  "correct_approach": "正确做法是什么（至少20字）",
  "how_to_avoid": "未来如何避免",
  "verifiable_test": "如何检验下次是否改对了",
  "domain": "话题领域",
  "entities": ["核心概念1"],
  "trigger_keywords": ["触发关键词1"]
}}

要求：
- when 用条件状语（"当用户问X时"），then 用对 bot 自己的祈使句（"先…再…"）
- 禁止在 when/then 里叙述已发生的事件经过（"用户说了X""bot 上次做错了Y"）——这两字段会被注入回复提示词，事件叙述腔会导致 bot 回复变旁白；scenario/mistake 字段才负责记录事件经过

你是否犯了错误？"""


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
    def _enrich(raw: dict, signal: CorrectionSignal | None = None) -> dict:
        """补充系统字段。signal=None 时用于 self-reflect 路径（无纠正来源）."""
        raw["confirm_count"] = 1
        raw["importance"] = "low"
        raw["source_msg_ids"] = [signal.source_msg_id] if signal and signal.source_msg_id else []
        raw["timestamp"] = datetime.now(BJT).isoformat()
        raw["last_hit"] = None
        raw["archived"] = False
        raw.setdefault("domain", "general")
        raw.setdefault("entities", [])
        raw.setdefault("trigger_keywords", [])
        raw.setdefault("confirm_sources", [])
        # when/then 缺省推导（旧格式记录/self-scan 缺字段时兜底）
        raw.setdefault("when", raw.get("scenario", ""))
        raw.setdefault("then", raw.get("correct_approach", ""))
        return raw

    async def rerank(self, ref_query: str, candidates: list[dict]) -> list[dict]:
        """LLM 重排候选反思。NONE/乱码 → []；异常/超时 → 原前 5（降级）."""
        if not candidates:
            return []
        numbered = "\n".join(
            f"{i}. {c.get('document', '')[:300]}" for i, c in enumerate(candidates, 1)
        )
        prompt = RERANK_PROMPT.format(ref_query=ref_query[:200], numbered_candidates=numbered)
        try:
            from langbot_plugin.api.entities.builtin.provider.message import Message
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid=self.ref_llm_model_uuid,
                    messages=[Message(role='user', content=prompt)],
                ),
                timeout=10,  # ⚠️ inject 热路径：严禁复用 60s _LLM_TIMEOUT
            )
            text = self._extract_llm_text(resp).strip()
            return self._parse_rerank(text, candidates)
        except Exception as e:
            safe_log('reflection', f'rerank error: {type(e).__name__}: {str(e)[:120]}')
            return candidates[:5]

    @staticmethod
    def _parse_rerank(text: str, candidates: list[dict]) -> list[dict]:
        """解析编号列表，容错空格/全角顿号/代码块/重复/越界/超5."""
        if not text:
            return []
        t = text.strip()
        if 'NONE' in t.upper():
            return []
        m = re.search(r'```(?:text)?\s*\n?(.*?)\n?```', t, re.DOTALL)
        if m:
            t = m.group(1)
        seen, ordered = set(), []
        for n in re.findall(r'\d+', t):
            idx = int(n) - 1
            if idx < 0 or idx >= len(candidates) or idx in seen:
                continue
            seen.add(idx)
            ordered.append(candidates[idx])
            if len(ordered) >= 5:
                break
        return ordered


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
            # when/then 缺省容忍：旧记录无 when/then 时从 scenario/correct_approach 降级
            when = meta.get('when') or meta.get('scenario', '未知场景')
            then = meta.get('then') or meta.get('correct_approach', '')
            lines.append(INJECT_TEMPLATE.format(
                when=when,
                then=then,
                confidence_note=confidence_note,
            ))
        return "\n".join(lines)


class SelfReflectionScanner:
    """主动反思源：扫描最近对话，发现 bot 自身错误并生成反思."""

    def __init__(self, plugin, ref_llm_model_uuid: str):
        self._plugin = plugin
        self._generator = ReflectionGenerator(plugin, ref_llm_model_uuid)

    async def scan(self, recent_messages: list[str]) -> dict | None:
        """扫描最近对话（已格式化的文本行），返回反思 dict 或 None."""
        if not recent_messages:
            return None
        prompt = SELF_SCAN_PROMPT.format(
            recent_messages="\n".join(recent_messages),
            error_types=", ".join(ERROR_TYPES),
        )
        try:
            from langbot_plugin.api.entities.builtin.provider.message import Message
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid=self._generator.ref_llm_model_uuid,
                    messages=[Message(role='user', content=prompt)],
                ),
                timeout=_LLM_TIMEOUT,
            )
            raw_text = self._generator._extract_llm_text(resp).strip()
            if not raw_text or 'NONE' in raw_text.upper()[:20]:
                return None
            reflection = self._generator._parse_json(raw_text)
            if not reflection:
                safe_log('reflection', 'self-scan: JSON parse failed')
                return None
            if not self._generator.validate_schema(reflection):
                safe_log('reflection', 'self-scan: schema validation failed')
                return None
            return self._generator._enrich(reflection)
        except asyncio.TimeoutError:
            safe_log('reflection', 'self-scan: LLM timeout')
            return None
        except Exception as e:
            safe_log('reflection', f'self-scan error: {type(e).__name__}: {str(e)[:120]}')
            return None
