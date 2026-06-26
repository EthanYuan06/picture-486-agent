"""
昴云助手 - 检索链路模块
负责完整的检索流程：查询重写 → 向量化 → 检索 → 重排 → 应答生成
"""
from typing import List

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable

from app.agent.config.chroma_config import chroma_vector_store
from app.agent.config import workflow_config as config, parse_filters
from app.agent.model.model import multi_embedding_model, deepseek_chat_model, rerank_model
from app.agent.schemas import QueryRewriteResult
from app.common.logger import logger  # 【新增】导入日志模块
# 改动：从本地 prompts 目录导入提示词
from app.agent.rag.prompts import (
    get_image_rewrite_prompt,
    get_text_rewrite_prompt,
    get_response_generation_prompt,
    get_no_result_response,
    get_fallback_response
)

# 初始化查询重写 Parser + Prompt Template
query_rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是查询重写助手。
将用户自然语言改写为适合向量检索的关键词，并提取期望返回的图片数量。

要求：
1. 关键词要简洁、核心语义明确，用空格分隔（例如："女孩 呆毛 挡雨"）
2. 数量范围 1-10，默认 3
3. keywords 字段必须是空格分隔的字符串，不是数组
4. 只返回 JSON 格式"""),
    ("human", "{user_input}")
])
query_rewrite_parser = JsonOutputParser(pydantic_object=QueryRewriteResult)
query_rewrite_chain = query_rewrite_prompt | deepseek_chat_model | query_rewrite_parser


# ===================== 查询重写节点 =====================

@traceable(run_type="chain", name="query_rewriter")  # 改动：添加 LangSmith 追踪
async def query_rewriter(state: dict) -> dict:
    """
    节点2：查询重写 + 数量提取（Output Parser 版本）
    调用 deepseek 文本模型将用户自然语言改写为检索关键词，并提取期望返回的图片数量
    Returns:
        rewritten_query: 重写后的检索关键词
        expected_count: 用户期望返回的图片数量（1-10，默认3）
    """
    query = state.get("user_input", "").strip()
    image_url = state.get("image_url")  # 【新增】获取图片URL

    try:
        # 使用 Chain 自动解析和校验
        result = await query_rewrite_chain.ainvoke({"user_input": query})
        
        # 【修复】JsonOutputParser 返回 dict，不是 Pydantic 对象
        keywords = result.get("keywords", query)
        expected_count = result.get("expected_count", config.DEFAULT_EXPECTED_COUNT)
        
        logger.info(f"[查询重写] 关键词: {keywords}, 数量: {expected_count}")
        
        return {
            "rewritten_query": keywords,
            "expected_count": expected_count
        }
    except Exception as e:
        logger.warning(f"[查询重写] Parser 失败，使用原始查询: {str(e)}")
        # 降级：使用原始查询
        return {
            "rewritten_query": query,
            "expected_count": config.DEFAULT_EXPECTED_COUNT
        }


# ===================== 多模态向量化节点 =====================

@traceable(run_type="chain", name="multimodal_embedder")  # 【修复】LangSmith 不支持 embed 类型，改为 chain
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
            logger.info(f"[向量化] 意图={intent}, 查询='{query[:50]}...', 执行多模态融合嵌入")
            embedding = multi_embedding_model.embed_multimodal(query, image_url)
        elif intent == "text_retrieval":
            # 纯文本嵌入
            logger.info(f"[向量化] 意图={intent}, 查询='{query[:50]}...', 执行纯文本嵌入")
            embedding = multi_embedding_model.embed_query(query)
        
        # 【新增】记录向量化结果
        if embedding:
            logger.info(f"[向量化] ✓ 成功，向量维度={len(embedding)}, 前5维={embedding[:5]}")
        else:
            logger.warning(f"[向量化] ✗ 失败，embedding=None")
            
    except Exception as e:
        logger.error(f"[向量化]  异常: {str(e)}")
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
    
    # 【新增】记录检索开始
    logger.info(f"[向量检索] 开始检索, 意图={intent}, 查询='{query[:50]}...', embedding={'有' if embedding else '无'}")

    try:
        if intent == "text_retrieval":
            # 文本检索：使用 LangChain MMR Retriever（自动嵌入 + MMR 重排）
            # 【关键优化】扩大候选集，为复杂查询（如比喻语义）提供更多召回机会
            candidate_k = expected_count * 10  # 例如用户要3张，则 MMR 先筛选出 30 个候选
            
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
            
            # 【新增】记录 MMR 检索结果
            logger.info(f"[向量检索] MMR 检索完成, 返回{len(final_docs)}个文档")

        elif intent == "image_retrieval" and embedding:
            # 图文检索：使用预计算的多模态向量直接查询 Chroma
            # 【关键优化】扩大候选集，为复杂查询（如比喻语义）提供更多召回机会
            retrieve_count = expected_count * 10  # 为后续 reranker 提供充足候选
            results = chroma_vector_store._collection.query(
                query_embeddings=[embedding],
                n_results=retrieve_count,
                where=where_filter,
                include=['documents', 'metadatas', 'distances']
            )
            
            # 【新增】记录相似度分数用于评估
            distances = results['distances'][0]
            logger.info(f"[向量检索] 意图={intent}, 查询='{query[:50]}...', 检索到{len(results['ids'][0])}个候选")
            logger.info(f"[向量检索] Top-5 相似度详情:")
            for i in range(min(5, len(distances))):
                similarity = 1.0 / (1.0 + distances[i])
                name = results['metadatas'][0][i].get('name', '')
                logger.info(f"  [{i}] {name}: 距离={round(distances[i], 4)}, 相似度={round(similarity, 4)}")
            
            # 改动：删除无效 for 循环，仅保留列表推导式构造 final_docs
            final_docs = [
                Document(
                    page_content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i]
                )
                for i in range(len(results['ids'][0]))
            ]

    except Exception as e:
        logger.error(f"[向量检索] ✗ 异常: {str(e)}")
        pass
    
    # 【新增】记录最终检索结果
    if not final_docs:
        logger.warning(f"[向量检索] ️ 未检索到任何文档")
    else:
        logger.info(f"[向量检索] ✓ 检索到{len(final_docs)}个候选文档")

    return {"retrieved_docs": final_docs}


# ===================== 重排序节点 =====================

@traceable(run_type="chain", name="reranker")  # 改动：添加 LangSmith 追踪
async def reranker(state: dict) -> dict:
    """
    节点5：多模态重排序
    - 纯文本检索：调用 DashScope qwen3-vl-rerank 对检索结果进行语义重排
    - 图文检索：调用 qwen3-vl-rerank 的多模态能力，结合用户图片特征进行跨模态重排
    
    【核心优势】图文检索时，重排序模型能同时理解「用户图片 + 查询文本」与「候选图片元数据」的语义关联
    【优化】重排序时使用 metadata['introduction'] + metadata['name'] 构建文本，
           而非 page_content，确保即使 page_content 格式不统一也能正确重排
    
    【新增】记录重排前后的顺序变化，用于评估重排序效果
    """
    docs = state.get("retrieved_docs", [])
    intent = state["intent"]
    query = state.get("rewritten_query") or state.get("user_input", "").strip()
    image_url = state.get("image_url")  # 【新增】获取图片URL
    expected_count = state.get("expected_count", 3)
    
    if not docs:
        return {"reranked_docs": []}
    
    # 【新增】记录重排前的 Top-3
    logger.info(f"[重排序] 意图={intent}, 查询='{query[:50]}...', 候选数={len(docs)}, 期望返回={expected_count}")
    logger.info(f"[重排序] === 重排前 Top-{min(3, len(docs))} ===")
    for i, doc in enumerate(docs[:3]):
        name = doc.metadata.get('name', '未知')
        intro = doc.metadata.get('introduction', '')[:30]
        logger.info(f"  [{i}] {name} ({intro}...)")
    
    # 【关键修改】不再跳过图文检索的重排序，使用多模态重排序
    if len(docs) <= expected_count:
        logger.info(f"[重排序] 候选数({len(docs)}) <= 期望数({expected_count})，跳过重排")
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
        
        # 【关键修改】构建带图片URL的文档列表（纯文本和图文检索统一使用）
        documents_with_images = []
        for doc in docs:
            name = doc.metadata.get("name", "")
            introduction = doc.metadata.get("introduction", "").strip()
            image_url = doc.metadata.get("image_url", "")
            
            # 构建文档文本描述
            if introduction:
                doc_text = f"{name}：{introduction}"
            elif name:
                doc_text = name
            else:
                doc_text = doc.page_content
            
            # 构建带图片的文档对象
            documents_with_images.append({
                "text": doc_text,
                "image": image_url if image_url else ""  # 如果没有图片URL传空字符串
            })
        
        # 【关键修改】根据意图选择重排序方法
        if intent == "image_retrieval" and image_url:
            # 图文检索：传入用户图片URL
            logger.info(f"[重排序] 使用多模态重排序（图文），用户图片: {image_url[:80]}...")
            ranked_indices = rerank_model.rerank_multimodal(
                query, documents_with_images, 
                user_image_url=image_url, 
                top_n=expected_count
            )
        else:
            # 纯文本检索：不传用户图片，但 documents 仍包含候选图片URL
            logger.info(f"[重排序] 使用多模态重排序（纯文本），候选图片数={len(documents_with_images)}")
            ranked_indices = rerank_model.rerank_multimodal(
                query, documents_with_images, 
                user_image_url=None, 
                top_n=expected_count
            )
        
        # 【新增】记录重排后的 Top-3
        logger.info(f"[重排序] === 重排后 Top-{len(ranked_indices)} ===")
        for rank_idx, orig_idx in enumerate(ranked_indices[:3]):
            doc = docs[orig_idx]
            name = doc.metadata.get('name', '未知')
            intro = doc.metadata.get('introduction', '')[:30]
            logger.info(f"  [{rank_idx}] {name} ({intro}...) [原位置={orig_idx}]")
        
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
