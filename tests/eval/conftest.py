"""DeepEval 共享配置 — Qwen 百炼 Judge."""
import os

from deepeval.models import LiteLLMModel


def get_qwen_judge(model: str = "qwen3-flash") -> LiteLLMModel:
    """百炼 Qwen，OpenAI 兼容模式."""
    return LiteLLMModel(
        model=f"openai/{model}",
        api_base=os.environ.get(
            "DASHSCOPE_API_BASE",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        api_key=os.environ.get("DASHSCOPE_API_KEY", ""),
        generation_kwargs={"temperature": 0.0},
    )
