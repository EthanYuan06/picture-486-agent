"""
昴云助手 - 图片分析子图构建器
符合Agents.md规范：封装build_subgraph()，内部节点组装、私有路由、子图编译

Phase 3 改动：
- Specialist Agents（动漫/景点/通用）已规范化实现
- Supervisor 内部调用规范的Specialist Agents
- 移除占位符节点，使用真实的分析Agent
- 简化子图结构，将复杂性封装在 Supervisor 内部

职责：
1. 定义图片分析子图的完整流程
2. 注册所有分析相关节点（包括Supervisor）
3. 配置简单线性流程（Supervisor → Formatter）
4. 返回编译后的子图供主工作流调用
"""
from langgraph.graph import StateGraph, END

from app.agent.image_analysis.state import ImageAnalysisState
from app.agent.image_analysis.nodes.supervisor import supervisor_coordinator
from app.agent.image_analysis.nodes.analysis_formatter import analysis_response_formatter


def build_subgraph():
    """
    构建并编译图片分析子图
    
    Phase 3 架构：
    - Supervisor Agent 作为协调者，负责任务分解和分发
    - Specialist Agents（动漫/景点/通用）已规范化实现，由 Supervisor 调用
    - 简化主图结构，将复杂性封装在子图内部
    
    Returns:
        编译后的 LangGraph 子图，可作为单个节点嵌入主工作流
    """
    builder = StateGraph(ImageAnalysisState)
    
    # ===================== 注册所有节点 =====================
    # Phase 3: Supervisor 内部调用规范的Specialist Agents
    builder.add_node("supervisor", supervisor_coordinator)
    builder.add_node("analysis_response_formatter", analysis_response_formatter)
    
    # ===================== 设置入口 =====================
    # 子图入口为 Supervisor 节点
    builder.set_entry_point("supervisor")
    
    # ===================== 定义流程边 =====================
    # Supervisor → Formatter → END
    # Supervisor 内部会调用对应的 Specialist Agent（Anime/Attraction/Common）
    builder.add_edge("supervisor", "analysis_response_formatter")
    
    # ===================== 出口 =====================
    builder.add_edge("analysis_response_formatter", END)
    
    return builder.compile()
