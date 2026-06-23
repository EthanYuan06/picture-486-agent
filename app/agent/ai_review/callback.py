"""
AI图片审核 - HTTP回调客户端
将审核结果回调给Java后端
"""
import requests

from app.agent.ai_review.config import AIReviewConfig
from app.agent.ai_review.state import AIReviewState
from app.common.logger import logger


def callback_backend(state: AIReviewState) -> bool:
    """
    回调后端接口,提交审核结果
    
    Args:
        state: AI审核状态(包含所有审核结果)
        
    Returns:
        是否回调成功
    """
    picture_id = state.get("picture_id")
    
    try:
        # 构建回调URL
        url = f"{AIReviewConfig.BACKEND_URL}/api/picture/ai/review/callback"
        
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": AIReviewConfig.BACKEND_API_KEY
        }
        
        # 构建请求体
        payload = {
            "pictureId": state.get("picture_id"),
            "userId": state.get("user_id"),
            "reviewStatus": state.get("review_status"),
            "reviewMessage": state.get("review_message"),
            # 智能字段传空值(上传时已填写)
            "name": "",
            "introduction": "",
            "category": "",
            "tags": [],
            "reviewTimestamp": state.get("review_timestamp")
        }
        
        logger.info(f"[HTTP回调] 开始回调 - picture_id: {picture_id}, url: {url}")
        
        # 发送POST请求
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # 检查响应
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                logger.info(f"[HTTP回调] 回调成功 - picture_id: {picture_id}")
                return True
            else:
                logger.warning(
                    f"[HTTP回调] 后端返回错误 - "
                    f"picture_id: {picture_id}, "
                    f"code: {data.get('code')}, "
                    f"message: {data.get('message')}"
                )
                return False
        else:
            logger.warning(
                f"[HTTP回调] HTTP状态码异常 - "
                f"picture_id: {picture_id}, "
                f"status_code: {response.status_code}, "
                f"response: {response.text[:200]}"
            )
            return False
    
    except requests.exceptions.Timeout:
        logger.error(f"[HTTP回调] 回调超时 - picture_id: {picture_id}")
        return False
    
    except requests.exceptions.ConnectionError:
        logger.error(f"[HTTP回调] 连接失败 - picture_id: {picture_id}, url: {url}")
        return False
    
    except Exception as e:
        logger.error(f"[HTTP回调] 回调异常 - picture_id: {picture_id}, error: {str(e)}", exc_info=True)
        return False
