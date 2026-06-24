"""
昴云助手 - 图片内容分析模块
负责图片类型路由、具体分析和结果格式化

Phase 3 改动：
- 引入 Specialist Agents 规范化架构（Anime/Attraction/Common）
- 所有Agent继承BaseSpecialistAgent，提供统一接口
- 移除占位符，替换为真实的分析Agent
- 符合Agents.md规范：唯一顶层导出入口，对外输出State、build_subgraph、业务常量（导出≥3个对象）
"""

# 导出状态定义
from app.agent.image_analysis.state import ImageAnalysisState

# 导出子图构建器
from app.agent.image_analysis.graph import build_subgraph

# 导出配置常量
from app.agent.image_analysis.config import ANALYSIS_TYPES, DEFAULT_ANALYSIS_TYPE

# Phase 2: 导出Supervisor Agent（核心协调者）
from app.agent.image_analysis.nodes.supervisor import supervisor_coordinator

# Phase 3: 导出Specialist Agents（规范化版本）
from app.agent.image_analysis.nodes.anime_analyzer import (
    anime_analyzer,  # 向后兼容函数
    anime_analysis_agent  # 新Agent实例
)
from app.agent.image_analysis.nodes.attraction_analyzer import (
    attraction_analyzer,  # 向后兼容函数
    attraction_analysis_agent  # 新Agent实例
)
from app.agent.image_analysis.nodes.common_analyzer import (
    common_analyzer,  # 向后兼容函数
    common_analysis_agent  # 新Agent实例
)

# 导出其他节点函数（供主工作流直接使用，向后兼容）
from app.agent.image_analysis.nodes.analysis_router import image_analysis_router, route_after_image_analysis
from app.agent.image_analysis.nodes.analysis_formatter import analysis_response_formatter

__all__ = [
    # 核心导出（符合Agents.md规范：≥3个对象）
    "ImageAnalysisState",
    "build_subgraph",
    "ANALYSIS_TYPES",
    "DEFAULT_ANALYSIS_TYPE",
    
    # Phase 2: Supervisor Agent
    "supervisor_coordinator",
    
    # Phase 3: Specialist Agents（新Agent实例）
    "anime_analysis_agent",
    "attraction_analysis_agent",
    "common_analysis_agent",
    
    # 节点函数导出（向后兼容）
    "image_analysis_router",
    "route_after_image_analysis",
    "anime_analyzer",  # 旧版函数，内部委托给anime_analysis_agent
    "attraction_analyzer",  # 新版函数，内部委托给attraction_analysis_agent
    "common_analyzer",  # 新版函数，内部委托给common_analysis_agent
    "analysis_response_formatter",
]
