"""
AI图片审核 - 结果验证节点
确保审核结果的完整性和有效性
"""
import time

from app.agent.ai_review.state import AIReviewState
from app.common.logger import logger


def validate_result(state: AIReviewState) -> AIReviewState:
    """
    节点2: 结果验证
    
    验证审核结果的完整性,确保必填字段有效
    
    Args:
        state: AI审核状态
        
    Returns:
        更新后的状态(包含review_timestamp等元数据)
    """
    picture_id = state.get("picture_id")
    
    # 验证review_status
    review_status = state.get("review_status", 0)
    if review_status not in [1, 2, 3]:
        logger.warning(f"[结果验证] 无效的审核状态: {review_status}, 修正为3(存疑)")
        state["review_status"] = 3
        state["review_message"] = "审核状态异常,等待人工复核"
    
    # 验证review_message
    review_message = state.get("review_message", "").strip()
    if not review_message:
        logger.warning(f"[结果验证] 缺少审核原因,使用默认值")
        status_map = {1: "通过", 2: "拒绝", 3: "存疑"}
        state["review_message"] = f"AI自动审核{status_map.get(review_status, '存疑')}"
    
    # 设置审核时间戳(毫秒)
    state["review_timestamp"] = int(time.time() * 1000)
    
    logger.info(
        f"[结果验证] 验证完成 - "
        f"picture_id: {picture_id}, "
        f"review_status: {state['review_status']}, "
        f"review_message: {state['review_message'][:50]}"
    )
    
    return state
