"""
昴云助手 - RAG检索状态定义
"""
from typing import TypedDict, Optional, List
from langchain_core.documents import Document


class RAGState(TypedDict):
    """RAG检索业务专属状态"""
    user_input: str
    image_url: Optional[str]
    intent: str  # "text_retrieval" | "image_retrieval" | "other"
    rewritten_query: Optional[str]
    expected_count: int
    query_embedding: Optional[List[float]]
    retrieved_docs: List[Document]
    reranked_docs: List[Document]
    response_text: str
    response_images: List[str]
    error_message: Optional[str]
