"""
昴云助手 - RAG检索配置常量
"""

# MMR重排参数
LAMBDA_MULT = 0.5

# 默认期望返回数量
DEFAULT_EXPECTED_COUNT = 3

# 意图类型枚举
INTENT_TYPES = {
    "TEXT_RETRIEVAL": "text_retrieval",
    "IMAGE_RETRIEVAL": "image_retrieval",
    "OTHER": "other",
    "ERROR": "error"
}
