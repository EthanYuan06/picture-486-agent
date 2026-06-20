"""
昴云助手 - 图片分析器模块
负责具体的图片分析逻辑（动漫/风景/通用）
"""
from langsmith import traceable

from app.agent.model.model import deepseek_chat_model
from app.agent.tools import anime_analysis as anime_tool
from app.common.logger import logger
from app.utils.api_utils import safe_parse_json


# ===================== 动漫分析节点 =====================

@traceable(run_type="chain", name="anime_analyzer")
def anime_analyzer(state: dict) -> dict:
    """
    动漫分析节点（直接调用工具，避免 Agent 循环和过度搜索）
    
    Args:
        state: 包含 image_url, user_input 的字典
    Returns:
        analysis_result: 标准化的分析结果
    """
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


# ===================== 辅助函数 =====================

def _translate_anime_info(character_jp: str, work_jp: str) -> dict:
    """
    使用 DeepSeek 翻译日文动漫信息
    
    Args:
        character_jp: 日文角色名
        work_jp: 日文作品名
        
    Returns:
        包含中文字段名的字典
    """
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


# ===================== 占位节点（TODO）=====================

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
