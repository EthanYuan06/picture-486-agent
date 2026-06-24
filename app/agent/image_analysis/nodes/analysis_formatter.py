"""
昴云助手 - 图片分析格式化模块
负责将分析结果格式化为友好的用户回复
"""
from langsmith import traceable

from app.agent.model.model import deepseek_chat_model
from app.agent.image_analysis.prompts import get_analysis_prompt_template
from app.common.logger import logger


# ===================== 分析结果格式化节点 =====================

@traceable(run_type="chain", name="analysis_response_formatter")  # 改动：添加 LangSmith 追踪
async def analysis_response_formatter(state: dict) -> dict:
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
        resp = await deepseek_chat_model.ainvoke(prompt)
        response_text = resp.content.strip()
    except Exception as e:
        # 改动：记录异常并返回友好提示
        logger.error(f"[图片分析格式化] LLM调用失败: {str(e)}")
        response_text = "😊 图片分析完成啦～ 但生成回复时出了点小问题，请稍后再试！"
    
    return {
        "response_text": response_text,
        "response_images": []
    }
