"""
昴云助手 - 图片分析路由模块
负责图片类型判断和二级路由分发
"""
from langsmith import traceable

from app.agent.model.model import deepseek_chat_model
from app.common.logger import logger


# ===================== 图片分析二级路由节点 =====================

@traceable(run_type="chain", name="image_analysis_router")
async def image_analysis_router(state: dict) -> dict:
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
        resp = await deepseek_chat_model.ainvoke(prompt)
        analysis_type = resp.content.strip().lower()
        if analysis_type not in ["attraction", "anime_analysis", "common"]:
            analysis_type = "common"  # 兜底
    except Exception as e:
        analysis_type = "common"  # 异常兜底
    
    return {"analysis_type": analysis_type}


# ===================== 二级路由函数 =====================

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
