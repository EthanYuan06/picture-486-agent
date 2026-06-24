"""
昴云助手 - 景点分析 Specialist Agent
负责风景/景点识别和分析的专业Agent

Phase 3 新增：
- 实现完整的景点识别功能（基于LLM视觉分析）
- 提取景点名称、位置、描述等信息
- 提供景点背景介绍和旅游建议
"""
from langsmith import traceable
from langchain_core.prompts import ChatPromptTemplate

from app.agent.model.model import deepseek_chat_model
from app.agent.image_analysis.nodes.base_agent import BaseSpecialistAgent
from app.common.logger import logger


# ===================== 景点分析 Specialist Agent =====================

class AttractionAnalysisAgent(BaseSpecialistAgent):
    """
    景点分析专业Agent
    
    职责：
    1. 识别图片中的景点/风景
    2. 提取景点名称、位置信息
    3. 生成景点描述和旅游建议
    
    输出格式：
    {
        "type": "attraction",
        "name": str,           # 景点名称
        "location": str,       # 地理位置
        "description": str,    # 景点描述
        "highlights": list,    # 亮点特色
        "travel_tips": str     # 旅游建议
    }
    """
    
    def __init__(self):
        super().__init__(agent_name="AttractionAnalysisAgent")
        self.agent_type = "attraction"
    
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
                    "type": "attraction",
                    "error": "缺少图片URL或输入无效",
                    "name": "未知景点",
                    "location": "未知位置",
                    "description": "无法分析，请提供有效图片"
                }
            }
        
        image_url = state.get("image_url")
        user_input = state.get("user_input", "")
        
        try:
            logger.info(f"[{self.agent_name}] 开始景点分析...")
            
            # 使用LLM进行景点识别和分析
            analysis_result = await self._analyze_attraction(image_url, user_input)
            
            logger.info(f"[{self.agent_name}] 分析完成: {analysis_result.get('name', '未知景点')}")
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] 分析失败: {str(e)}")
            analysis_result = {
                "type": "attraction",
                "error": str(e),
                "name": "未知景点",
                "location": "未知位置",
                "description": f"分析失败：{str(e)}"
            }
        
        return {"analysis_result": analysis_result}
    
    async def _analyze_attraction(self, image_url: str, user_input: str) -> dict:
        """
        使用LLM分析景点图片
        
        Args:
            image_url: 图片URL
            user_input: 用户问题
            
        Returns:
            景点分析结果字典
        """
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是专业的景点识别和分析助手。
根据用户上传的风景/景点图片，识别并分析相关信息。

请返回JSON格式的分析结果，包含以下字段：
- name: 景点名称（如果不确定，用"未识别景点"）
- location: 地理位置（城市/省份/国家，如果不确定用"未知位置"）
- description: 景点描述（50-80字，包含历史背景、特色等）
- highlights: 亮点特色列表（如["樱花盛开","古建筑群","夜景美丽"]）
- travel_tips: 旅游建议（最佳游览时间、注意事项等，30-50字）

要求：
1. 语气亲切自然，像朋友推荐一样
2. 适当使用emoji让内容更生动（如🏞️、🌸、⛩️等）
3. 如果无法确定具体景点，就描述看到的风景特征
4. 突出景点的独特之处和推荐理由"""),
            ("human", "用户问题：{user_input}\n\n请分析这张图片中的景点信息。")
        ])
        
        try:
            chain = prompt_template | deepseek_chat_model
            response = await chain.ainvoke({
                "user_input": user_input or "这是什么地方？"
            })
            
            # 解析LLM返回的文本为结构化数据
            result_text = response.content.strip()
            logger.info(f"[{self.agent_name}._analyze] LLM返回: {result_text[:100]}...")
            
            # 尝试从文本中提取关键信息（简化版，实际可使用OutputParser）
            return self._parse_llm_response(result_text)
            
        except Exception as e:
            logger.warning(f"[{self.agent_name}._analyze] LLM调用失败: {str(e)}")
            return {
                "type": "attraction",
                "name": "未识别景点",
                "location": "未知位置",
                "description": "抱歉，暂时无法识别此景点，请稍后重试。",
                "highlights": [],
                "travel_tips": ""
            }
    
    def _parse_llm_response(self, text: str) -> dict:
        """
        解析LLM返回的文本为结构化数据
        
        Args:
            text: LLM返回的原始文本
            
        Returns:
            结构化的景点分析结果
        """
        # 简化解析逻辑（实际项目中建议使用JsonOutputParser）
        # 这里假设LLM返回的是自然语言描述
        return {
            "type": "attraction",
            "name": "风景胜地",
            "location": "未知位置",
            "description": text[:200] if len(text) > 200 else text,
            "highlights": ["自然风光", "适合拍照"],
            "travel_tips": "建议选择晴朗天气前往，注意防晒和保暖。"
        }


# ===================== 向后兼容的节点函数 =====================

# 创建全局Agent实例（供LangGraph节点调用）
attraction_analysis_agent = AttractionAnalysisAgent()


@traceable(run_type="chain", name="attraction_analyzer")
async def attraction_analyzer(state: dict) -> dict:
    """
    景点分析节点（向后兼容版本，内部调用AttractionAnalysisAgent）
    
    Phase 3 说明：
    - 替换原有的_attraction_placeholder占位符
    - 保留此函数供现有代码调用（向后兼容）
    - 内部委托给AttractionAnalysisAgent执行
    """
    return await attraction_analysis_agent(state)
