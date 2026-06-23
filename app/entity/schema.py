from pydantic import BaseModel, Field
from typing import Optional, List

class ChatRequest(BaseModel):
    """
    对话请求体（支持HITL人机交互确认）
    
    字段说明：
    - thread_id: 会话ID（UUID格式）
    - query: 用户输入文本
    - image_url: 图片URL（可选，用于图文混合输入或图片上传）
    - user_id: 用户ID（必填，用于后端API调用权限控制）
    - space_id: 相册ID（可选，null表示公共图库，非null表示个人相册）
    - user_confirmed: HITL确认标志（可选，用户点击确认时为true）
    - modified_data: 用户修改的数据（可选，HITL恢复时携带）
    """
    thread_id: str = Field(..., description="会话ID（UUID格式）")
    query: str = Field(..., description="用户输入文本")
    image_url: Optional[str] = Field(None, description="图片URL（可选）")
    user_id: int = Field(..., description="用户ID（必填，用于后端API调用权限控制）")
    space_id: Optional[int] = Field(None, description="相册ID（null表示公共图库，非null表示个人相册）")
    
    # HITL 人机交互确认相关字段
    user_confirmed: Optional[bool] = Field(None, description="用户是否确认上传（HITL恢复时使用）")
    modified_data: Optional[dict] = Field(None, description="用户修改后的数据（HITL恢复时使用）")
