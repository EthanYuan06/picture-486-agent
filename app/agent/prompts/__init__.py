"""
提示词模块
统一管理工作流中所有节点的提示词（闲聊、图片上传、RAG提示词已迁移至各自业务模块）
"""

# 改动：移除RAG相关提示词导入，已迁移至 app.agent.rag.prompts
from app.agent.prompts.response_prompt import (
    get_analysis_prompt_template  # 改动：图片分析提示词模板函数
)

__all__ = [
    # 改动：移除闲聊、图片上传和RAG相关导出，已迁移至各自业务模块
    "get_analysis_prompt_template",  # 改动：导出图片分析提示词模板函数
]
