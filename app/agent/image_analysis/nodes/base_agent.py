"""
昴云助手 - Specialist Agent 基类定义
提供图片分析专用Agent的统一接口规范

设计原则：
- 统一的输入输出契约（ImageAnalysisState → analysis_result）
- 每个Agent专注于单一类型分析
- 可插拔、可扩展的Agent架构
- 符合Agents.md规范：业务内聚、职责清晰
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from app.common.logger import logger


class BaseSpecialistAgent(ABC):
    """
    Specialist Agent 抽象基类
    
    所有专业分析Agent必须继承此类并实现analyze方法。
    
    职责：
    1. 接收 ImageAnalysisState 作为输入
    2. 执行特定类型的图片分析（动漫/景点/通用）
    3. 返回标准化的 analysis_result 字典
    
    契约：
    - 输入：state (dict) 包含 user_input, image_url, analysis_type
    - 输出：{"analysis_result": dict} 标准化分析结果
    """
    
    def __init__(self, agent_name: str):
        """
        初始化Agent
        
        Args:
            agent_name: Agent名称标识（用于日志追踪）
        """
        self.agent_name = agent_name
    
    @abstractmethod
    async def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心分析方法（子类必须实现）
        
        Args:
            state: ImageAnalysisState 状态字典
                - user_input: 用户输入文本
                - image_url: 图片URL
                - analysis_type: 分析类型
                
        Returns:
            {"analysis_result": dict} 标准化分析结果
            结果应包含：
                - type: 分析类型标识
                - 其他字段根据具体类型而定
        """
        pass
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        使Agent可被直接调用（兼容LangGraph节点签名）
        
        Args:
            state: ImageAnalysisState 状态字典
            
        Returns:
            {"analysis_result": dict} 分析结果
        """
        logger.info(f"[{self.agent_name}] 开始分析...")
        try:
            result = await self.analyze(state)
            logger.info(f"[{self.agent_name}] 分析完成")
            return result
        except Exception as e:
            logger.error(f"[{self.agent_name}] 分析失败: {str(e)}")
            return {
                "analysis_result": {
                    "type": getattr(self, 'agent_type', 'unknown'),
                    "error": str(e),
                    "description": f"分析失败：{str(e)}"
                }
            }
    
    def validate_input(self, state: Dict[str, Any]) -> bool:
        """
        验证输入状态是否有效
        
        Args:
            state: ImageAnalysisState 状态字典
            
        Returns:
            bool: 输入是否有效
        """
        if not isinstance(state, dict):
            logger.warning(f"[{self.agent_name}] 输入不是字典类型")
            return False
        
        if "image_url" not in state or not state.get("image_url"):
            logger.warning(f"[{self.agent_name}] 缺少image_url")
            return False
        
        return True
