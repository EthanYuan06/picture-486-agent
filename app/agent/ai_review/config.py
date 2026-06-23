"""AI审核模块配置管理"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class AIReviewConfig:
    """AI审核配置类"""
    
    # ==================== RabbitMQ配置 ====================
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
    
    # 队列配置
    EXCHANGE_NAME = "ai-review-exchange"
    QUEUE_NAME = "ai-review-queue"
    ROUTING_KEY = "ai.review"
    
    # ==================== 后端服务配置 ====================
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8124")
    BACKEND_API_KEY = os.getenv("AI_SERVICE_API_KEY", "")
    
    # ==================== AI服务配置 ====================
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", 
                                   "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    # ==================== 审核配置 ====================
    CONTENT_SAFETY_MODEL = "qwen-vl-plus"  # 内容安全审核使用的模型
    REVIEW_TIMEOUT = 30  # 审核超时时间(秒)
