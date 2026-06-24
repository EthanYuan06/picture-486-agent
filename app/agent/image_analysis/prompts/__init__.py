"""
云助手 - 图片分析提示词模块
统一管理图片分析业务的所有提示词模板

职责：
1. 提供图片分析结果格式化提示词
2. 支持不同分析类型（动漫/景点/通用）的差异化提示
3. 保持业务模块内聚，所有提示词集中在本模块
"""

from app.agent.image_analysis.prompts.response_prompt import (
    get_analysis_prompt_template,
)

__all__ = [
    "get_analysis_prompt_template",
]
