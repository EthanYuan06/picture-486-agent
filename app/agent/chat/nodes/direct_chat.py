"""
昴云助手 - 闲聊节点模块
负责纯闲聊对话逻辑
"""
from langchain_core.messages import SystemMessage

# 改动：从闲聊业务模块导入模型和提示词
from app.agent.model.model import deepseek_chat_model
# 改动：直接导入提示词函数，无需经过 __init__.py
from app.agent.chat.prompts.chat_prompt import get_system_prompt, get_fallback_chat_reply
from app.common.logger import logger


# ===================== 闲聊节点 =====================

async def _direct_chat(state: dict) -> dict:
    """
    闲聊节点：使用完整消息历史进行多轮对话（优化：支持上下文记忆）
    注意：DeepSeek 不支持多模态输入，需要清理消息中的图片内容，但保留文本上下文
    Args:
        state: 包含 messages 的字典
    Returns:
        response_text, response_images
    """
    # 【改动】获取完整消息历史，而非仅 user_input
    raw_messages = list(state.get("messages", []))
    
    # 【新增】清理消息中的图片内容，但保留文本部分以维持对话上下文（DeepSeek 不支持 image_url）
    cleaned_messages = []
    for msg in raw_messages:
        if isinstance(msg, dict):
            # 序列化字典格式
            content = msg.get("content")
            if isinstance(content, list):
                # 多模态消息：只保留 text 类型的内容块
                text_blocks = [block for block in content if block.get("type") == "text"]
                if text_blocks:
                    # 重建消息，只包含文本块
                    cleaned_msg = {**msg, "content": text_blocks}
                    cleaned_messages.append(cleaned_msg)
                # 如果只有图片没有文本，则跳过该消息
            elif isinstance(content, str):
                # 纯文本消息：直接保留
                cleaned_messages.append(msg)
        else:
            # 原生 Message 对象
            from langchain_core.messages import HumanMessage, AIMessage
            content = msg.content
            if isinstance(content, list):
                # 多模态消息：只保留 text 类型的内容块
                text_blocks = [block for block in content if block.get("type") == "text"]
                if text_blocks:
                    # 创建新的消息对象，只包含文本块
                    if isinstance(msg, HumanMessage):
                        cleaned_msg = HumanMessage(content=text_blocks)
                    elif isinstance(msg, AIMessage):
                        cleaned_msg = AIMessage(content=text_blocks)
                    else:
                        cleaned_msg = HumanMessage(content=text_blocks)
                    cleaned_messages.append(cleaned_msg)
                # 如果只有图片没有文本，则跳过该消息
            elif isinstance(content, str):
                # 纯文本消息：直接保留
                cleaned_messages.append(msg)
    
    # 【新增】在消息列表开头插入系统提示词，定义 AI 身份和行为规范
    system_prompt = get_system_prompt()
    
    # 构建完整的消息列表（系统提示 + 清理后的历史对话）
    full_messages = [SystemMessage(content=system_prompt)] + cleaned_messages
    
    try:
        # 【改动】传入包含系统提示的完整消息列表
        resp = await deepseek_chat_model.ainvoke(full_messages)
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
