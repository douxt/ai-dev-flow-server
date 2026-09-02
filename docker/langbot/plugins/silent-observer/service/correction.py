"""纠正信号标记 — 实时层零 LLM：关键词初筛判定"长得像纠正"，供批量整合层触发.

2026-09-02 B 线批量化：原两阶段检测（关键词初筛 + LLM 确认）与话语重写整体拆除——
write-time 单轮内容筛选被投毒研究证伪（arXiv 2608.21230：0/360 拦截），真伪裁决
挪至 service/consolidator.py 批量层以完整事件弧进行。本模块只保留零成本判定。
"""
import re


class CorrectionDetector:
    """关键词标记器。命中≠学习，只是"该看看这段对话"的信号."""

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

    def __init__(self, plugin=None, bot_qq: str = "", llm_model_uuid: str = ""):
        # plugin/uuid 参数保留以兼容既有装配签名；标记器不再调用 LLM
        self._plugin = plugin
        self.bot_qq = bot_qq
        self._llm_model_uuid = llm_model_uuid

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

    def precheck(self, user_text: str) -> tuple[bool, float]:
        """实时层唯一入口：零成本判定该消息是否长得像纠正."""
        return self._stage1_keyword(user_text)
