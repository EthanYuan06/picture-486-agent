"""
API 辅助工具函数
"""

def extract_ai_reply(messages: list) -> str:
    """
    从 LangGraph 返回的 messages 中提取最后一条 AI 回复文本
    
    Args:
        messages: 消息列表（可能包含字典或 BaseMessage 对象）
    
    Returns:
        AI 回复的文本内容
    """
    if not messages:
        return "抱歉，我没有理解您的问题"
    
    # 倒序查找最后一条 AI 消息
    for msg in reversed(messages):
        # 处理序列化字典格式
        if isinstance(msg, dict) and msg.get("type") == "ai":
            content = msg.get("content", "")
            # 如果是图文混合格式（列表），提取文本部分
            if isinstance(content, list):
                text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
                return "\n".join(text_parts) if text_parts else ""
            return content if isinstance(content, str) else ""
        
        # 处理原生 AIMessage 对象
        elif hasattr(msg, 'content'):
            content = msg.content
            if isinstance(content, list):
                text_parts = [item.get("text", "") for item in content if item.get("type") == "text"]
                return "\n".join(text_parts) if text_parts else ""
            return content if isinstance(content, str) else ""
    
    return "抱歉，我没有理解您的问题"
