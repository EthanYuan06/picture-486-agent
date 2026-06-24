"""
统一的结构化输出 Schema 定义
所有 LLM 输出的类型约束集中管理，配合 Output Parser 使用
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ImageUploadAnalysis(BaseModel):
    """图片上传智能分析结果"""
    name: str = Field(
        description="图片名称",
        min_length=1,
        max_length=50
    )
    introduction: str = Field(
        description="图片简介",
        min_length=1,
        max_length=200
    )
    category: str = Field(
        description="图片分类",
        examples=["风景", "动漫", "人物", "美食", "其他"]
    )
    tags: List[str] = Field(
        description="标签列表",
        min_length=1,
        max_length=10,
        examples=["清新", "治愈", "蓝天白云"]
    )


class AnimeInfoTranslation(BaseModel):
    """动漫信息翻译结果"""
    character: str = Field(
        description="中文角色名",
        min_length=1
    )
    work: str = Field(
        description="中文作品名",
        min_length=1
    )


class QueryRewriteResult(BaseModel):
    """查询重写结果"""
    keywords: str = Field(
        description="重写后的检索关键词",
        min_length=1
    )
    expected_count: int = Field(
        description="期望返回的图片数量",
        ge=1,
        le=10,
        default=3
    )


class IntentRecognitionResult(BaseModel):
    """意图识别结果（纯文本场景）"""
    intent: str = Field(
        description="意图类型",
        pattern="^(retrieval|chat)$"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="判断理由（可选，用于调试）",
        max_length=100
    )


class ImageIntentRecognitionResult(BaseModel):
    """图片意图识别结果（多模态场景）"""
    intent: str = Field(
        description="意图类型",
        pattern="^(upload|analysis|retrieval|chat)$"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="置信度 0-1",
        ge=0.0,
        le=1.0
    )
