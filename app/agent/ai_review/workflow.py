"""
AI图片审核 - LangGraph工作流定义

工作流程:
内容安全审核(Qwen) → 结果验证 → END
"""
from langgraph.graph import StateGraph, END

from app.agent.ai_review.state import AIReviewState
from app.agent.ai_review.nodes.content_safety import check_content_safety
from app.agent.ai_review.nodes.validation import validate_result
from app.common.logger import logger


def build_ai_review_workflow():
    """
    构建AI审核工作流
    
    Returns:
        编译后的LangGraph工作流
    """
    # 创建状态图
    workflow = StateGraph(AIReviewState)
    
    # 添加节点
    workflow.add_node("check_content_safety", check_content_safety)
    workflow.add_node("validate_result", validate_result)
    
    # 定义流程(线性执行)
    workflow.set_entry_point("check_content_safety")
    workflow.add_edge("check_content_safety", "validate_result")
    workflow.add_edge("validate_result", END)
    
    # 编译工作流
    ai_review_graph = workflow.compile()
    
    logger.info("[工作流] AI审核工作流构建完成")
    
    return ai_review_graph


# 全局单例: 工作流实例复用
ai_review_graph = build_ai_review_workflow()


def execute_ai_review(initial_state: dict) -> dict:
    """
    执行AI审核工作流
    
    Args:
        initial_state: 初始状态字典,包含:
            - picture_id: 图片ID
            - user_id: 用户ID
            - image_url: 图片URL
            
    Returns:
        最终状态字典,包含审核结果
    """
    try:
        logger.info(f"[工作流] 开始执行AI审核 - picture_id: {initial_state.get('picture_id')}")
        
        # 补充默认值
        if "review_status" not in initial_state:
            initial_state["review_status"] = 0
        if "review_message" not in initial_state:
            initial_state["review_message"] = ""
        if "review_timestamp" not in initial_state:
            initial_state["review_timestamp"] = 0
        
        # 执行工作流
        final_state = ai_review_graph.invoke(initial_state)
        
        logger.info(
            f"[工作流] AI审核完成 - "
            f"picture_id: {final_state.get('picture_id')}, "
            f"review_status: {final_state.get('review_status')}"
        )
        
        return final_state
    
    except Exception as e:
        logger.error(f"[工作流] AI审核异常 - picture_id: {initial_state.get('picture_id')}, error: {str(e)}", exc_info=True)
        # 返回错误状态
        return {
            **initial_state,
            "review_status": 3,  # 存疑
            "review_message": f"审核服务异常: {str(e)}",
            "review_timestamp": 0
        }
