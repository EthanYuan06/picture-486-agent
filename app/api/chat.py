import uuid
from fastapi import APIRouter, HTTPException
from app.common.logger import logger
from app.config.redis_config import checkpointer
from app.agent.workflow import compiled_graph, init_chat_state
from app.entity.schema import ChatRequest
from app.utils.api_utils import extract_ai_reply, success_response

# 创建路由器（prefix 由 main.py 统一配置）
router = APIRouter()

@router.get("/create-thread")
def create_thread():
    """
    创建全新会话，生成唯一 UUID 作为 thread_id
    """
    thread_id = str(uuid.uuid4())
    logger.info(f"创建新会话: {thread_id}")
    return success_response(
        data={"thread_id": thread_id},
        msg="会话创建成功"
    )

@router.get("/check-thread/{thread_id}")
def check_thread(thread_id: str):
    """
    获取当前会话
    """
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint = checkpointer.get(config)
    exist = checkpoint is not None
    
    logger.info(f"校验会话 {thread_id}: {'存在' if exist else '不存在'}")
    return success_response(
        data={"thread_id": thread_id, "exist": exist},
        msg=f"会话{'存在' if exist else '不存在'}"
    )

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    对话交互接口（支持HITL人机交互确认）
    - 支持纯文本和图文混合输入
    - 根据 thread_id 自动加载历史上下文
    - 调用 graph.invoke 执行对话
    - Redis 自动持久化新上下文
    - HITL：图片上传时会中断等待用户确认，第二次调用时继续执行
    """
    # 构建配置
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # HITL：检查是否是第二次请求（携带用户确认信息）
    is_hitl_resume = request.user_confirmed is not None
    
    if is_hitl_resume:
        # HITL：第二次请求，从中断点恢复执行（官方标准方式）
        logger.info(f"会话 {request.thread_id} HITL恢复执行")
        
        # 关键：先 update_state 注入用户确认信息
        update_state = {
            "user_confirmed": request.user_confirmed
        }
        
        if request.modified_data is not None:
            update_state["modified_data"] = request.modified_data
            logger.info(f"会话 {request.thread_id} 收到用户修改数据")
        
        compiled_graph.update_state(config, update_state)
        logger.info(f"会话 {request.thread_id} 已更新状态: user_confirmed={request.user_confirmed}")
        
        # 传入 None 从中断点继续执行（官方文档标准做法）
        result = await compiled_graph.ainvoke(None, config=config)
        logger.info(f"会话 {request.thread_id} 恢复执行完成")
    else:
        # 首次请求：正常构建输入状态
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
            logger.info(f"会话 {request.thread_id} 收到图文消息: {request.query[:50]}...")
        else:
            logger.info(f"会话 {request.thread_id} 收到消息: {request.query[:50]}...")
        
        # 传递 user_id 和 space_id
        if request.user_id is not None:
            input_state["user_id"] = request.user_id
            logger.info(f"会话 {request.thread_id} 收到用户ID: {request.user_id}")
        
        if request.space_id is not None:
            input_state["space_id"] = request.space_id
            logger.info(f"会话 {request.thread_id} 收到相册ID: {request.space_id}")
        
        # 首次请求：正常调用
        result = await compiled_graph.ainvoke(input_state, config=config)
    
    # 提取 AI 回复文本和图片URL
    reply_text, reply_images = extract_ai_reply(result.get("messages", []))
    
    # HITL：如果有确认信息，一并返回给前端
    response_data = {
        "thread_id": request.thread_id,
        "query": request.query,
        "reply": reply_text,
        "images": reply_images  # 【新增】返回图片URL列表
    }
    
    # 如果有上传确认信息，添加到响应中
    upload_confirmation = result.get("upload_confirmation")
    if upload_confirmation:
        response_data["upload_confirmation"] = upload_confirmation
        logger.info(f"会话 {request.thread_id} 返回上传确认信息")
    
    return success_response(data=response_data)


# ===================== 接口4：删除会话 =====================

@router.delete("/delete-thread/{thread_id}")
def delete_thread(thread_id: str):
    """
    删除指定会话的所有历史数据
    调用 checkpointer.delete_thread() 清空该会话所有检查点
    """
    # RedisSaver 的 delete_thread 方法直接接收 thread_id 字符串
    checkpointer.delete_thread(thread_id)
    
    logger.info(f"会话 {thread_id} 已删除")
    return success_response(
        data={"thread_id": thread_id},
        msg="会话删除成功"
    )
