"""
昴云助手 - SSE流式对话接口
支持打字机效果和HITL人机交互确认
"""
import json
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.common.logger import logger
from app.agent.workflow import compiled_graph, init_chat_state
from app.entity.schema import ChatRequest

# 创建路由器
router = APIRouter()


def format_sse_event(event_type: str, data: dict) -> str:
    """
    格式化SSE事件（对齐示例标准）
    
    示例格式：
    event: message
    data: {"type": "message", "content": "你好"}
    
    event: interrupt
    data: {"type": "interrupt", "reason": "...", "details": {...}}
    
    Args:
        event_type: 事件类型 (message/interrupt/done/error)
        data: 事件数据
        
    Returns:
        SSE格式字符串（包含 event: 和 data: 两行）
    """
    # 增加 event 行（对齐示例标准）
    event_line = f"event: {event_type}\n"
    data_line = f"data: {json.dumps({'type': event_type, 'data': data}, ensure_ascii=False)}\n\n"
    return event_line + data_line


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    SSE流式对话接口（统一接口，支持HITL自动恢复）
    
    功能特性：
    - 支持打字机效果（逐字推送）
    - 支持HITL人机交互确认（图片上传场景）
    - 支持图文混合输入
    - 自动从 Checkpointer 恢复中断状态（无需单独resume接口）
    
    HITL 工作流程：
    1. 首次请求：正常执行，遇到 interrupt_before 节点时中断
    2. 返回 interrupt 事件，SSE连接关闭
    3. 前端显示确认对话框
    4. 用户确认后，再次调用同一接口（携带 user_confirmed）
    5. LangGraph 自动从 checkpoint 恢复，继续执行
    
    事件类型：
    - message: LLM生成的文本片段（逐字推送）
    - images: 回复中的图片URL列表
    - interrupt: HITL中断事件（需要用户确认）
    - done: 完成事件
    - error: 错误事件
    
    Args:
        request: 聊天请求对象
            - 首次请求：包含 thread_id, query, image_url 等
            - HITL恢复：包含 thread_id, user_confirmed, modified_data
        
    Returns:
        StreamingResponse: SSE流式响应
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # ========== 判断是首次请求还是HITL恢复 ==========
    is_hitl_resume = request.user_confirmed is not None
    
    async def event_generator():
        try:
            if is_hitl_resume:
                # ===== HITL恢复：从断点继续执行 =====
                logger.info(f"[SSE] 会话 {request.thread_id} HITL恢复执行")
                
                # 先 update_state 注入用户确认信息
                update_state = {
                    "user_confirmed": request.user_confirmed
                }
                
                if request.modified_data is not None:
                    update_state["modified_data"] = request.modified_data
                    logger.info(f"[SSE] 收到用户修改数据")
                
                compiled_graph.update_state(config, update_state)
                logger.info(f"[SSE] 已更新状态: user_confirmed={request.user_confirmed}")
                
                # 传入 None 从中断点继续执行（LangGraph自动从checkpoint恢复）
                input_data = None
            else:
                # ===== 首次请求：构建完整输入状态 =====
                logger.info(f"[SSE] 会话 {request.thread_id} 首次请求")
                
                input_state = init_chat_state()
                
                # 构建消息内容（LangChain 标准格式）
                if request.image_url:
                    content_parts = [
                        {"type": "text", "text": request.query},
                        {
                            "type": "image_url",
                            "image_url": {"url": request.image_url}
                        }
                    ]
                else:
                    content_parts = request.query
                
                input_state["messages"] = [{"type": "human", "content": content_parts}]
                
                # 显式传递 image_url 到 state
                if request.image_url:
                    input_state["image_url"] = request.image_url
                    logger.info(f"[SSE] 收到图文消息")
                else:
                    logger.info(f"[SSE] 收到消息: {request.query[:50]}...")
                
                # 传递 user_id 和 space_id
                if request.user_id is not None:
                    input_state["user_id"] = request.user_id
                
                if request.space_id is not None:
                    input_state["space_id"] = request.space_id
                
                input_data = input_state
            
            # ========== 流式执行工作流 ==========
            logger.info(f"[SSE] 开始流式执行")
            
            async for chunk in compiled_graph.astream(
                input_data, 
                config=config,
                stream_mode=["messages", "updates"],  # 改动：同时监听两种模式（对齐示例）
                version="v2"  # 改动：使用 v2 API（对齐示例）
            ):
                # 遍历每个节点的输出
                for node_name, node_output in chunk.items():
                    logger.info(f"[SSE] 节点 {node_name} 执行完成")
                    
                    # ===== 跳过 LangGraph 内部中断节点 =====
                    if node_name == "__interrupt__":
                        # __interrupt__ 节点输出是元组，不是字典，直接跳过
                        logger.info(f"[SSE] 检测到 __interrupt__ 节点，跳过处理")
                        continue
                    
                    # ===== 检测HITL中断 =====
                    if node_name == "image_upload_callback":
                        upload_confirmation = node_output.get("upload_confirmation")
                        if upload_confirmation:
                            logger.info(f"[SSE] 检测到HITL中断，发送interrupt事件")
                            yield format_sse_event("interrupt", upload_confirmation)
                            return  # 关闭SSE连接，等待用户确认
                    
                    # ===== 提取文本响应并逐字推送（模拟打字机效果）=====
                    response_text = node_output.get("response_text")
                    if response_text and isinstance(response_text, str):
                        logger.info(f"[SSE] 节点 {node_name} 返回文本，长度: {len(response_text)}")
                        
                        # 逐字符推送，实现打字机效果
                        for char in response_text:
                            yield format_sse_event("message", {"content": char})
                            await asyncio.sleep(0.02)  # 控制打字速度（50字符/秒）
                    
                    # ===== 提取图片URL列表 =====
                    response_images = node_output.get("response_images", [])
                    if response_images:
                        logger.info(f"[SSE] 节点 {node_name} 返回 {len(response_images)} 张图片")
                        yield format_sse_event("images", {"urls": response_images})
            
            # ========== 发送完成事件 ==========
            logger.info(f"[SSE] 工作流执行完成")
            yield format_sse_event("done", {})
        
        except Exception as e:
            logger.error(f"[SSE] 错误: {str(e)}", exc_info=True)
            yield format_sse_event("error", {"error": str(e)})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用Nginx缓冲
        }
    )
