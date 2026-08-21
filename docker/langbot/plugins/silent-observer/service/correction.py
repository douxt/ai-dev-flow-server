"""纠正信号检测 — 两阶段：关键词初筛 + LLM 确认."""
import asyncio
import re
from dataclasses import dataclass, field

from util.logs import safe_log

_LLM_CONFIRM_TIMEOUT = 15
_BASE_WINDOW = 30  # 基础阅读窗口秒
_CHARS_PER_SEC = 10  # 估算阅读速率：10字/秒


@dataclass
class CorrectionSignal:
    session_name: str
    user_text: str
    bot_last_reply: str
    raw_user_text: str = ""  # 重写前原文（日志审计，防 LLM 幻觉扩写）
    error_type: str = ""
    confidence: float = 0.0
    source_msg_id: str = ""
    context_messages: list[dict] = field(default_factory=list)


class CorrectionDetector:
    """两阶段检测：关键词初筛（零成本）→ LLM 确认（高精度）."""

    # 阶段1：关键词初筛
    DIRECT_KEYWORDS = [
        "不对", "错了", "不是这样", "你说错了", "错了吧",
        "根本不是", "搞错了", "你想错了", "你说得不对",
        "不准确", "不完全对", "你理解错了", "没搞对",
        "你确定", "你再想想", "你查一下", "你核实一下",
    ]
    ACTION_KEYWORDS = ["撤回", "纠正", "更正", "重说"]
    CONTEXTUAL_PATTERN = re.compile(
        r"(不对|错了|不是|没有|错了吧).{0,30}(是|应该|实际|正确|其实是)",
        re.DOTALL,
    )

    # 阶段2：LLM 确认 prompt
    CONFIRM_PROMPT = """判断以下群聊消息是否在纠正 bot 的上一次回答错误。仅回答 YES 或 NO。

Bot 上次回复: {bot_reply}

用户消息: {user_msg}

用户是否在指出 bot 的回答有误？（YES/NO）"""

    # 话语重写 prompt：补全省略/指代（省略句"不对，你搞错了"无指代，直接判断漏检 ~95%）
    REWRITE_PROMPT = """以下是 bot 的回复和用户对它的反应。
若用户消息省略了内容或用代词指代，请补全为完整的纠正句。
若无省略（本身就是完整句），原样返回。

Bot 回复: {bot_reply}
用户消息: {user_msg}

只输出补全后的用户消息本身，不要解释。"""

    def __init__(self, plugin, bot_qq: str = "", llm_model_uuid: str = ""):
        self._plugin = plugin
        self.bot_qq = bot_qq
        self._llm_model_uuid = llm_model_uuid

    def _dynamic_window(self, bot_reply_text: str) -> int:
        """基于回复长度估算阅读+反应时间：base=30s + 每100字10s，上限120s."""
        if not bot_reply_text:
            return _BASE_WINDOW
        chars = len(bot_reply_text)
        return min(_BASE_WINDOW + int(chars / _CHARS_PER_SEC), 120)

    def _stage1_keyword(self, user_text: str) -> tuple[bool, float]:
        """关键词初筛。返回 (matched, confidence)."""
        if not user_text:
            return False, 0.0
        for kw in self.DIRECT_KEYWORDS:
            if kw in user_text:
                return True, 0.9
        for kw in self.ACTION_KEYWORDS:
            if kw in user_text:
                return True, 0.7
        if self.CONTEXTUAL_PATTERN.search(user_text):
            return True, 0.7
        return False, 0.0

    async def _stage2_confirm(self, user_text: str, bot_reply: str, confidence: float = 0.0) -> bool:
        """LLM 确认——过滤日常否定（如"不对，你说的那个是旧版本"这类对第三方说的话）."""
        prompt = self.CONFIRM_PROMPT.format(
            bot_reply=bot_reply[:500],
            user_msg=user_text[:300],
        )
        try:
            from langbot_plugin.api.entities.builtin.provider.message import Message
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid=self._llm_model_uuid,
                    messages=[Message(role='user', content=prompt)],
                ),
                timeout=_LLM_CONFIRM_TIMEOUT,
            )
            text = self._extract_llm_text(resp)
            return text.strip().upper().startswith('YES')
        except Exception as e:
            safe_log('reflection', f'stage2 confirm error: {e}')
            # 降级：LLM 不可用时信任高置信度关键词（0.9 直击词），否则丢弃
            return confidence >= 0.9

    async def _rewrite_utterance(self, user_text: str, bot_reply: str) -> str:
        """LLM 补全省略/指代。失败/空串/变短 → 原样返回（防幻觉截断）."""
        prompt = self.REWRITE_PROMPT.format(
            bot_reply=bot_reply[:500],
            user_msg=user_text[:300],
        )
        try:
            from langbot_plugin.api.entities.builtin.provider.message import Message
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid=self._llm_model_uuid,
                    messages=[Message(role='user', content=prompt)],
                ),
                timeout=_LLM_CONFIRM_TIMEOUT,
            )
            text = self._extract_llm_text(resp).strip()
            if text and len(text) >= len(user_text):
                safe_log('reflection', f'rewrite: "{user_text[:30]}" → "{text[:60]}"')
                return text
            safe_log('reflection', f'rewrite: invalid result, keep original: "{user_text[:30]}"')
            return user_text
        except Exception as e:
            safe_log('reflection', f'rewrite error: {e}')
            return user_text

    @staticmethod
    def _extract_llm_text(resp) -> str:
        """从 invoke_llm 返回中提取文本（兼容多种返回格式）."""
        if isinstance(resp, str):
            return resp
        if isinstance(resp, dict):
            return resp.get('content', '') or resp.get('text', '') or str(resp)
        if hasattr(resp, 'content'):
            return resp.content or ''
        if hasattr(resp, 'text'):
            return resp.text or ''
        return str(resp)

    async def detect(
        self,
        session_name: str,
        user_text: str,
        bot_last_reply: str,
        recent_messages: list[dict],
    ) -> CorrectionSignal | None:
        """主检测入口：两阶段管道."""
        if not user_text or not bot_last_reply:
            return None

        # 阶段1：关键词初筛
        matched, confidence = self._stage1_keyword(user_text)
        if not matched:
            return None

        # 阶段2：先重写补全省略/指代，再 LLM 确认（stage1 命中即重写）
        rewritten = await self._rewrite_utterance(user_text, bot_last_reply)
        is_correction = await self._stage2_confirm(rewritten, bot_last_reply, confidence)
        # 降级链：重写句被拒 → 原文再试一次（仅重写有变化时，一次额外调用）
        if not is_correction and rewritten != user_text:
            is_correction = await self._stage2_confirm(user_text, bot_last_reply, confidence)
        if not is_correction:
            safe_log('reflection', f'stage2 filtered: "{user_text[:60]}"')
            return None

        signal_text = rewritten or user_text
        return CorrectionSignal(
            session_name=session_name,
            user_text=signal_text,
            raw_user_text=user_text,
            bot_last_reply=bot_last_reply,
            confidence=confidence,
            context_messages=recent_messages[-5:] if recent_messages else [],
        )
