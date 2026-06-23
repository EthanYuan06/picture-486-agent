"""
RAG提示词模块
导出意图识别、查询重写和应答生成的提示词函数
"""

from app.agent.rag.prompts.intent_prompt import get_intent_recognition_prompt
from app.agent.rag.prompts.query_rewrite_prompt import (
    get_image_rewrite_prompt,
    get_text_rewrite_prompt
)
from app.agent.rag.prompts.response_prompt import (
    get_response_generation_prompt,
    get_no_result_response,
    get_fallback_response
)

__all__ = [
    "get_intent_recognition_prompt",
    "get_image_rewrite_prompt",
    "get_text_rewrite_prompt",
    "get_response_generation_prompt",
    "get_no_result_response",
    "get_fallback_response",
]
