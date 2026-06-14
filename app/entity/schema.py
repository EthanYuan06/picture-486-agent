from pydantic import BaseModel


class ChatRequest(BaseModel):
    """对话请求体"""
    thread_id: str  # 会话ID
    query: str      # 用户输入
