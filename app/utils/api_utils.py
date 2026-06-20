"""
API 辅助工具函数
"""
import json
from typing import Any, Dict, Optional
from app.common.logger import logger

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


def safe_parse_json(data: Any) -> Dict[str, Any]:
    """
    安全地解析 JSON 数据（字符串或字典）
    
    Args:
        data: 可能是 JSON 字符串或已经是字典的数据
        
    Returns:
        解析后的字典，如果解析失败返回空字典
    """
    if isinstance(data, dict):
        return data
    
    if isinstance(data, str):
        try:
            return json.loads(data)
        except Exception as e:
            logger.warning(f"[safe_parse_json] JSON解析失败: {str(e)}")
            return {}
    
    # 其他类型尝试转为字符串再解析
    try:
        return json.loads(str(data))
    except Exception as e:
        logger.warning(f"[safe_parse_json] 数据类型转换失败: {str(e)}")
        return {}


def success_response(data=None, msg="success", code=200):
    """
    统一成功响应格式
    
    Args:
        data: 业务数据
        msg: 响应消息
        code: 状态码
        
    Returns:
        标准响应字典
    """
    return {"code": code, "msg": msg, "data": data}


def error_response(msg="操作失败", code=500, data=None):
    """
    统一错误响应格式
    
    Args:
        msg: 错误消息
        code: 错误状态码
        data: 额外数据（可选）
        
    Returns:
        标准错误响应字典
    """
    return {"code": code, "msg": msg, "data": data}
