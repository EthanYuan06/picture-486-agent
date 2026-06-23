"""
昴云助手 - 检索链路模块
负责完整的检索流程：查询重写 → 向量化 → 检索 → 重排 → 应答生成
"""
from typing import List

from langchain_core.documents import Document
from langsmith import traceable

from app.agent.config.chroma_config import chroma_vector_store
from app.agent.config import workflow_config as config, parse_filters
from app.agent.model.model import multi_embedding_model, deepseek_chat_model, rerank_model
# 改动：从本地 prompts 目录导入提示词
from app.agent.rag.prompts import (
    get_image_rewrite_prompt,
    get_text_rewrite_prompt,
    get_response_generation_prompt,
    get_no_result_response,
    get_fallback_response
)


# ===================== 查询重写节点 =====================

@traceable(run_type="chain", name="query_rewriter")  # 改动：添加 LangSmith 追踪
async def query_rewriter(state: dict) -> dict:
    """
    节点2：查询重写 + 数量提取
    调用 deepseek 文本模型将用户自然语言改写为检索关键词，并提取期望返回的图片数量
    Returns:
        rewritten_query: 重写后的检索关键词
        expected_count: 用户期望返回的图片数量（1-10，默认3）
    """
    query = state.get("user_input", "").strip()
    image_url = state.get("image_url")  # 【新增】获取图片URL

    # 改动：根据是否有图片调整提示词，使用提示词模块
    if image_url:
        # 图文检索：强调相似性
        prompt = get_image_rewrite_prompt(query)
    else:
        # 纯文本检索：不需要强调相似性
        prompt = get_text_rewrite_prompt(query)
    
    try:
        resp = await deepseek_chat_model.ainvoke(prompt)
        result = resp.content.strip()
        
        # 解析输出
        rewritten = query  # 默认值
        expected_count = config.DEFAULT_EXPECTED_COUNT  # 改动：使用配置常量
        
        for line in result.split('\n'):
            line = line.strip()
            if line.startswith('关键词:'):
                rewritten = line.replace('关键词:', '').strip()
            elif line.startswith('数量:'):
                try:
                    count_str = line.replace('数量:', '').strip()
                    # 处理中文数字
                    chinese_nums = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
                                   '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                    if count_str in chinese_nums:
                        expected_count = chinese_nums[count_str]
                    else:
                        expected_count = int(count_str)
                    # 限制范围 1-10
                    expected_count = max(1, min(10, expected_count))
                except (ValueError, KeyError):
                    expected_count = 3  # 解析失败使用默认值
    except Exception as e:
        rewritten = query
        expected_count = 3

    return {"rewritten_query": rewritten, "expected_count": expected_count}


# ===================== 多模态向量化节点 =====================

@traceable(run_type="embed", name="multimodal_embedder")  # 改动：添加 LangSmith 追踪
async def multimodal_embedder(state: dict) -> dict:
    """
    节点3：向量化
    - 图文检索：调用 embed_multimodal（重写后关键词 + 图片融合向量）
    - 文本检索：调用 embed_query（重写后关键词向量）
    保证所有检索路径使用同一向量空间
    """
    intent = state["intent"]
    query = state.get("rewritten_query") or state.get("user_input", "").strip()
    image_url = state.get("image_url")
    embedding = None

    try:
        if intent == "image_retrieval" and image_url:
            # 多模态融合嵌入
            embedding = multi_embedding_model.embed_multimodal(query, image_url)
        elif intent == "text_retrieval":
            # 纯文本嵌入
            embedding = multi_embedding_model.embed_query(query)
    except Exception as e:
        embedding = None

    return {"query_embedding": embedding}


# ===================== 向量检索节点 =====================

@traceable(run_type="retriever", name="vector_retriever")  # 改动：添加 LangSmith 追踪
async def vector_retriever(state: dict) -> dict:
    """
    节点4：向量检索 + 元数据过滤
    - 文本检索：使用 LangChain MMR Retriever（内置嵌入+MMR，一步到位）
    - 图文检索：使用预计算的多模态向量直接查询 Chroma
    """
    intent = state["intent"]
    query = state.get("rewritten_query") or state.get("user_input", "").strip()
    embedding = state.get("query_embedding")
    filters = state.get("filters")
    expected_count = state.get("expected_count", 3)  # 【新增】获取用户期望数量
    final_docs: List[Document] = []

    # 构建过滤参数（改动：使用全局 parse_filters 函数）
    where_filter = parse_filters(filters)

    try:
        if intent == "text_retrieval":
            # 文本检索：使用 LangChain MMR Retriever（自动嵌入 + MMR 重排）
            # 【优化】根据用户期望数量动态调整 candidate_k
            candidate_k = expected_count * 3  # 例如用户要5张，则 MMR 先筛选出 15 个候选
            
            search_kwargs = {
                "k": candidate_k,
                "fetch_k": max(candidate_k * 2, 20),  # MMR 内部候选集，至少 20 个
                "lambda_mult": config.LAMBDA_MULT,  # 改动：使用配置常量
            }
            if where_filter:
                search_kwargs["filter"] = where_filter

            mmr_retriever = chroma_vector_store.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs
            )
            final_docs = mmr_retriever.invoke(query)

        elif intent == "image_retrieval" and embedding:
            # 图文检索：使用预计算的多模态向量直接查询 Chroma
            # 【优化】根据用户期望数量动态调整 n_results
            retrieve_count = expected_count * 3  # 为后续 reranker 提供充足候选
            results = chroma_vector_store._collection.query(
                query_embeddings=[embedding],
                n_results=retrieve_count,
                where=where_filter,
                include=['documents', 'metadatas', 'distances']
            )
            # 改动：删除无效 for 循环，仅保留列表推导式构造 final_docs
            final_docs = [
                Document(
                    page_content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i]
                )
                for i in range(len(results['ids'][0]))
            ]

    except Exception as e:
        pass

    return {"retrieved_docs": final_docs}


# ===================== 重排序节点 =====================

@traceable(run_type="chain", name="reranker")  # 改动：添加 LangSmith 追踪
async def reranker(state: dict) -> dict:
    """
    节点5：多模态重排序
    - 纯文本检索：调用 DashScope qwen3-vl-rerank 对检索结果进行语义重排
    - 图文检索：跳过重排，直接使用向量检索结果（已融合图片特征）
    
    【重要】Qwen3-VL-Rerank 输入模态仅为文本，无法接收图片，因此图文检索时不使用
    【优化】重排序时使用 metadata['introduction'] + metadata['name'] 构建文本，
           而非 page_content，确保即使 page_content 格式不统一也能正确重排
    """
    docs = state.get("retrieved_docs", [])
    intent = state["intent"]
    query = state.get("rewritten_query") or state.get("user_input", "").strip()
    expected_count = state.get("expected_count", 3)
    
    if not docs:
        return {"reranked_docs": []}
    
    # 【关键修改】图文检索时跳过重排，直接使用向量检索结果
    if intent == "image_retrieval":
        # 直接返回前 expected_count 个（向量检索已按相似度排序）
        return {"reranked_docs": docs[:expected_count]}
    
    # 纯文本检索：使用 LLM 重排
    if len(docs) <= expected_count:
        return {"reranked_docs": docs}
    
    try:
        # 【优化】构建重排序文本：优先使用 introduction，其次使用 name
        doc_texts = []
        for doc in docs:
            name = doc.metadata.get("name", "")
            introduction = doc.metadata.get("introduction", "").strip()
            
            # 如果有简介，使用「名称 + 简介」；否则只用名称
            if introduction:
                doc_texts.append(f"{name}：{introduction}")
            elif name:
                doc_texts.append(name)
            else:
                # 兜底：使用 page_content
                doc_texts.append(doc.page_content)
        
        # 调用重排序模型（使用用户期望数量）
        ranked_indices = rerank_model.rerank(query, doc_texts, top_n=expected_count)
        
        # 根据重排索引重新排序文档
        reranked_docs = [docs[idx] for idx in ranked_indices if idx < len(docs)]
        
        return {"reranked_docs": reranked_docs}
        
    except Exception as e:
        # 降级：返回原始检索结果的前 expected_count 个
        return {"reranked_docs": docs[:expected_count]}


# ===================== 应答生成节点 =====================

@traceable(run_type="chain", name="response_generator")  # 改动：添加 LangSmith 追踪
async def response_generator(state: dict) -> dict:
    """
    节点6：应答生成
    调用 deepseek 文本模型整理检索结果，生成用户友好的回复
    """
    docs = state.get("reranked_docs", [])
    user_q = state.get("user_input", "").strip()

    if not docs:
        # 改动：使用提示词模块
        return {
            "response_text": get_no_result_response(),
            "response_images": []
        }

    # 提取图片URL列表（改动：metadata.get 避免 KeyError）
    img_list = [doc.metadata.get("image_url") for doc in docs if doc.metadata.get("image_url")]

    # 【关键修复】构建提示词时优先使用 metadata['introduction']，没有则不添加描述
    context_lines = []
    for i, doc in enumerate(docs):
        name = doc.metadata.get("name", "未知")
        introduction = doc.metadata.get("introduction", "").strip()
        
        # 如果有简介，使用「名称 + 简介」格式；否则只写名称
        if introduction:
            context_lines.append(f"[{i+1}] 图片名称：{name}，简介：{introduction}")
        else:
            context_lines.append(f"[{i+1}] 图片名称：{name}")
    
    context = "\n".join(context_lines)
    
    # 改动：使用提示词模块
    prompt = get_response_generation_prompt(user_q, context)

    try:
        resp = await deepseek_chat_model.ainvoke(prompt)
        response_text = resp.content
    except Exception as e:
        # 改动：使用提示词模块的降级回复
        response_text = get_fallback_response(len(docs))

    return {
        "response_text": response_text,
        "response_images": img_list
    }
