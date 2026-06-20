from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    """对话请求体"""
    thread_id: str  # 会话ID
    query: str      # 用户输入
    image_url: Optional[str] = None # 图片资源在线COS/外部链接，无图则不传
