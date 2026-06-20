"""
提示词模块
统一管理工作流中所有节点的提示词
"""

from app.agent.prompts.intent_prompt import get_intent_recognition_prompt
from app.agent.prompts.query_rewrite_prompt import get_image_rewrite_prompt, get_text_rewrite_prompt
from app.agent.prompts.chat_prompt import get_chat_prompt, get_fallback_chat_reply, get_system_prompt
from app.agent.prompts.response_prompt import (
    get_response_generation_prompt,
    get_no_result_response,
    get_fallback_response,
    get_analysis_prompt_template  # 改动：新增图片分析提示词模板函数
)

__all__ = [
    "get_intent_recognition_prompt",
    "get_image_rewrite_prompt",
    "get_text_rewrite_prompt",
    "get_chat_prompt",
    "get_system_prompt",
    "get_fallback_chat_reply",
    "get_response_generation_prompt",
    "get_no_result_response",
    "get_fallback_response",
    "get_analysis_prompt_template",  # 改动：导出图片分析提示词模板函数
]

