"""
昴云助手 - SSE流式对话接口
支持打字机效果和HITL人机交互确认
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.common.logger import logger
from app.agent.workflow import compiled_graph
from app.agent.state import init_chat_state
from app.entity.schema import ChatRequest
from app.utils.sse_utils import (
    format_sse_event,
    build_hitl_resume_state,
    build_first_request_state,
    process_node_output
)

# 创建路由器
router = APIRouter()


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    SSE流式对话接口（统一接口，支持HITL自动恢复）
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # 判断是首次请求还是HITL恢复
    is_hitl_resume = request.user_confirmed is not None
    
    async def event_generator():
        try:
            if is_hitl_resume:
                # HITL恢复：从断点继续执行
                update_state = build_hitl_resume_state(
                    user_confirmed=request.user_confirmed,
                    space_id=request.space_id,
                    modified_data=request.modified_data
                )
                await compiled_graph.aupdate_state(config, update_state)
                input_data = None
            else:
                # 首次请求：构建完整输入状态
                input_data = build_first_request_state(
                    query=request.query,
                    user_id=request.user_id,
                    image_url=request.image_url,
                    space_id=request.space_id,
                    init_state_func=init_chat_state
                )
            
            # 流式执行工作流
            async for chunk in compiled_graph.astream(
                input_data, 
                config=config,
                stream_mode="updates"
            ):
                for node_name, node_output in chunk.items():
                    # 处理节点输出并生成SSE事件
                    async for sse_event in process_node_output(node_name, node_output):
                        yield sse_event
                        # 如果是中断事件，立即返回
                        if '"type": "interrupt"' in sse_event:
                            return
            
            # 发送完成事件
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
