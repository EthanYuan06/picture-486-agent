import uuid
from fastapi import APIRouter, HTTPException
from app.common.logger import logger
from app.config.redis_config import checkpointer
from app.agent.workflow import compiled_graph, init_chat_state
from app.entity.schema import ChatRequest
from app.utils.api_utils import extract_ai_reply

# 创建路由器（prefix 由 main.py 统一配置）
router = APIRouter()


# ===================== 接口1：新建会话 =====================

@router.get("/create-thread")
def create_thread():
    """
    创建全新会话，生成唯一 UUID 作为 thread_id
    仅生成 ID，不操作 Redis
    """
    try:
        thread_id = str(uuid.uuid4())
        logger.info(f"创建新会话: {thread_id}")
        return {
            "code": 200,
            "thread_id": thread_id,
            "msg": "会话创建成功"
        }
    except Exception as e:
        logger.error(f"创建会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


# ===================== 接口2：校验会话是否存在 =====================

@router.get("/check-thread/{thread_id}")
def check_thread(thread_id: str):
    """
    判断传入的 thread_id 是否有历史对话上下文
    调用 checkpointer.get() 查询检查点
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = checkpointer.get(config)
        exist = checkpoint is not None
        
        logger.info(f"校验会话 {thread_id}: {'存在' if exist else '不存在'}")
        return {
            "code": 200,
            "thread_id": thread_id,
            "exist": exist,
            "msg": f"会话{'存在' if exist else '不存在'}"
        }
    except Exception as e:
        logger.error(f"校验会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"校验会话失败: {str(e)}")


# ===================== 接口3：对话交互 =====================

@router.post("/chat")
def chat(request: ChatRequest):
    """
    对话交互接口
    - 根据 thread_id 自动加载历史上下文
    - 调用 graph.invoke 执行对话
    - Redis 自动持久化新上下文
    """
    try:
        # 构建配置
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # 构建输入状态（使用标准消息格式）
        input_state = init_chat_state()
        input_state["messages"] = [{"type": "human", "content": request.query}]
        
        logger.info(f"会话 {request.thread_id} 收到消息: {request.query[:50]}...")
        
        # 调用 LangGraph 工作流
        result = compiled_graph.invoke(input_state, config=config)
        
        # 提取 AI 回复文本
        reply_text = extract_ai_reply(result.get("messages", []))
        
        logger.info(f"会话 {request.thread_id} 回复成功")
        return {
            "code": 200,
            "thread_id": request.thread_id,
            "query": request.query,
            "reply": reply_text,
            "msg": "success"
        }
    except Exception as e:
        logger.error(f"对话处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")


# ===================== 接口4：删除会话 =====================

@router.delete("/delete-thread/{thread_id}")
def delete_thread(thread_id: str):
    """
    删除指定会话的所有历史数据
    调用 checkpointer.delete_thread() 清空该会话所有检查点
    """
    try:
        # RedisSaver 的 delete_thread 方法直接接收 thread_id 字符串
        checkpointer.delete_thread(thread_id)
        
        logger.info(f"会话 {thread_id} 已删除")
        return {
            "code": 200,
            "thread_id": thread_id,
            "msg": "会话删除成功"
        }
    except Exception as e:
        logger.error(f"删除会话失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")
