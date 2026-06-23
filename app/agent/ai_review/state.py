"""AI审核工作流状态定义"""
from typing import TypedDict


class AIReviewState(TypedDict):
    """
    AI图片审核工作流状态
    
    注意: 智能字段(name/introduction/category/tags)在AI上传流程已填充,
    审核阶段不再生成,回调时传空值即可
    """
    # 输入字段(来自MQ消息)
    picture_id: int           # 图片ID
    user_id: int              # 用户ID
    image_url: str            # 图片URL(COS临时目录)
    
    # 审核结果
    review_status: int        # 1-通过 / 2-拒绝 / 3-存疑
    review_message: str       # 审核原因/备注
    
    # 元数据
    review_timestamp: int     # 审核时间戳(毫秒)
