from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
import uvicorn
from app.common.logger import logger, setup_logging
from app.config.redis_config import client as redis_client, checkpointer
from app.api.chat import router as chat_router
from app.api.cos import router as cos_router
from app.api.chat_sse import router as chat_sse_router  # 新增：SSE流式接口
from app.agent.ai_review.consumer import start_ai_review_consumer, stop_ai_review_consumer

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理
    - 启动时：初始化日志，初始化Redis索引，启动MQ消费者，打印服务就绪信息
    - 关闭时：释放 Redis 连接资源，停止MQ消费者
    """
    # 启动阶段
    setup_logging()
    
    # 初始化 AsyncRedisSaver 索引（必须！）
    try:
        await checkpointer.asetup()
        logger.info("Redis Checkpointer 索引初始化成功")
    except Exception as e:
        logger.error(f"Redis Checkpointer 索引初始化失败: {str(e)}", exc_info=True)
        raise
    
    logger.info("服务启动成功，Redis 连接已就绪")
    
    # 启动AI审核MQ消费者(后台任务)
    ai_review_task = asyncio.create_task(start_ai_review_consumer())
    logger.info("AI审核消费者已启动")
    
    yield
    
    # 关闭阶段
    stop_ai_review_consumer()
    logger.info("AI审核消费者已停止")
    
    redis_client.close()
    logger.info("服务关闭，Redis 连接已释放")


app = FastAPI(lifespan=lifespan)

# ===================== 全局异常处理 =====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """处理 FastAPI HTTPException"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": exc.detail, "data": None}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """处理所有未捕获异常"""
    logger.error(f"全局异常捕获: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": f"服务器内部错误: {str(exc)}", "data": None}
    )

# ===================== 中间件配置 =====================

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由（prefix 和 tags 在这里统一配置）
app.include_router(chat_router, prefix="/api", tags=["会话管理"])
app.include_router(cos_router, prefix="/api", tags=["云存储"])
app.include_router(chat_sse_router, prefix="/api", tags=["SSE流式对话"])  # 新增：SSE流式接口


if __name__ == "__main__":
    """直接运行此文件启动服务"""
    setup_logging()
    logger.info(f"服务启动中...")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8024,
        reload=True  # 开发模式自动重载，生产模式务必关掉
    )