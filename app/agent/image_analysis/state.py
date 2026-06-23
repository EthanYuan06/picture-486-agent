"""
昴云助手 - 图片分析状态定义
"""
from typing import TypedDict, Optional, Any


class ImageAnalysisState(TypedDict):
    """图片分析业务专属状态"""
    user_input: str
    image_url: Optional[str]
    analysis_type: str  # "anime_analysis" | "attraction" | "common"
    analysis_result: Optional[dict]
    response_text: str
    response_images: list
