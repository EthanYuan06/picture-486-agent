from pydantic import BaseModel, Field
from typing import Optional, List

class ChatRequest(BaseModel):
    """对话请求体（支持HITL人机交互确认）"""
    thread_id: str  # 会话ID
    query: str      # 用户输入
    image_url: Optional[str] = None # 图片资源在线COS/外部链接，无图则不传
    user_id: Optional[int] = None   # 用户ID（图片上传时使用）
    space_id: Optional[int] = None  # 相册ID（null表示公共图库）
    
    # HITL 人机交互确认相关字段
    user_confirmed: Optional[bool] = None  # 用户是否确认上传
    modified_data: Optional[dict] = None   # 用户修改后的数据
