import os
from typing import List, Tuple, Optional
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
import dashscope

from app.agent.chroma import chroma_vector_store
from app.agent.model.model import multi_embedding_model

load_dotenv()

# 配置 DashScope API 地址
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

@tool(response_format="content_and_artifact")
def multimodal_retrieve(query: str, image_url: Optional[str] = None, filters: Optional[dict] = None) -> Tuple[str, List[Document]]:
    """
    【节点2：调用检索工具】跨模态检索工具。
    支持通过自然语言提取元数据过滤（category, tags），并结合图片视觉特征进行细粒度检索。
    
    流程说明：
    1. 接收用户查询文本和图片URL（可选）
    2. 调用嵌入模型进行向量化（纯文本或多模态融合）
    3. 在Chroma向量数据库中执行相似性检索
    4. 返回匹配的文档列表
    
    Args:
        query: 用户的文本查询（必填）
        image_url: (可选) 用户上传的图片公网 URL。如有则启用多模态检索，否则使用纯文本检索
        filters: (可选) 自动提取的元数据过滤条件，如 {"category": "car"} 
                 注意：tags 字段在库中为 JSON 字符串，建议过滤时使用精确匹配或包含匹配。
    
    Returns:
        Tuple[str, List[Document]]: 
            - 第一个元素：简短的状态描述（用于调试）
            - 第二个元素：匹配的文档列表，每个文档的metadata中包含image_url字段
    """
    
    # 【节点2.1：调试日志】
    print(f"\n=== Multimodal Retrieve Debug ===")
    print(f"Query: {query}")
    print(f"Image URL: {image_url}")
    print(f"Filters: {filters}")
    print("=================================\n")
    
    # 【节点2.2：判断检索模式】根据是否有图片URL决定使用多模态还是纯文本检索
    if image_url:
        # 【分支A：多模态检索】有图片URL，使用图文融合向量检索
        print(f"Using multimodal retrieval with image...")
        
        try:
            # 【节点2.3：多模态向量化】构造多模态输入并调用DashScope多模态嵌入模型
            multimodal_input = [
                {"text": query},
                {"image": image_url}
            ]
            
            # 调用多模态嵌入模型（内部已封装向量化逻辑）
            embedding_resp = multi_embedding_model
            
            if embedding_resp.status_code == 200:
                # 【节点2.4：获取查询向量】从响应中提取融合后的向量
                query_embedding = embedding_resp.output["embeddings"][0]["embedding"]
                
                # 【节点2.5：Chroma向量检索】使用向量直接在Chroma中搜索
                results = chroma_vector_store._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=3,  # 返回最相关的3个结果
                    where=filters if filters else None,  # 应用元数据过滤
                    include=['documents', 'metadatas', 'distances']
                )
                
                # 【节点2.6：转换为Document对象】将Chroma原始结果转换为LangChain Document格式
                from langchain_core.documents import Document
                final_docs = []
                for i in range(len(results['ids'][0])):
                    doc = Document(
                        page_content=results['documents'][0][i],
                        metadata=results['metadatas'][0][i]
                    )
                    final_docs.append(doc)
            else:
                print(f"Multimodal embedding failed: {embedding_resp.code} - {embedding_resp.message}")
                final_docs = []
        except Exception as e:
            print(f"Multimodal retrieval error: {e}")
            final_docs = []
    else:
        # 【分支B：纯文本检索】无图片URL，使用纯文本向量检索
        print(f"Using text-only retrieval...")
        combined_query = query.strip()
        
        # 【节点2.3：配置检索参数】使用MMR（最大边界相关性）算法保证结果多样性
        search_kwargs = {
            "k": 3,           # 返回3个结果
            "fetch_k": 10,    # 先检索10个候选
            "lambda_mult": 0.7  # MMR平衡参数（0-1之间，越大越重视相关性，越小越重视多样性）
        }
        
        # 【节点2.4：应用元数据过滤】如果提供了过滤条件，添加到检索参数中
        if filters:
            import json
            if isinstance(filters, str):
                try:
                    filters = json.loads(filters)
                except json.JSONDecodeError:
                    print(f"Warning: Failed to parse filters as JSON: {filters}")
                    filters = None
            
            if filters and isinstance(filters, dict):
                search_kwargs["filter"] = filters
        
        # 【节点2.5：创建Retriever并执行检索】
        retriever = chroma_vector_store.as_retriever(
            search_type="mmr",
            search_kwargs=search_kwargs
        )
        final_docs = retriever.invoke(combined_query)
        
        # 【节点2.6：降级策略】如果MMR返回0结果，尝试使用普通相似度搜索作为备选
        if len(final_docs) == 0:
            print(f"MMR returned 0 results, falling back to similarity search")
            search_kwargs.pop("fetch_k", None)
            search_kwargs.pop("lambda_mult", None)
            final_docs = chroma_vector_store.similarity_search(combined_query, k=3)

    # 【节点2.7：返回结果】返回二元组：(状态描述, 文档列表)
    # 注意：Agent会从final_docs中提取metadata中的image_url字段进行输出
    if len(final_docs) > 0:
        retrieval_mode = "multimodal" if image_url else "text-only"
        summary_str = f"Retrieved {len(final_docs)} documents using {retrieval_mode} retrieval."
    else:
        summary_str = f"No documents found for query: {query}"
    
    return summary_str, final_docs

# web搜索工具,LangChain已封装，不需要@tool
web_search = TavilySearch(
    max_results=5,
    topic="general",
    api_key=os.environ.get("TAVILY_API_KEY"),
)
