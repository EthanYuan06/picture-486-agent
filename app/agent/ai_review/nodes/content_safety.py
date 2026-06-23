"""
AI图片审核 - 内容安全审核节点
使用Qwen多模态模型进行敏感内容检测
"""
import json
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.ai_review.state import AIReviewState
from app.agent.model.model import qwen_vision_model
from app.common.logger import logger


# 内容安全审核提示词(可根据需求自定义调整)
CONTENT_SAFETY_PROMPT = """你是一个专业的内容安全审核助手。请仔细分析这张图片,判断是否包含违规内容。

审核标准:
1. **色情低俗**: 裸露、性暗示、成人内容等
2. **暴力血腥**: 血腥场面、武器暴力、恐怖内容等
3. **政治敏感**: 政治人物、敏感事件、违禁标识等
4. **违法内容**: 毒品、赌博、诈骗等违法信息
5. **其他违规**: 侵犯隐私、恶意攻击、虚假信息等等

请根据图片内容,返回JSON格式的判断结果:
{
  "suggestion": "pass" | "block" | "review",
  "reason": "简要说明判断原因"
}

字段说明:
- suggestion: 
  * "pass" - 内容安全,审核通过
  * "block" - 明确违规,直接拒绝
  * "review" - 存疑或不确定,需要人工复核
- reason: 简短说明判断依据(50字以内)

⚠️ 重要:
- 只返回JSON格式,不要添加任何额外文字
- 如果无法确定,请返回"review"而非猜测
- 保持客观公正,避免过度审查"""


def check_content_safety(state: AIReviewState) -> AIReviewState:
    """
    节点1: 内容安全审核
    
    使用Qwen多模态模型分析图片,判断是否包含违规内容
    
    Args:
        state: AI审核状态(包含image_url等字段)
        
    Returns:
        更新后的状态(包含review_status和review_message)
    """
    image_url = state.get("image_url")
    
    if not image_url:
        logger.error("[内容安全审核] 缺少图片URL")
        state["review_status"] = 3  # 存疑
        state["review_message"] = "图片URL缺失,无法审核"
        return state
    
    try:
        logger.info(f"[内容安全审核] 开始审核 - picture_id: {state.get('picture_id')}")
        
        # 构建消息
        messages = [
            SystemMessage(content=CONTENT_SAFETY_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": "请审核这张图片的内容安全性"},
                {"type": "image_url", "image_url": {"url": image_url}}
            ])
        ]
        
        # 调用Qwen多模态模型
        response = qwen_vision_model.invoke(messages)
        result_text = response.content
        
        logger.info(f"[内容安全审核] LLM原始输出: {result_text}")
        
        # 解析JSON结果（兼容 <think> 标签和混合文本）
        import re
        result_data = None
        
        # 策略1：直接解析纯JSON
        try:
            result_data = json.loads(result_text)
        except json.JSONDecodeError:
            # 策略2：提取Markdown代码块
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', result_text, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group(1).strip())
            
            # 策略3：查找最后一个JSON对象（处理 <think> 推理格式）
            if result_data is None:
                json_objects = re.findall(r'\{[^{}]*\}', result_text, re.DOTALL)
                for json_str in reversed(json_objects):
                    try:
                        result_data = json.loads(json_str)
                        break
                    except json.JSONDecodeError:
                        continue
        
        # 解析失败时降级为人工审核
        if result_data is None:
            state["review_status"] = 3
            state["review_message"] = "LLM响应格式异常，等待人工审核"
            return state
        
        # 提取审核结果
        suggestion = result_data.get("suggestion", "").lower()
        reason = result_data.get("reason", "未知原因")
        
        # 映射到审核状态
        if suggestion == "pass":
            state["review_status"] = 1  # 通过
            state["review_message"] = f"AI自动审核通过: {reason}"
            logger.info(f"[内容安全审核] 审核通过 - picture_id: {state.get('picture_id')}")
            
        elif suggestion == "block":
            state["review_status"] = 2  # 拒绝
            state["review_message"] = f"包含违规内容: {reason}"
            logger.warning(f"[内容安全审核] 审核拒绝 - picture_id: {state.get('picture_id')}, 原因: {reason}")
            
        else:
            # review或其他值都视为存疑
            state["review_status"] = 3  # 存疑
            state["review_message"] = f"内容疑似违规,需人工复核: {reason}"
            logger.info(f"[内容安全审核] 标记存疑 - picture_id: {state.get('picture_id')}, 原因: {reason}")
    
    except Exception as e:
        logger.error(f"[内容安全审核] 审核异常 - picture_id: {state.get('picture_id')}, error: {str(e)}", exc_info=True)
        # 异常时标记为存疑,等待人工审核
        state["review_status"] = 3
        state["review_message"] = f"审核服务暂时不可用,等待人工审核: {str(e)}"
    
    return state
