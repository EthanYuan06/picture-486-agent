from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
import dashscope
import os
from typing import List
from langchain_deepseek import ChatDeepSeek

load_dotenv()

# 主模型初始化
# 改动：修正 DeepSeek 模型的 base_url，从 DASHSCOPE_BASE_URL 改为 DEEPSEEK_BASE_URL
deepseek_chat_model = init_chat_model(
    model="deepseek-v4-flash",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL"),  # 改动：使用 DeepSeek 官方地址
)

# 多模态视觉模型初始化
qwen_vision_model = init_chat_model(
    model="qwen3.7-plus",
    model_provider="openai",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    temperature=0.1,  # 图片分析要稳，随机性低
    max_tokens=600
)

# 多模态嵌入模型初始化
class DashScopeMultiModalEmbeddings(Embeddings):
    """在线阶段对用户消息与图片特征信息向量化，只需处理文本"""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未设置")
    # 重写LangChain文本向量化方法
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            resp = dashscope.MultiModalEmbedding.call(
                api_key=self.api_key,
                model="qwen3-vl-embedding",
                input=[{"text": text}],
                enable_fusion=True,
            )
            if getattr(resp, "status_code", 200) != 200:
                raise RuntimeError(str(resp))
            embeddings.append(resp.output["embeddings"][0]["embedding"])
        return embeddings
    # 重写LangChain向量检索方法
    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
    
    # 多模态图文融合向量化（文本+图片URL）
    def embed_multimodal(self, text: str, image_url: str) -> List[float]:
        """
        多模态嵌入：将文本和图片URL融合为单一向量
        Args:
            text: 查询文本
            image_url: 图片公网URL
        Returns:
            融合后的向量
        """
        resp = dashscope.MultiModalEmbedding.call(
            api_key=self.api_key,
            model="qwen3-vl-embedding",
            input=[{"text": text}, {"image": image_url}],
            enable_fusion=True,
        )
        if getattr(resp, "status_code", 200) != 200:
            raise RuntimeError(f"多模态嵌入失败: {resp.code} - {resp.message}")
        return resp.output["embeddings"][0]["embedding"]

# 全局单例嵌入实例（对外统一使用）
multi_embedding_model = DashScopeMultiModalEmbeddings()


# 多模态重排序模型
class DashScopeRerankModel:
    """DashScope qwen3-vl-rerank 多模态重排序模型"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未设置")
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    
    def rerank(self, query: str, documents: List[str], top_n: int = 3) -> List[int]:
        """
        对文档列表进行重排序
        Args:
            query: 查询文本
            documents: 候选文档列表
            top_n: 返回前 N 个最相关的文档索引
        Returns:
            重排后的文档索引列表（按相关性从高到低）
        """
        import requests
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "entity": "qwen3-vl-rerank",
            "input": {
                "query": query,
                "documents": documents
            },
            "parameters": {
                "return_documents": False,
                "top_n": top_n
            }
        }
        
        response = requests.post(
            self.base_url, 
            headers=headers, 
            json=data, 
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        # 返回格式: {"output": {"results": [{"index": 2, "score": 0.95}, ...]}}
        indices = [item["index"] for item in result["output"]["results"]]
        return indices


# 全局单例重排序实例
rerank_model = DashScopeRerankModel()