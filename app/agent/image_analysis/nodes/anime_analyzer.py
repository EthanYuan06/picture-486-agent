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
import json

from app.agent.model.model import deepseek_chat_model
from app.agent.image_upload.tool.tools import anime_analysis as anime_tool
from app.agent.schemas import AnimeInfoTranslation
from app.agent.image_analysis.nodes.base_agent import BaseSpecialistAgent
from app.agent.tool import web_search  # 新增：导入 Tavily 搜索工具
from app.common.logger import logger

# 初始化翻译 Prompt Template（不再使用 Chain，改为直接调用）
anime_translation_prompt = ChatPromptTemplate.from_messages([
    ("system", """你是专业的动漫翻译助手。
将日文角色名和作品名翻译成中文常用译名。

输出格式必须是严格的 JSON，包含以下字段：
- character: 中文角色名
- work: 中文作品名

只返回 JSON，不要其他内容。"""),
    ("human", "角色名（日文）：{character_jp}\n作品名（日文）：{work_jp}")
])


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
            
            # 步骤2：翻译日文为中文（先搜索官方译名，再用 DeepSeek 整理）
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
        使用 Tavily 搜索 + DeepSeek 整理的方式翻译日文动漫信息
        
        流程：
        1. 搜索作品的官方中文译名
        2. 基于搜索结果生成翻译
        
        Args:
            character_jp: 日文角色名
            work_jp: 日文作品名
            
        Returns:
            包含中文字段名的字典
        """
        try:
            # 步骤1：搜索作品和角色的官方中文译名
            search_query = f"{work_jp} {character_jp} 中文译名 官方翻译"
            logger.info(f"[{self.agent_name}._translate] 搜索官方译名: {search_query}")
            
            search_results_raw = await web_search.ainvoke({"query": search_query})
            
            # 处理 Tavily 返回结果（提取完整内容）
            if isinstance(search_results_raw, dict):
                results_list = search_results_raw.get('results', [])
                context_parts = []
                for i, r in enumerate(results_list[:3], 1):  # 取前3个结果
                    content = r.get('content', '')
                    title = r.get('title', '')
                    if content or title:
                        context_parts.append(f"[来源{i}] {title}: {content}")  # 不截断，让后续逻辑统一处理
                search_context = "\n\n".join(context_parts) if context_parts else ""
                logger.info(f"[{self.agent_name}._translate] 从 Tavily 提取到 {len(context_parts)} 条结果")
            else:
                search_context = str(search_results_raw)
            
            logger.info(f"[{self.agent_name}._translate] 搜索结果总长度: {len(search_context)}")
            
            # 步骤2：基于搜索结果用 DeepSeek 提取官方译名
            prompt = f"""你是专业的动漫翻译助手。请基于以下搜索结果，提取角色和作品的官方中文译名。

【日文原名】
角色：{character_jp}
作品：{work_jp}

【搜索结果】
{search_context}

【输出要求】
1. 优先使用搜索结果中的官方中文译名
2. 如果搜索结果中没有明确的官方译名，使用常见的中文译名
3. 如果以上都没有，再进行合理翻译
4. 输出严格的 JSON 格式：{{"character": "中文角色名", "work": "中文作品名"}}

只返回 JSON，不要其他内容。"""
            
            result = await deepseek_chat_model.ainvoke(prompt)
            result_content = result.content if hasattr(result, 'content') else str(result)
            
            # 解析 JSON
            try:
                result_dict = json.loads(result_content)
            except json.JSONDecodeError:
                # 尝试提取 JSON 部分
                import re
                json_match = re.search(r'\{[^}]+\}', result_content)
                if json_match:
                    result_dict = json.loads(json_match.group())
                else:
                    raise ValueError("无法解析 JSON")
            
            logger.info(f"[{self.agent_name}._translate] 翻译结果: {result_dict}")
            return {"character": result_dict["character"], "work": result_dict["work"]}
            
        except Exception as e:
            logger.warning(f"[{self.agent_name}._translate] 翻译失败: {str(e)}")
            # 降级方案：使用简单翻译
            try:
                simple_result = await anime_translation_prompt.format_messages(
                    character_jp=character_jp,
                    work_jp=work_jp
                )
                result = await deepseek_chat_model.ainvoke(simple_result)
                result_content = result.content if hasattr(result, 'content') else str(result)
                result_dict = json.loads(result_content)
                return {"character": result_dict["character"], "work": result_dict["work"]}
            except Exception as e2:
                logger.error(f"[{self.agent_name}._translate] 降级翻译也失败: {str(e2)}")
                return {"character": character_jp, "work": work_jp}
    
    async def _generate_character_description(self, character: str, work: str) -> str:
        """
        生成角色简要介绍（基于 Tavily 搜索 + DeepSeek 整理）
        
        Args:
            character: 角色名
            work: 作品名
            
        Returns:
            50-80字的角色介绍（基于真实数据源）
        """
        try:
            # 步骤1：调用 Tavily 搜索角色信息
            search_query = f"{character} {work} 角色介绍 性格 身份"
            logger.info(f"[{self.agent_name}._search] 搜索查询: {search_query}")
            
            # TavilySearch 作为 Tool 使用时，可能返回 dict 或字符串
            try:
                search_results_raw = await web_search.ainvoke({"query": search_query})
                logger.info(f"[{self.agent_name}._search] Tavily返回类型: {type(search_results_raw)}")
                
                # 处理不同类型的返回值
                if isinstance(search_results_raw, dict):
                    # 如果是字典，提取 results 字段
                    results_list = search_results_raw.get('results', [])
                    if results_list:
                        # 拼接所有结果的完整内容（不限制单个来源长度）
                        context_parts = []
                        for i, r in enumerate(results_list[:3], 1):  # 取前3个结果
                            content = r.get('content', '')
                            title = r.get('title', '')
                            if content or title:
                                context_parts.append(f"[来源{i}] {title}: {content}")
                        search_results_str = "\n\n".join(context_parts) if context_parts else ""
                    else:
                        search_results_str = ""
                elif isinstance(search_results_raw, str):
                    search_results_str = search_results_raw
                else:
                    search_results_str = str(search_results_raw)
                
                logger.info(f"[{self.agent_name}._search] Tavily返回内容长度: {len(str(search_results_str)) if search_results_str else 0}")
                if search_results_str:
                    logger.info(f"[{self.agent_name}._search] Tavily返回内容前200字符: {str(search_results_str)[:200]}")
            except Exception as e:
                logger.error(f"[{self.agent_name}._search] Tavily API调用失败: {str(e)}")
                raise
            
            # 检查搜索结果是否为空或无效
            if not search_results_str or not isinstance(search_results_str, str) or len(search_results_str.strip()) == 0:
                logger.warning(f"[{self.agent_name}._search] 搜索无结果或结果为空")
                return f"关于 {character} 暂无详细公开信息，建议查阅《{work}》官方资料。"
            
            # 直接使用搜索结果字符串作为上下文（提升限制以保留更多信息）
            context = search_results_str[:2500]  # 限制长度避免过长，但保留足够信息
            logger.info(f"[{self.agent_name}._search] 获取到搜索结果，长度: {len(context)}")
            if len(search_results_str) > 2500:
                logger.info(f"[{self.agent_name}._search] ⚠️ 搜索结果被截断，原始长度: {len(search_results_str)}")
            
            # 步骤2：使用 DeepSeek 基于搜索结果生成介绍（智能总结）
            prompt = f"""你是专业的动漫知识助手。请基于以下搜索结果，简要介绍角色 {character}。

【搜索结果】
{context}

【输出要求】
1. ⚠️ 只使用上述搜索结果中的信息，绝对不要编造角色的职业、性格、剧情等细节
2. 📝 字数控制在 180-220 字左右，提供较完整的角色介绍
3. 💬 语气亲切自然，像朋友聊天，适当使用 emoji（如 🎬、😊、🌟 等）
4. 📋 内容应包含：角色身份/职业、性格特点、在作品中的作用或亮点
5. ❗ 如果搜索结果信息不足，明确说明"暂无详细公开信息"
6. 🎯 结尾可以用一句温馨的互动语

请直接输出介绍文本，不要包含其他说明。"""
            
            resp = await deepseek_chat_model.ainvoke(prompt)
            description = resp.content.strip()
            logger.info(f"[{self.agent_name}._generate_desc] 生成描述: {description[:50]}...")
            return description
            
        except Exception as e:
            logger.error(f"[{self.agent_name}._generate_desc] 生成失败: {str(e)}")
            # 降级方案：返回简洁的保守描述
            return f"😊 {character} 是《{work}》中的角色。由于暂时无法获取详细信息，建议您查阅官方资料了解更多～"


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
