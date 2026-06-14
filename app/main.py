from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.common.logger import logger, setup_logging
from app.config.redis_config import client as redis_client
from app.api.chat import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理
    - 启动时：初始化日志，打印服务就绪信息
    - 关闭时：释放 Redis 连接资源
    """
    # 启动阶段
    setup_logging()
    logger.info("服务启动成功，Redis 连接已就绪")
    
    yield
    
    # 关闭阶段
    redis_client.close()
    logger.info("服务关闭，Redis 连接已释放")


app = FastAPI(lifespan=lifespan)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由（prefix 和 tags 在这里统一配置）
app.include_router(router, prefix="/api", tags=["会话管理"])


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