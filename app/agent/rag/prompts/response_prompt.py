"""
响应生成提示词模块
负责将检索结果整理为用户友好的回复
"""


def get_response_generation_prompt(user_q: str, context: str) -> str:
    """
    生成检索结果响应提示词
    
    Args:
        user_q: 用户原始查询
        context: 检索到的图片信息（已格式化为「名称 + 简介」格式）
        
    Returns:
        格式化的响应生成提示词
    """
    return (
        f"你是「昴云助手」，专业的图片检索AI。请用简洁友好的语气回复用户，告知找到的图片信息。\n\n"
        f"用户问题：{user_q}\n\n"
        f"检索到的图片信息（每张图片包含名称和简介）：\n{context}\n\n"
        f"要求：\n"
        f"1. 开头用「以下是为您找到的[主题]的图片：」\n"
        f"2. 对每张图片的展示格式：「[序号] 图片名称：{{名称}}，简介：{{简介}}」\n"
        f"   - **必须严格使用元数据中的简介字段，不要自行编造或解释**\n"
        f"   - 如果某张图片没有简介，只写「图片名称：{{名称}}」即可，不要添加任何描述\n"
        f"   - 绝对不要对图片内容进行推测、解读或自由发挥\n"
        f"3. 结尾加一句「我还可以帮您推荐其他图片，如有需要请告诉我哦～」\n"
        f"4. 保持自然友好，不要暴露技术细节"
    )


def get_no_result_response() -> str:
    """
    无检索结果时的回复
    
    Returns:
        无结果提示文本
    """
    return "抱歉，图库中没有找到相关图片"


def get_fallback_response(doc_count: int) -> str:
    """
    LLM调用失败时的降级回复
    
    Args:
        doc_count: 检索到的文档数量
        
    Returns:
        降级回复文本
    """
    return f"以下是为您找到的相关图片，共 {doc_count} 张：\n我还可以帮您推荐其他图片，如有需要请告诉我哦"


def get_analysis_prompt_template(analysis_type: str, result: dict) -> str:
    """
    获取图片分析的通用提示词模板（改动：新增通用分析格式化函数）
    
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
        "2. 适当使用 emoji（如 🎬、🌟、、🎨、😊 等）让文案更生动\n"
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
