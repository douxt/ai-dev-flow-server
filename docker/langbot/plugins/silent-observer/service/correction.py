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

    def __init__(self, plugin, bot_qq: str = ""):
        self._plugin = plugin
        self.bot_qq = bot_qq

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

    async def _stage2_confirm(self, user_text: str, bot_reply: str) -> bool:
        """LLM 确认——过滤日常否定（如"不对，你说的那个是旧版本"这类对第三方说的话）."""
        prompt = self.CONFIRM_PROMPT.format(
            bot_reply=bot_reply[:500],
            user_msg=user_text[:300],
        )
        try:
            from langbot_plugin.api.entities.builtin.provider.message import Message
            resp = await asyncio.wait_for(
                self._plugin.invoke_llm(
                    llm_model_uuid="",  # 空字符串 = 使用 pipeline 默认模型
                    messages=[Message(role='user', content=prompt)],
                ),
                timeout=_LLM_CONFIRM_TIMEOUT,
            )
            text = self._extract_llm_text(resp)
            return text.strip().upper().startswith('YES')
        except Exception as e:
            safe_log('reflection', f'stage2 confirm error: {e}')
            # 降级：LLM 不可用时信任关键词（高置信度才过）
            return False

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

        # 阶段2：LLM 确认
        is_correction = await self._stage2_confirm(user_text, bot_last_reply)
        if not is_correction:
            safe_log('reflection', f'stage2 filtered: "{user_text[:60]}"')
            return None

        return CorrectionSignal(
            session_name=session_name,
            user_text=user_text,
            bot_last_reply=bot_last_reply,
            confidence=confidence,
            context_messages=recent_messages[-5:] if recent_messages else [],
        )
