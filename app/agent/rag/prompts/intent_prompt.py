"""
意图识别提示词模块
负责判断用户输入是否包含图片检索意图
"""


def get_intent_recognition_prompt(user_input: str) -> str:
    """
    生成意图识别提示词
    
    Args:
        user_input: 用户输入文本
        
    Returns:
        格式化的意图识别提示词
    """
    return f"""你是意图识别助手,判断用户输入是否包含「图片检索」意图。

用户输入:{user_input}

判断标准:
- 检索意图:用户想找图片、搜图、查询图片、推荐图片、描述图片内容、上传图片找相似等
- 闲聊意图:打招呼、问名字、聊天、询问功能等非检索类对话

只输出一个词:retrieval 或 chat
不要解释,不要其他内容。"""
