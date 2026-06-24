"""
昴云助手 - 动漫分析 Specialist Agent
负责动漫角色识别和分析的专业Agent

Phase 3 改动：
- 继承 BaseSpecialistAgent，实现统一的Agent接口
- 保持原有功能不变（识图、翻译、生成描述）
- 增强错误处理和日志追踪
"""
from langsmith import traceable
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.agent.model.model import deepseek_chat_model
from app.agent.image_upload.tool.tools import anime_analysis as anime_tool
from app.agent.schemas import AnimeInfoTranslation
from app.agent.image_analysis.nodes.base_agent import BaseSpecialistAgent
from app.common.logger import logger

# 初始化翻译 Parser + Prompt Template
anime_translation_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是专业的动漫翻译助手。
将日文角色名和作品名翻译成中文常用译名。
只返回 JSON 格式，不要其他内容。"""),
    ("human", "角色名（日文）：{character_jp}\n作品名（日文）：{work_jp}")
])
anime_translation_parser = JsonOutputParser(pydantic_object=AnimeInfoTranslation)
anime_translation_chain = anime_translation_prompt | deepseek_chat_model | anime_translation_parser


# ===================== 动漫分析 Specialist Agent =====================

class AnimeAnalysisAgent(BaseSpecialistAgent):
    """
    动漫分析专业Agent
    
    职责：
    1. 调用识图工具获取角色和作品信息
    2. 翻译日文为中文
    3. 生成角色简要介绍
    
    输出格式：
    {
        "type": "anime_analysis",
        "character_name": str,
        "character_name_jp": str,
        "work_name": str,
        "work_name_jp": str,
        "description": str,
        "confidence": float
    }
    """
    
    def __init__(self):
        super().__init__(agent_name="AnimeAnalysisAgent")
        self.agent_type = "anime_analysis"
    
    async def analyze(self, state: dict) -> dict:
        """
        核心分析方法
        
        Args:
            state: ImageAnalysisState 状态字典
            
        Returns:
            {"analysis_result": dict} 标准化分析结果
        """
        if not self.validate_input(state):
            return {
                "analysis_result": {
                    "type": "anime_analysis",
                    "error": "缺少图片URL或输入无效",
                    "character_name": "未知角色",
                    "work_name": "未知作品",
                    "description": "无法分析，请提供有效图片"
                }
            }
        
        image_url = state.get("image_url")
        user_input = state.get("user_input", "")
        
        try:
            # 步骤1：调用识图工具获取基本信息
            logger.info(f"[{self.agent_name}] 开始识图: {image_url[:50]}...")
            raw_result = anime_tool.invoke({"image_url": image_url})
            
            # 调试：打印原始结果类型和内容
            logger.info(f"[{self.agent_name}] 工具返回类型: {type(raw_result)}")
            logger.info(f"[{self.agent_name}] 工具返回内容: {raw_result}")
            
            # 检查是否为错误信息
            if isinstance(raw_result, str) and ("请求参数错误" in raw_result or "超时" in raw_result or "失败" in raw_result):
                logger.warning(f"[{self.agent_name}] 识图失败: {raw_result}")
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
            
            logger.info(f"[{self.agent_name}] 识图结果: {character_jp} | {work_jp} (置信度: {confidence})")
            
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
                translated = await self._translate_anime_info(character_jp, work_jp)
            else:
                translated = {"character": "未知角色", "work": "未知作品"}
            
            # 步骤3：生成简要介绍（不调用 Tavily，直接用 LLM）
            description = await self._generate_character_description(
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
            
            logger.info(f"[{self.agent_name}] 分析完成: {analysis_result['character_name']} - {analysis_result['work_name']}")
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] 分析失败: {str(e)}")
            analysis_result = {
                "error": str(e),
                "type": "anime_analysis",
                "character_name": "未知角色",
                "work_name": "未知作品",
                "description": "分析失败，请稍后重试"
            }
        
        return {"analysis_result": analysis_result}
    
    # ===================== 辅助方法（作为Agent实例方法）=====================
    
    async def _translate_anime_info(self, character_jp: str, work_jp: str) -> dict:
        """
        使用 DeepSeek 翻译日文动漫信息（异步版本）
        
        Args:
            character_jp: 日文角色名
            work_jp: 日文作品名
            
        Returns:
            包含中文字段名的字典
        """
        try:
            # 使用 Chain 自动解析和校验
            result = await anime_translation_chain.ainvoke({
                "character_jp": character_jp,
                "work_jp": work_jp
            })
            # result 是 AnimeInfoTranslation 对象，类型安全
            logger.info(f"[{self.agent_name}._translate] 翻译结果: {result.character} | {result.work}")
            return {"character": result.character, "work": result.work}
        except Exception as e:
            logger.warning(f"[{self.agent_name}._translate] 翻译失败: {str(e)}")
            return {"character": character_jp, "work": work_jp}
    
    async def _generate_character_description(self, character: str, work: str) -> str:
        """
        生成角色简要介绍（异步版本，不调用外部搜索，节省token）
        
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
            resp = await deepseek_chat_model.ainvoke(prompt)
            description = resp.content.strip()
            logger.info(f"[{self.agent_name}._generate_desc] 生成描述: {description[:50]}...")
            return description
        except Exception as e:
            logger.warning(f"[{self.agent_name}._generate_desc] 生成失败: {str(e)}")
            return f"{character} 是 {work} 中的角色，暂无详细信息。"


# ===================== 向后兼容的节点函数 =====================

# 创建全局Agent实例（供LangGraph节点调用）
anime_analysis_agent = AnimeAnalysisAgent()


@traceable(run_type="chain", name="anime_analyzer")
async def anime_analyzer(state: dict) -> dict:
    """
    动漫分析节点（向后兼容版本，内部调用AnimeAnalysisAgent）
    
    Phase 3 说明：
    - 保留此函数供现有代码调用（向后兼容）
    - 内部委托给AnimeAnalysisAgent执行
    - 新代码建议直接使用anime_analysis_agent实例
    """
    return await anime_analysis_agent(state)
