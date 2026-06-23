"""
昴云助手 - 智能上传状态定义
"""
from typing import TypedDict, Optional
import time


class ImageUploadState(TypedDict):
    """智能上传业务专属状态"""
    user_id: str
    space_id: Optional[str]
    image_url: str
    analysis_result: dict
    upload_confirmation: Optional[dict]
    user_confirmed: Optional[bool]
    modified_data: Optional[dict]
    confirmation_timestamp: Optional[float]
    callback_result: Optional[dict]
    response_text: str
