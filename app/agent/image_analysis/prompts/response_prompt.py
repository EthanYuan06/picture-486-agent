"""
云助手 - 图片分析响应生成提示词模块
负责将结构化分析结果整理为用户友好的自然语言回复

职责：
1. 提供通用的图片分析格式化提示词模板
2. 根据不同分析类型（动漫/景点/通用）添加特定要求
3. 保持语气亲切自然，适当使用emoji增强可读性
"""


def get_analysis_prompt_template(analysis_type: str, result: dict) -> str:
    """
    获取图片分析的通用提示词模板
    
    Args:
        analysis_type: 分析类型（anime_analysis | attraction | common）
        result: 分析结果的JSON字典
        
    Returns:
        格式化的分析结果整理提示词
    """
    # 基础提示词模板
    base_prompt = (
        "你是一个专业的图片分析助手，擅长将结构化数据转化为生动有趣的自然语言回复。\n\n"
        f"分析类型：{analysis_type}\n"
        f"分析结果（JSON格式）：\n{result}\n\n"
        "✨ 任务要求：\n"
        "1. 用亲切、自然的语气与用户交流，像朋友聊天一样\n"
        "2. 适当使用 emoji（如 🎬、、、🎨、😊 等）让文案更生动\n"
        "3. 突出关键信息（角色名、作品名、地点、背景故事等）\n"
        "4. 控制在 100-200 字以内，简洁但有温度\n"
        "5. 结尾可以用一句温馨的总结或互动语\n\n"
        "请直接输出整理后的回复文本，不要包含其他说明。"
    )
    
    # 根据不同类型添加特定要求
    type_specific_requirements = {
        "anime_analysis": (
            "\n\n🎯 动漫分析特殊要求：\n"
            "- 如果是动漫角色，可以补充有趣的背景知识或冷知识\n"
            "- 提及角色的性格特点、经典台词或名场面\n"
            "- 可以适当玩梗，增加趣味性"
        ),
        "attraction": (
            "\n\n🏞️ 景点识别特殊要求：\n"
            "- 介绍景点的历史背景、文化意义或建造年份\n"
            "- 提供游玩建议或最佳观赏时间\n"
            "- 可以提及相关的传说或趣闻"
        ),
        "common": (
            "\n\n🎨 通用分析特殊要求：\n"
            "- 根据图片内容提取关键信息，撰写吸引人的文案\n"
            "- 如果是美食，描述色香味；如果是物品，突出特色\n"
            "- 适合社交媒体分享的风格（可添加话题标签）"
        )
    }
    
    # 拼接特定要求
    specific_req = type_specific_requirements.get(analysis_type, "")
    
    return base_prompt + specific_req
