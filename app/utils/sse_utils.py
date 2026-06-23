"""
SSE流式响应工具函数
提供SSE事件格式化、状态构建、节点输出处理等公共功能
"""
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional


def format_sse_event(event_type: str, data: dict) -> str:
    """
    格式化SSE事件（对齐示例标准）
    
    Args:
        event_type: 事件类型（message/interrupt/images/done/error）
        data: 事件数据字典
    
    Returns:
        SSE格式字符串
    """
    event_line = f"event: {event_type}\n"
    data_line = f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
    return event_line + data_line


def build_hitl_resume_state(
    user_confirmed: bool,
    space_id: Optional[str] = None,
    modified_data: Optional[dict] = None
) -> Dict[str, Any]:
    """
    构建HITL恢复时的状态更新数据
    
    Args:
        user_confirmed: 用户是否确认
        space_id: 相册ID（可选）
        modified_data: 用户修改的数据（可选）
    
    Returns:
        状态更新字典
    """
    update_state = {"user_confirmed": user_confirmed}
    
    if space_id is not None:
        update_state["space_id"] = space_id
    
    if modified_data is not None:
        update_state["modified_data"] = modified_data
        # 如果 modified_data 中包含 space_id，优先使用
        if "space_id" in modified_data:
            update_state["space_id"] = modified_data["space_id"]
    
    return update_state


def build_first_request_state(
    query: str,
    user_id: str,
    image_url: Optional[str] = None,
    space_id: Optional[str] = None,
    init_state_func=None
) -> Dict[str, Any]:
    """
    构建首次请求的输入状态
    
    Args:
        query: 用户查询文本
        user_id: 用户ID（必填）
        image_url: 图片URL（可选）
        space_id: 相册ID（可选）
        init_state_func: 初始化状态的函数（从workflow导入）
    
    Returns:
        完整的输入状态字典
    """
    input_state = init_state_func() if init_state_func else {}
    
    # 构建消息内容（LangChain 标准格式）
    if image_url:
        content_parts = [
            {"type": "text", "text": query},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    else:
        content_parts = query
    
    input_state["messages"] = [{"type": "human", "content": content_parts}]
    
    if image_url:
        input_state["image_url"] = image_url
    
    input_state["user_id"] = user_id
    
    if space_id is not None:
        input_state["space_id"] = space_id
    
    return input_state


async def process_node_output(
    node_name: str,
    node_output: Dict[str, Any],
    typing_speed: float = 0.02
) -> AsyncGenerator[str, None]:
    """
    处理工作流节点输出，生成SSE事件流
    
    Args:
        node_name: 节点名称
        node_output: 节点输出数据
        typing_speed: 打字机速度（秒/字符），默认0.02
    
    Yields:
        SSE事件字符串
    """
    # 跳过 LangGraph 内部中断节点
    if node_name == "__interrupt__":
        return
    
    # 检测HITL中断
    if node_name == "image_upload_analyzer":
        upload_confirmation = node_output.get("upload_confirmation")
        if upload_confirmation:
            yield format_sse_event("interrupt", upload_confirmation)
            return
    
    # 提取文本响应并逐字推送
    response_text = node_output.get("response_text")
    if response_text and isinstance(response_text, str):
        for char in response_text:
            yield format_sse_event("message", {"content": char})
            await asyncio.sleep(typing_speed)
    
    # 提取图片URL列表
    response_images = node_output.get("response_images", [])
    if response_images:
        yield format_sse_event("images", {"urls": response_images})
