"""
昴云助手 - 出口节点模块
负责通用的输出格式化，被检索、闲聊、图片分析三条链路共同使用
"""
from langchain_core.messages import AIMessage


# ===================== 出口格式化节点 =====================

def _format_output(state: dict) -> dict:
    """
    出口节点:将 response_text + response_images 转为 AIMessage (LangChain 标准格式)
    Args:
        state: 包含 response_text, response_images 的字典
    Returns:
        {"messages": [AIMessage(content=[...])]} 使用标准图文格式
    """
    # 构建标准 LangChain 图文消息格式
    content_parts = []
    
    response_text = state.get("response_text")
    if response_text:
        content_parts.append({"type": "text", "text": response_text})
    
    # 添加图片URL (使用 LangChain 标准格式)
    if state.get("response_images"):
        for img_url in state["response_images"]:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
    
    # 如果没有任何内容,使用默认文本
    if not content_parts:
        content_parts.append({"type": "text", "text": "抱歉,没有找到相关图片"})
    
    return {"messages": [AIMessage(content=content_parts)]}
