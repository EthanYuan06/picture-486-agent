"""
昴云助手 - 工作流编排模块
仅负责 LangGraph 图的构建、节点注册、边连接和编译
所有业务逻辑已拆分到独立模块
"""
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END

# 改动：从独立模块导入状态定义
from app.agent.state import ChatState, init_chat_state

# 改动：从独立模块导入所有业务节点
from app.agent.routing import intent_recognizer, route_after_intent
from app.agent.retrieval_chain import (
    query_rewriter,
    multimodal_embedder,
    vector_retriever,
    reranker,
    response_generator
)
from app.agent.chat_chain import _direct_chat
from app.agent.output_nodes import _format_output
from app.agent.image_analysis import (
    image_analysis_router,
    anime_analyzer,
    analysis_response_formatter,
    _attraction_placeholder,
    _common_placeholder
)

# 改动：导入 Redis checkpointer
from app.config.redis_config import checkpointer


# ===================== 工作流构建函数 =====================

def build_chat_workflow():
    """构建并编译 LangGraph 单张对话工作流"""
    builder = StateGraph(ChatState)

    # === 注册所有节点（改动：节点实现已从独立模块导入）===
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
