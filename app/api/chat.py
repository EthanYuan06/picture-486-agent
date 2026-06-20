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
def chat(request: ChatRequest):
    """
    对话交互接口
    - 支持纯文本和图文混合输入
    - 根据 thread_id 自动加载历史上下文
    - 调用 graph.invoke 执行对话
    - Redis 自动持久化新上下文
    """
    # 构建配置
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # 构建输入状态（支持多模态）
    input_state = init_chat_state()
    
    # 改动：构建消息内容（LangChain 标准格式）
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
    
    # 改动：显式传递 image_url 到 state（确保下游节点可访问）
    if request.image_url:
        input_state["image_url"] = request.image_url
        logger.info(f"会话 {request.thread_id} 收到图文消息: {request.query[:50]}...")
    else:
        logger.info(f"会话 {request.thread_id} 收到消息: {request.query[:50]}...")
    
    # 调用 LangGraph 工作流
    result = compiled_graph.invoke(input_state, config=config)
    
    # 提取 AI 回复文本
    reply_text = extract_ai_reply(result.get("messages", []))
    
    return success_response(
        data={
            "thread_id": request.thread_id,
            "query": request.query,
            "reply": reply_text
        }
    )


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
