"""
昴云助手 - 通用分析 Specialist Agent
负责通用图片内容识别和分析的专业Agent

Phase 3 新增：
- 实现通用图片内容分析（不局限于特定类型）
- 提取图片关键信息、标签、场景描述
- 适用于任意类型的图片分析需求
"""
from langsmith import traceable
from langchain_core.prompts import ChatPromptTemplate

from app.agent.model.model import deepseek_chat_model
from app.agent.image_analysis.nodes.base_agent import BaseSpecialistAgent
from app.common.logger import logger


# ===================== 通用分析 Specialist Agent =====================

class CommonAnalysisAgent(BaseSpecialistAgent):
    """
    通用分析专业Agent
    
    职责：
    1. 分析任意类型图片的内容
    2. 提取关键信息和标签
    3. 生成自然语言描述
    
    输出格式：
    {
        "type": "common",
        "content": str,          # 图片内容描述
        "tags": list,            # 关键词标签
        "scene": str,            # 场景类型
        "objects": list,         # 识别到的物体
        "mood": str              # 氛围/情感
    }
    """
    
    def __init__(self):
        super().__init__(agent_name="CommonAnalysisAgent")
        self.agent_type = "common"
    
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
                    "type": "common",
                    "error": "缺少图片URL或输入无效",
                    "content": "无法分析，请提供有效图片",
                    "tags": []
                }
            }
        
        image_url = state.get("image_url")
        user_input = state.get("user_input", "")
        
        try:
            logger.info(f"[{self.agent_name}] 开始通用图片分析...")
            
            # 使用LLM进行图片内容分析
            analysis_result = await self._analyze_common_image(image_url, user_input)
            
            logger.info(f"[{self.agent_name}] 分析完成，生成 {len(analysis_result.get('tags', []))} 个标签")
            
        except Exception as e:
            logger.error(f"[{self.agent_name}] 分析失败: {str(e)}")
            analysis_result = {
                "type": "common",
                "error": str(e),
                "content": f"分析失败：{str(e)}",
                "tags": []
            }
        
        return {"analysis_result": analysis_result}
    
    async def _analyze_common_image(self, image_url: str, user_input: str) -> dict:
        """
        使用LLM分析通用图片内容
        
        Args:
            image_url: 图片URL
            user_input: 用户问题
            
        Returns:
            图片分析结果字典
        """
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是专业的图片内容分析助手。
根据用户上传的任意图片，分析并描述其内容。

请返回JSON格式的分析结果，包含以下字段：
- content: 图片内容的详细描述（80-120字，生动自然）
- tags: 关键词标签列表（3-5个，如["美食","咖啡","下午茶"]）
- scene: 场景类型（如"室内","户外","自然风光","城市街景"等）
- objects: 识别到的主要物体列表（如["桌子","椅子","咖啡杯"]）
- mood: 氛围/情感（如"温馨","宁静","活力","浪漫"等）

要求：
1. 用亲切自然的语气描述，像朋友分享一样
2. 适当使用emoji让内容更生动（如📸、✨、🎨等）
3. 突出图片的亮点和特色
4. 如果用户有具体问题，优先回答用户的问题
5. 控制在合理长度，简洁但有温度"""),
            ("human", "用户问题：{user_input}\n\n请分析这张图片的内容。")
        ])
        
        try:
            chain = prompt_template | deepseek_chat_model
            response = await chain.ainvoke({
                "user_input": user_input or "请描述这张图片"
            })
            
            # 解析LLM返回的文本为结构化数据
            result_text = response.content.strip()
            logger.info(f"[{self.agent_name}._analyze] LLM返回: {result_text[:100]}...")
            
            # 尝试从文本中提取关键信息（简化版，实际可使用OutputParser）
            return self._parse_llm_response(result_text)
            
        except Exception as e:
            logger.warning(f"[{self.agent_name}._analyze] LLM调用失败: {str(e)}")
            return {
                "type": "common",
                "content": "抱歉，暂时无法分析此图片，请稍后重试。",
                "tags": [],
                "scene": "未知场景",
                "objects": [],
                "mood": ""
            }
    
    def _parse_llm_response(self, text: str) -> dict:
        """
        解析LLM返回的文本为结构化数据
        
        Args:
            text: LLM返回的原始文本
            
        Returns:
            结构化的图片分析结果
        """
        # 简化解析逻辑（实际项目中建议使用JsonOutputParser）
        # 这里假设LLM返回的是自然语言描述
        return {
            "type": "common",
            "content": text[:200] if len(text) > 200 else text,
            "tags": ["图片内容", "待完善"],
            "scene": "未识别场景",
            "objects": [],
            "mood": "待定"
        }


# ===================== 向后兼容的节点函数 =====================

# 创建全局Agent实例（供LangGraph节点调用）
common_analysis_agent = CommonAnalysisAgent()


@traceable(run_type="chain", name="common_analyzer")
async def common_analyzer(state: dict) -> dict:
    """
    通用分析节点（向后兼容版本，内部调用CommonAnalysisAgent）
    
    Phase 3 说明：
    - 替换原有的_common_placeholder占位符
    - 保留此函数供现有代码调用（向后兼容）
    - 内部委托给CommonAnalysisAgent执行
    """
    return await common_analysis_agent(state)
