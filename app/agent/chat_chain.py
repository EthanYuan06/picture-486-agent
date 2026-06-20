"""
昴云助手 - 闲聊模块
负责纯闲聊对话逻辑
"""
from langchain_core.messages import SystemMessage

from app.agent.model.model import deepseek_chat_model
from app.agent.prompts import get_system_prompt, get_fallback_chat_reply
from app.common.logger import logger


# ===================== 闲聊节点 =====================

def _direct_chat(state: dict) -> dict:
    """
    闲聊节点：使用完整消息历史进行多轮对话（优化：支持上下文记忆）
    Args:
        state: 包含 messages 的字典
    Returns:
        response_text, response_images
    """
    # 【改动】获取完整消息历史，而非仅 user_input
    messages = list(state.get("messages", []))
    
    # 【新增】在消息列表开头插入系统提示词，定义 AI 身份和行为规范
    system_prompt = get_system_prompt()
    
    # 构建完整的消息列表（系统提示 + 历史对话）
    full_messages = [SystemMessage(content=system_prompt)] + messages
    
    try:
        # 【改动】传入包含系统提示的完整消息列表
        resp = deepseek_chat_model.invoke(full_messages)
        reply_text = resp.content.strip() if resp.content else None
    except Exception as e:
        # 改动：记录异常并返回 fallback 回复
        logger.error(f"[闲聊节点] LLM调用失败: {str(e)}")
        reply_text = get_fallback_chat_reply()
    
    # 确保 response_text 不为 None
    if not reply_text:
        reply_text = get_fallback_chat_reply()
    
    result = {
        "response_text": reply_text,
        "response_images": [],
    }
    return result
