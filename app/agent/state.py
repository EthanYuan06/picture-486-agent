"""
昴云助手 - 状态定义模块
集中管理 LangGraph 工作流的状态结构
"""
import operator
from typing import List, Optional, Annotated, Sequence

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from app.agent.config import workflow_config as config


# ===================== 状态定义 =====================

class ChatState(TypedDict):
    """
    LangGraph 对话标准状态
    - messages: 使用 operator.add 支持多轮对话累积
    - 其他字段: 用于节点间传递临时业务数据（不累积，每次覆盖）
    """
    messages: Annotated[Sequence[BaseMessage], operator.add]  # 消息历史（累积）
    
    # 临时业务字段（用于节点间数据传递，每次覆盖）
    user_input: str  # 用户输入文本
    image_url: Optional[str]  # 图片URL
    filters: Optional[dict]  # 元数据过滤条件
    intent: str  # 意图类型
    expected_count: int  # 用户期望返回的图片数量（默认3）
    rewritten_query: str  # 重写后的查询词
    query_embedding: Optional[List[float]]  # 查询向量
    retrieved_docs: List[Document]  # 检索结果
    reranked_docs: List[Document]  # 重排后结果
    response_text: str  # 生成的回复文本
    response_images: List[str]  # 回复中的图片URL列表
    
    # 图片分析相关字段
    analysis_type: Optional[str]  # 图片分析类型：attraction | anime_analysis | common
    analysis_result: Optional[dict]  # 图片分析结果（JSON格式）
    
    # 图片上传相关字段
    user_id: Optional[int]  # 用户ID（从请求传入）
    space_id: Optional[int]  # 相册ID（null表示公共图库）
    callback_result: Optional[dict]  # 回调后端结果
    
    # HITL 人机交互确认相关字段
    upload_confirmation: Optional[dict]  # 待确认的上传数据
    user_confirmed: Optional[bool]  # 用户是否确认
    modified_data: Optional[dict]  # 用户修改后的数据
    confirmation_timestamp: Optional[float]  # 确认请求时间戳（用于超时判断）


def init_chat_state() -> ChatState:
    """
    全局状态初始化函数
    为所有状态字段赋予空值默认值，杜绝字段缺失、KeyError 异常
    Returns:
        包含所有字段默认值的 ChatState 实例
    """
    return {
        "messages": [],
        "user_input": "",
        "image_url": None,
        "filters": None,
        "intent": "other",
        "expected_count": config.DEFAULT_EXPECTED_COUNT,  # 改动：使用配置常量
        "rewritten_query": "",
        "query_embedding": None,
        "retrieved_docs": [],
        "reranked_docs": [],
        "response_text": "",
        "response_images": [],
        "analysis_type": None,
        "analysis_result": None,
        "user_id": None,
        "space_id": None,
        "callback_result": None,
        "upload_confirmation": None,
        "user_confirmed": None,
        "modified_data": None,
        "confirmation_timestamp": None
    }
