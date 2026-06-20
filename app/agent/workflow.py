import operator
from typing import List, Optional, Annotated, Sequence

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from langsmith import traceable
from typing_extensions import TypedDict

from app.agent.chroma import chroma_vector_store
from app.agent.config import workflow_config as config, parse_filters
from app.agent.model.model import multi_embedding_model, deepseek_chat_model, rerank_model
from app.agent.prompts import (
    get_intent_recognition_prompt,
    get_image_rewrite_prompt,
    get_text_rewrite_prompt,
    get_system_prompt,
    get_fallback_chat_reply,
    get_response_generation_prompt,
    get_no_result_response,
    get_fallback_response,
    get_analysis_prompt_template
)
from app.common.logger import logger
from app.config.redis_config import checkpointer


# ===================== 1. 状态定义（改动：仅保留 messages 标准字段）=====================

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
        "analysis_result": None
    }


# ===================== 出口节点 =====================


def _format_output(state: dict) -> dict:
    """
    出口节点:将 response_text + response_images 转为 AIMessage (LangChain 标准格式)
    Args:
        state: 包含 response_text, response_images 的字典
    Returns:
        {"messages": [AIMessage(content=[...])]} 使用标准图文格式
    """
    # 构建标准 LangChain 图文消息格式
    content_parts = []
    
    response_text = state.get("response_text")
    if response_text:
        content_parts.append({"type": "text", "text": response_text})
    
    # 添加图片URL (使用 LangChain 标准格式)
    if state.get("response_images"):
        for img_url in state["response_images"]:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
    
    # 如果没有任何内容,使用默认文本
    if not content_parts:
        content_parts.append({"type": "text", "text": "抱歉,没有找到相关图片"})
    
    return {"messages": [AIMessage(content=content_parts)]}


def _direct_chat(state: dict) -> dict:
    """
    闲聊节点：使用完整消息历史进行多轮对话（优化：支持上下文记忆）
    Args:
        state: 包含 messages 的字典
    Returns:
        response_text, response_images
    """
    # 【改动】获取完整消息历史，而非仅 user_input
    messages = list(state.get("messages", []))
    
    # 【新增】在消息列表开头插入系统提示词，定义 AI 身份和行为规范
    system_prompt = get_system_prompt()
    
    # 构建完整的消息列表（系统提示 + 历史对话）
    full_messages = [SystemMessage(content=system_prompt)] + messages
    
    try:
        # 【改动】传入包含系统提示的完整消息列表
        resp = deepseek_chat_model.invoke(full_messages)
        reply_text = resp.content.strip() if resp.content else None
    except Exception as e:
        # 改动：记录异常并返回 fallback 回复
        logger.error(f"[闲聊节点] LLM调用失败: {str(e)}")
        reply_text = get_fallback_chat_reply()
    
    # 确保 response_text 不为 None
    if not reply_text:
        reply_text = get_fallback_chat_reply()
    
    result = {
        "response_text": reply_text,
        "response_images": [],
    }
    return result


# ===================== 4. 检索节点 =====================

@traceable(run_type="chain", name="intent_recognizer")  # 改动:添加 LangSmith 追踪
def intent_recognizer(state: ChatState) -> dict:
    """
    节点1:从 HumanMessage 提取输入并识别意图 (兼容原生对象 + LangGraph序列化字典消息)
    - 有图片URL → 直接判定为 image_retrieval
    - 无图片 → 调用 deepseek 判断是否为检索意图
    
    支持的输入格式:
    1. 纯文本: HumanMessage(content="你好")
    2. 标准图文: HumanMessage(content=[{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}}])
    3. 序列化字典: {"type": "human", "content": ...} (Checkpoint/Playground场景)
    """
    all_messages = list(state.get("messages", []))
    last_human_msg = None

    # ========== 核心修改：兼容序列化字典 + 原生Message对象，通过type字段判断 ==========
    # 倒序遍历，取最后一条人类消息
    for msg in reversed(all_messages):
        msg_type = None
        # 场景1：序列化后字典消息（线上/Checkpoint/Playground 主流场景）
        if isinstance(msg, dict):
            msg_type = msg.get("type", "").lower()
        # 场景2：内存中原生 Message 对象（本地调试场景）
        elif isinstance(msg, (HumanMessage, AIMessage)):
            msg_type = "human" if isinstance(msg, HumanMessage) else "ai"

        # 匹配人类消息，终止遍历
        if msg_type == "human":
            last_human_msg = msg
            break

    if not last_human_msg:
        return {"intent": "other", "user_input": "", "image_url": None}

    # ========== 核心修改：统一解析 字典/原生对象 的 content 内容 ==========
    content = None
    # 分支1：消息是序列化字典
    if isinstance(last_human_msg, dict):
        content = last_human_msg.get("content")
    # 分支2：消息是原生 Message 对象
    else:
        content = last_human_msg.content

    user_text = ""
    image_urls = []

    # 解析纯文本 content
    if isinstance(content, str):
        user_text = content
    # 解析 LangChain 标准多模态数组 content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    user_text += block.get("text", "")
                elif block_type == "image_url":
                    img_url_data = block.get("image_url", {})
                    if isinstance(img_url_data, dict):
                        url = img_url_data.get("url")
                        if url:
                            image_urls.append(url)
                    elif isinstance(img_url_data, str):
                        image_urls.append(img_url_data)
                    else:
                        url = block.get("url")
                        if url:
                            image_urls.append(url)

    # 去除首尾空白，过滤纯空输入
    user_input = user_text.strip()
    image_url = image_urls[0] if image_urls else None

    # 有图片URL时，调用 DeepSeek 判断是检索、分析还是闲聊
    if image_url:
        # 改动：使用 DeepSeek 模型智能判断图片意图（支持检索/分析/闲聊三种意图）
        intent_prompt = f"""你是意图识别助手。用户上传了一张图片并提问，请判断用户意图：

用户问题：{user_input}

判断标准：
- retrieval（检索）：用户想找相似图片、搜索相关图片、推荐类似内容等
- analysis（分析）：用户想知道图片内容、识别角色/地点、询问这是什么等
- chat（闲聊）：打招呼、评价图片、日常聊天等非检索非分析的对话

只输出一个词：retrieval、analysis 或 chat
不要解释，不要其他内容。"""
        
        try:
            resp = deepseek_chat_model.invoke(intent_prompt)
            intent_result = resp.content.strip().lower()
            
            # 改动：记录 DeepSeek 原始返回结果
            logger.info(f"[图片意图识别] 用户输入: '{user_input}', DeepSeek原始返回: '{intent_result}'")
            
            if "analysis" in intent_result:
                intent = "image_analysis"
            elif "chat" in intent_result:
                intent = "other"  # 闲聊意图
            else:
                intent = "image_retrieval"
            
            # 改动：记录最终判定的意图
            logger.info(f"[图片意图识别] 判定结果: {intent}")
        except Exception as e:
            # 改动：记录异常情况
            logger.error(f"[图片意图识别] DeepSeek调用失败: {str(e)}, 降级为图文检索")
            # 降级：默认视为图文检索
            intent = "image_retrieval"
        
        return {"intent": intent, "user_input": user_input, "image_url": image_url}

    # 无图片 → 调用 LLM 判断意图
    
    # 改动：使用提示词模块
    intent_prompt = get_intent_recognition_prompt(user_input)
    
    try:
        resp = deepseek_chat_model.invoke(intent_prompt)
        intent_result = resp.content.strip().lower()
        
        # 改动：记录纯文本意图识别结果
        logger.info(f"[纯文本意图识别] 用户输入: '{user_input}', DeepSeek原始返回: '{intent_result}'")
        
        # 解析 LLM 返回结果
        if "retrieval" in intent_result:
            intent = "text_retrieval"
        elif "chat" in intent_result:
            intent = "other"
        else:
            # 兜底:默认视为闲聊
            intent = "other"
        
        # 改动：记录最终判定的意图
        logger.info(f"[纯文本意图识别] 判定结果: {intent}")
            
    except Exception as e:
        # 改动：记录异常情况
        logger.error(f"[纯文本意图识别] DeepSeek调用失败: {str(e)}, 降级为关键词匹配")
        # 降级方案:关键词匹配
        if any(kw in user_input for kw in config.SEARCH_KEYWORDS):  # 改动：使用配置常量
            intent = "text_retrieval"
        else:
            intent = "other"

    return {"intent": intent, "user_input": user_input, "image_url": image_url}


@traceable(run_type="chain", name="query_rewriter")  # 改动：添加 LangSmith 追踪
def query_rewriter(state: dict) -> dict:
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
        resp = deepseek_chat_model.invoke(prompt)
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


@traceable(run_type="embed", name="multimodal_embedder")  # 改动：添加 LangSmith 追踪
def multimodal_embedder(state: dict) -> dict:
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


@traceable(run_type="retriever", name="vector_retriever")  # 改动：添加 LangSmith 追踪
def vector_retriever(state: dict) -> dict:
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


@traceable(run_type="chain", name="reranker")  # 改动：添加 LangSmith 追踪
def reranker(state: dict) -> dict:
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


@traceable(run_type="chain", name="response_generator")  # 改动：添加 LangSmith 追踪
def response_generator(state: dict) -> dict:
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
        resp = deepseek_chat_model.invoke(prompt)
        response_text = resp.content
    except Exception as e:
        # 改动：使用提示词模块的降级回复
        response_text = get_fallback_response(len(docs))

    return {
        "response_text": response_text,
        "response_images": img_list
    }


# ===================== 7. 图片分析节点 =====================

@traceable(run_type="chain", name="image_analysis_router")
def image_analysis_router(state: dict) -> dict:
    """
    图片分析二级路由：调用 DeepSeek 判断图片类型
    输出：{"analysis_type": "attraction" | "anime_analysis" | "common"}
    """
    user_input = state.get("user_input", "")
    
    # 构建提示词，要求 LLM 仅输出三个字段名之一
    prompt = f"""你是一个图片分类助手。用户上传图片并提问，请判断属于以下哪一类：

- attraction：用户上传风景图，询问图中是什么地方/景点
- anime_analysis：用户上传动漫图，询问图中是哪个动漫的角色
- common：用户上传任意图片，要求根据图片提取信息或撰写文案

用户问题：{user_input}

仅允许输出 `attraction`、`anime_analysis` 或 `common` 这三个字段名之一，不要输出其他内容。
"""
    
    try:
        resp = deepseek_chat_model.invoke(prompt)
        analysis_type = resp.content.strip().lower()
        if analysis_type not in ["attraction", "anime_analysis", "common"]:
            analysis_type = "common"  # 兜底
    except Exception as e:
        analysis_type = "common"  # 异常兜底
    
    return {"analysis_type": analysis_type}


@traceable(run_type="chain", name="anime_analyzer")
def anime_analyzer(state: dict) -> dict:
    """
    动漫分析节点（直接调用工具，避免 Agent 循环和过度搜索）
    
    Args:
        state: 包含 image_url, user_input 的字典
    Returns:
        analysis_result: 标准化的分析结果
    """
    from app.agent.tools import anime_analysis as anime_tool
    
    image_url = state.get("image_url")
    
    if not image_url:
        return {
            "analysis_result": {
                "error": "缺少图片URL",
                "work": "未知作品",
                "character": "未知角色",
                "description": "无法分析，请提供图片"
            }
        }
    
    try:
        # 步骤1：调用识图工具获取基本信息
        logger.info(f"[anime_analyzer] 开始识图: {image_url[:50]}...")
        raw_result = anime_tool.invoke({"image_url": image_url})
        
        # 调试：打印原始结果类型和内容
        logger.info(f"[anime_analyzer] 工具返回类型: {type(raw_result)}")
        logger.info(f"[anime_analyzer] 工具返回内容: {raw_result}")
        
        # 检查是否为错误信息
        if isinstance(raw_result, str) and ("请求参数错误" in raw_result or "超时" in raw_result or "失败" in raw_result):
            logger.warning(f"[anime_analyzer] 识图失败: {raw_result}")
            return {
                "analysis_result": {
                    "type": "anime_analysis",
                    "character_name": "未识别",
                    "work_name": "未识别",
                    "description": f"识图失败：{raw_result}",
                    "confidence": 0
                }
            }
        
        # 解析字符串格式："角色名 | 作品名"
        if not isinstance(raw_result, str) or "|" not in raw_result:
            raise ValueError(f"识图工具返回格式异常: {raw_result}")
        
        parts = raw_result.split("|")
        if len(parts) != 2:
            raise ValueError(f"识图工具返回格式异常，期望'角色名 | 作品名'，实际: {raw_result}")
        
        character_jp = parts[0].strip()
        work_jp = parts[1].strip()
        confidence = 0.95  # 默认置信度（工具不返回）
        
        logger.info(f"[anime_analyzer] 识图结果: {character_jp} | {work_jp} (置信度: {confidence})")
        
        # 如果置信度太低，直接返回
        if confidence < 0.5:
            return {
                "analysis_result": {
                    "type": "anime_analysis",
                    "character_name": "未识别",
                    "character_name_jp": character_jp,
                    "work_name": "未识别",
                    "work_name_jp": work_jp,
                    "description": f"图片识别置信度较低 ({confidence:.2%})，可能是 {character_jp} 来自 {work_jp}",
                    "confidence": confidence
                }
            }
        
        # 步骤2：翻译日文为中文（单次LLM调用）
        if character_jp and work_jp:
            translated = _translate_anime_info(character_jp, work_jp)
        else:
            translated = {"character": "未知角色", "work": "未知作品"}
        
        # 步骤3：生成简要介绍（不调用 Tavily，直接用 LLM）
        description = _generate_character_description(
            translated.get("character", character_jp),
            translated.get("work", work_jp)
        )
        
        # 构建标准化输出
        analysis_result = {
            "type": "anime_analysis",
            "character_name": translated.get("character", character_jp),
            "character_name_jp": character_jp,
            "work_name": translated.get("work", work_jp),
            "work_name_jp": work_jp,
            "description": description,
            "confidence": confidence
        }
        
        logger.info(f"[anime_analyzer] 分析完成: {analysis_result['character_name']} - {analysis_result['work_name']}")
        
    except Exception as e:
        logger.error(f"[anime_analyzer] 分析失败: {str(e)}")
        analysis_result = {
            "error": str(e),
            "type": "anime_analysis",
            "character_name": "未知角色",
            "work_name": "未知作品",
            "description": "分析失败，请稍后重试"
        }
    
    return {"analysis_result": analysis_result}


def _translate_anime_info(character_jp: str, work_jp: str) -> dict:
    """
    使用 DeepSeek 翻译日文动漫信息
    
    Args:
        character_jp: 日文角色名
        work_jp: 日文作品名
        
    Returns:
        包含中文字段名的字典
    """
    from app.utils.api_utils import safe_parse_json
    
    prompt = f"""请将以下日文动漫信息翻译成中文：

角色名（日文）：{character_jp}
作品名（日文）：{work_jp}

要求：
1. 只返回 JSON 格式，不要其他内容
2. 格式：{{"character": "中文角色名", "work": "中文作品名"}}
3. 如果不知道官方译名，使用常见译名或音译
4. 保持简洁，不要解释
"""
    
    try:
        resp = deepseek_chat_model.invoke(prompt)
        result = safe_parse_json(resp.content)
        logger.info(f"[_translate_anime_info] 翻译结果: {result}")
        return result
    except Exception as e:
        logger.warning(f"[_translate_anime_info] 翻译失败: {str(e)}")
        return {"character": character_jp, "work": work_jp}


def _generate_character_description(character: str, work: str) -> str:
    """
    生成角色简要介绍（不调用外部搜索，节省token）
    
    Args:
        character: 角色名
        work: 作品名
        
    Returns:
        50-100字的角色介绍
    """
    prompt = f"""请简要介绍动漫角色 {character}（来自《{work}》）。

要求：
1. 50-80字简短介绍
2. 包含角色身份、性格特点
3. 如果不确定具体信息，就说"暂无详细信息"
4. 语气友好自然
"""
    
    try:
        resp = deepseek_chat_model.invoke(prompt)
        description = resp.content.strip()
        logger.info(f"[_generate_character_description] 生成描述: {description[:50]}...")
        return description
    except Exception as e:
        logger.warning(f"[_generate_character_description] 生成失败: {str(e)}")
        return f"{character} 是 {work} 中的角色，暂无详细信息。"


@traceable(run_type="chain", name="analysis_response_formatter")  # 改动：添加 LangSmith 追踪
def analysis_response_formatter(state: dict) -> dict:
    """
    通用图片分析结果格式化节点（改动：统一处理所有分析类型的结果）
    - 接收所有分析类型的 JSON 结果（anime_analysis | attraction | common）
    - 根据 analysis_type 动态调整提示词风格
    - 生成用户友好的回复
    
    Args:
        state: 包含 analysis_result, analysis_type 的字典
    Returns:
        response_text, response_images
    """
    analysis_result = state.get("analysis_result")
    analysis_type = state.get("analysis_type", "common")
    
    # 校验分析结果
    if not analysis_result or (isinstance(analysis_result, dict) and analysis_result.get("error")):
        return {
            "response_text": "😔 抱歉，图片分析失败，请稍后重试～",
            "response_images": []
        }
    
    # 改动：使用统一的提示词模板函数，根据分析类型动态生成提示词
    prompt = get_analysis_prompt_template(analysis_type, analysis_result)
    
    try:
        resp = deepseek_chat_model.invoke(prompt)
        response_text = resp.content.strip()
    except Exception as e:
        # 改动：记录异常并返回友好提示
        logger.error(f"[图片分析格式化] LLM调用失败: {str(e)}")
        response_text = "😊 图片分析完成啦～ 但生成回复时出了点小问题，请稍后再试！"
    
    return {
        "response_text": response_text,
        "response_images": []
    }


# TODO: 实现风景识别 Agent
def _attraction_placeholder(state: dict) -> dict:
    """
    风景识别占位节点（改动：返回标准JSON格式，供统一格式化节点处理）
    Returns:
        analysis_result: 标准JSON格式的分析结果
    """
    # 改动：返回标准JSON格式，而非硬编码文本
    return {
        "analysis_result": {
            "type": "attraction",
            "name": "示例景点名称",
            "location": "示例位置",
            "description": "示例描述",
            "note": "此功能正在开发中，当前为占位数据"
        }
    }


# TODO: 实现通用图片分析 Agent  
def _common_placeholder(state: dict) -> dict:
    """
    通用图片分析占位节点（改动：返回标准JSON格式，供统一格式化节点处理）
    Returns:
        analysis_result: 标准JSON格式的分析结果
    """
    # 改动：返回标准JSON格式，而非硬编码文本
    return {
        "analysis_result": {
            "type": "common",
            "content": "示例分析内容",
            "tags": ["标签1", "标签2"],
            "note": "此功能正在开发中，当前为占位数据"
        }
    }


def route_after_image_analysis(state: dict) -> str:
    """
    图片分析二级路由（根据 analysis_type 分发到不同处理节点）
    
    Returns:
        下一步要执行的节点名称
    """
    analysis_type = state.get("analysis_type", "anime_analysis")
    
    # 目前只有动漫分析有实现，其他类型暂时也走动漫分析或降级
    if analysis_type == "anime_analysis":
        return "anime_analyzer"
    else:
        # TODO: 风景和通用分析暂未实现，暂时降级为动漫分析或直接返回
        logger.warning(f"[route_after_image_analysis] 未实现的类型: {analysis_type}，降级为动漫分析")
        return "anime_analyzer"


# ===================== 5. 路由函数 =====================

def route_after_intent(state: dict) -> str:
    """意图路由：根据意图分发到不同链路"""
    intent = state.get("intent", "other")
    if intent in ("text_retrieval", "image_retrieval"):
        return "retrieval_chain"
    elif intent == "image_analysis":
        return "image_analysis_chain"  # 改动：新增图片分析分支
    else:
        return "chat_chain"  # 闲聊


# ===================== 6. 构建 & 编译工作流（改动：单张图，所有节点可见）=====================

def build_chat_workflow():
    """构建并编译 LangGraph 单张对话工作流"""
    builder = StateGraph(ChatState)

    # === 注册所有节点 ===
    builder.add_node("intent_recognizer", intent_recognizer)
    builder.add_node("query_rewriter", query_rewriter)
    builder.add_node("multimodal_embedder", multimodal_embedder)
    builder.add_node("vector_retriever", vector_retriever)
    builder.add_node("reranker", reranker)
    builder.add_node("response_generator", response_generator)
    builder.add_node("_direct_chat", _direct_chat)
    builder.add_node("_format_output", _format_output)
    
    # 图片分析相关节点
    builder.add_node("image_analysis_router", image_analysis_router)
    builder.add_node("anime_analyzer", anime_analyzer)
    builder.add_node("analysis_response_formatter", analysis_response_formatter)
    builder.add_node("_attraction_placeholder", _attraction_placeholder)  # TODO
    builder.add_node("_common_placeholder", _common_placeholder)  # TODO

    # === 设置入口 ===
    builder.set_entry_point("intent_recognizer")

    # === 条件边：意图路由 ===
    builder.add_conditional_edges(
        "intent_recognizer",
        route_after_intent,
        {
            "retrieval_chain": "query_rewriter",   # 有检索意图 → 进入检索链路
            "chat_chain": "_direct_chat",           # 无检索意图 → 闲聊回复
            "image_analysis_chain": "image_analysis_router",  # 改动：修正键名为图片分析分支
        }
    )

    # === 检索链路（固定边）===
    builder.add_edge("query_rewriter", "multimodal_embedder")
    builder.add_edge("multimodal_embedder", "vector_retriever")
    builder.add_edge("vector_retriever", "reranker")
    builder.add_edge("reranker", "response_generator")
    builder.add_edge("response_generator", "_format_output")

    # === 闲聊链路 ===
    builder.add_edge("_direct_chat", "_format_output")
    
    # === 图片分析链路 ===
    # 简化路由：所有图片分析类型暂时都走 anime_analyzer
    builder.add_edge("image_analysis_router", "anime_analyzer")
    
    # TODO: 未来扩展时可以添加条件边
    # builder.add_conditional_edges(
    #     "image_analysis_router",
    #     route_after_image_analysis,
    #     {
    #         "anime_analyzer": "anime_analyzer",
    #         "attraction_placeholder": "_attraction_placeholder",
    #         "common_placeholder": "_common_placeholder",
    #     }
    # )
    
    # 动漫分析节点 → 格式化节点
    builder.add_edge("anime_analyzer", "analysis_response_formatter")
    
    # TODO: 预留分支（当前未使用）
    # builder.add_edge("_attraction_placeholder", "analysis_response_formatter")
    # builder.add_edge("_common_placeholder", "analysis_response_formatter")
    
    # 格式化节点到出口
    builder.add_edge("analysis_response_formatter", "_format_output")

    # === 出口 ===
    builder.add_edge("_format_output", END)

    return builder.compile(checkpointer=checkpointer)
    # return builder.compile()

# LangSmith / langgraph.json 指向此实例
compiled_graph = build_chat_workflow()

# 改动：构建标准 Runnable 接口，供 LangSmith Playground 直接调试
def _invoke_workflow(input_data: dict) -> dict:
    """直接调用编译后的图"""
    return compiled_graph.invoke(input_data)

chat_runnable = RunnableLambda(_invoke_workflow)

# 兼容旧入口名称
chat_graph = compiled_graph
