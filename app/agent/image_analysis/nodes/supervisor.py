"""
昴云助手 - 图片分析Supervisor Agent（协调者）
负责Multi-Agent架构的核心协调逻辑

Phase 3 改动：
- 集成所有Specialist Agents（Anime/Attraction/Common）
- 使用统一的Agent接口进行调用
- 移除占位符，替换为真实的分析Agent

职责：
1. 接收用户输入和图片URL
2. 调用Router进行初步分类（复用现有逻辑）
3. 根据分类结果分发给对应的Specialist Agent
4. 收集分析结果并进行质量控制
5. 返回最终的分析结果供后续格式化

设计原则：
- 保持核心职责简洁，优先跑通流程
- 不引入复杂的质量控制机制（如重试、融合等）
- 为未来扩展预留接口（并行调用、冲突解决等）
"""
from langsmith import traceable

from app.common.logger import logger


@traceable(run_type="chain", name="supervisor_coordinator")
async def supervisor_coordinator(state: dict) -> dict:
    """
    Supervisor核心协调逻辑
    
    Args:
        state: 包含 user_input, image_url 的字典
        
    Returns:
        analysis_type: 分析类型（anime_analysis | attraction | common）
        analysis_result: 标准化分析结果
    """
    user_input = state.get("user_input", "")
    image_url = state.get("image_url")
    
    logger.info(f"[Supervisor] 开始协调任务 - user_input: {user_input[:50]}..., image_url: {'有' if image_url else '无'}")
    
    # ===================== Step 1: 初步分类 =====================
    # 复用现有的 image_analysis_router 节点进行类型判断
    from app.agent.image_analysis.nodes.analysis_router import image_analysis_router
    
    try:
        router_result = await image_analysis_router({"user_input": user_input})
        analysis_type = router_result.get("analysis_type", "common")
        logger.info(f"[Supervisor] 分类结果: {analysis_type}")
    except Exception as e:
        logger.error(f"[Supervisor] Router调用失败: {str(e)}")
        # 降级策略：默认使用通用分析
        analysis_type = "common"
    
    # ===================== Step 2: 分发到对应Agent =====================
    # Phase 3: 使用规范的Specialist Agents替代占位符
    
    try:
        if analysis_type == "anime_analysis":
            # 动漫专家Agent（Phase 3规范化版本）
            from app.agent.image_analysis.nodes.anime_analyzer import anime_analysis_agent
            result = await anime_analysis_agent({
                "user_input": user_input,
                "image_url": image_url
            })
            logger.info(f"[Supervisor] 动漫分析完成")
            
        elif analysis_type == "attraction":
            # 景点专家Agent（Phase 3新增）
            from app.agent.image_analysis.nodes.attraction_analyzer import attraction_analysis_agent
            result = await attraction_analysis_agent({
                "user_input": user_input,
                "image_url": image_url
            })
            logger.info(f"[Supervisor] 景点分析完成")
            
        else:
            # 通用分析Agent（Phase 3新增）
            from app.agent.image_analysis.nodes.common_analyzer import common_analysis_agent
            result = await common_analysis_agent({
                "user_input": user_input,
                "image_url": image_url
            })
            logger.info(f"[Supervisor] 通用分析完成")
    
    except Exception as e:
        logger.error(f"[Supervisor] Specialist Agent调用失败: {str(e)}")
        # 降级策略：返回错误信息
        result = {
            "analysis_result": {
                "error": str(e),
                "type": analysis_type,
                "description": "分析服务暂时不可用，请稍后重试"
            }
        }
    
    # ===================== Step 3: 质量控制（简单版本）=====================
    # 当前仅检查结果完整性，未来可扩展为：
    # - 置信度校验
    # - 多次重试机制
    # - 多Agent结果融合
    
    analysis_result = result.get("analysis_result", {})
    
    if not analysis_result:
        logger.warning(f"[Supervisor] 分析结果为空")
        analysis_result = {
            "error": "分析结果为空",
            "type": analysis_type,
            "description": "分析失败，请稍后重试"
        }
    elif analysis_result.get("error"):
        logger.warning(f"[Supervisor] 分析结果包含错误: {analysis_result.get('error')}")
    
    logger.info(f"[Supervisor] 协调完成 - type: {analysis_type}, has_error: {bool(analysis_result.get('error'))}")
    
    # ===================== Step 4: 返回结果 =====================
    return {
        "analysis_type": analysis_type,
        "analysis_result": analysis_result
    }
