"""
AI图片审核模块
对外统一导出接口，确保 main.py 无需修改导入路径
"""

# 从 workflow 模块导出工作流实例和执行函数
from app.agent.ai_review.workflow import ai_review_graph, execute_ai_review

# 从 callback 模块导出回调函数
from app.agent.ai_review.callback import callback_backend

# 从 consumer 模块导出消费者启动/停止函数
from app.agent.ai_review.consumer import start_ai_review_consumer, stop_ai_review_consumer

__all__ = [
    "ai_review_graph",
    "execute_ai_review",
    "callback_backend",
    "start_ai_review_consumer",
    "stop_ai_review_consumer",
]
