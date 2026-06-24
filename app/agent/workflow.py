"""
昴云助手 - 工作流编排模块
仅负责 LangGraph 图的构建、节点注册、边连接和编译
所有业务逻辑已拆分到独立模块
"""
import os
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage  # 改动：新增导入用于错误处理
from langgraph.graph import StateGraph, END
from app.common.logger import logger

# 改动：从独立模块导入状态定义
from app.agent.state import ChatState

# 改动：从RAG模块导入意图识别和检索链路节点
from app.agent.rag import (
    intent_recognizer,
    route_after_intent,
    query_rewriter,
    multimodal_embedder,
    vector_retriever,
    reranker,
    response_generator
)
# 改动：从闲聊业务模块导入闲聊节点
from app.agent.chat.nodes.direct_chat import _direct_chat
from app.agent.public_nodes.output_nodes import _format_output
# 改动：从图片内容分析模块导入状态和子图构建器
from app.agent.image_analysis import (
    ImageAnalysisState,
    build_subgraph as build_image_analysis_subgraph,
)
# 改动：从图片内容分析模块导入节点（向后兼容，供主图直接使用）
from app.agent.image_analysis import (
    image_analysis_router,
    route_after_image_analysis,
)
# 改动：从智能上传模块导入节点
from app.agent.image_upload import (
    image_upload_analyzer,
    image_upload_callback
)

# 改动：导入 Redis checkpointer
from app.config.redis_config import checkpointer


# ===================== 错误处理节点 =====================

def error_handler(state: dict) -> dict:
    """
    错误处理节点：当意图识别或其他节点发生错误时，返回友好提示
    """
    error_message = state.get("error_message", " 系统繁忙，请稍后重试")
    return {
        "response_text": error_message,
        "messages": [AIMessage(content=error_message)]
    }


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
    # 改动：注册 image_analysis_router 作为主图入口点
    builder.add_node("image_analysis_router", image_analysis_router)
    
    # 改动：编译子图并注册为单个节点
    image_analysis_subgraph = build_image_analysis_subgraph()
    builder.add_node("image_analysis_chain", image_analysis_subgraph)
    
    # TODO: 占位节点保留供未来扩展使用
    # from app.agent.image_analysis.nodes.anime_analyzer import (
    #     _attraction_placeholder,
    #     _common_placeholder
    # )
    # builder.add_node("_attraction_placeholder", _attraction_placeholder)
    # builder.add_node("_common_placeholder", _common_placeholder)
    
    # 新增：图片上传相关节点
    builder.add_node("image_upload_analyzer", image_upload_analyzer)
    builder.add_node("image_upload_callback", image_upload_callback)
    
    # 新增：错误处理节点
    builder.add_node("error_handler", error_handler)

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
            "image_upload_chain": "image_upload_analyzer",  # 新增：图片上传分支
            "error_handler": "error_handler"  # 新增：错误处理分支
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
    # 改动：简化为 router → 子图
    builder.add_edge("image_analysis_router", "image_analysis_chain")
    
    # TODO: 未来扩展时可以添加条件边（当前由子图内部处理）
    # builder.add_conditional_edges(
    #     "image_analysis_router",
    #     route_after_image_analysis,
    #     {
    #         "anime_analyzer": "anime_analyzer",
    #         "_attraction_placeholder": "_attraction_placeholder",
    #         "_common_placeholder": "_common_placeholder",
    #     }
    # )
    
    # 改动：子图出口直接连接到格式化节点
    builder.add_edge("image_analysis_chain", "_format_output")
    
    # === 图片上传链路 ===
    # 分析节点 → 回调节点 → 格式化节点
    builder.add_edge("image_upload_analyzer", "image_upload_callback")
    builder.add_edge("image_upload_callback", "_format_output")
    
    # === 错误处理链路 ===
    # 错误处理节点 → 格式化节点
    builder.add_edge("error_handler", "_format_output")

    # === 出口 ===
    builder.add_edge("_format_output", END)

    # HITL：根据环境变量决定是否启用中断机制
    enable_hitl = os.getenv("ENABLE_HITL", "true").lower() == "true"
    interrupt_nodes = ["image_upload_callback"] if enable_hitl else []
    
    logger.info(f"HITL 机制: {'启用' if enable_hitl else '禁用'} (ENABLE_HITL={os.getenv('ENABLE_HITL', 'true')})")

    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes  # HITL：在回调前中断，等待用户确认
    )

# LangSmith / langgraph.json 指向此实例
compiled_graph = build_chat_workflow()

# 改动：构建标准 Runnable 接口，供 LangSmith Playground 直接调试
def _invoke_workflow(input_data: dict) -> dict:
    """直接调用编译后的图"""
    return compiled_graph.invoke(input_data)

chat_runnable = RunnableLambda(_invoke_workflow)

# 兼容旧入口名称
chat_graph = compiled_graph
