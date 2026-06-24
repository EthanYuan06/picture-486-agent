"""
意图识别提示词模块
负责判断用户输入是否包含图片检索意图

改造说明：
- 使用 LangChain ChatPromptTemplate 替代 f-string 拼接
- 支持 Few-shot 示例注入（提升准确率）
- 保持向后兼容（导出函数接口不变）
"""
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate


# Few-shot 示例：提升意图识别准确率
intent_examples = [
    {"input": "帮我找类似的风景图", "output": "retrieval"},
    {"input": "推荐相似的图片", "output": "retrieval"},
    {"input": "搜索蓝天白云的照片", "output": "retrieval"},
    {"input": "今天天气不错", "output": "chat"},
    {"input": "你好", "output": "chat"},
    {"input": "你叫什么名字", "output": "chat"},
]

# 主模板（包含 Few-shot 占位符）
intent_template = ChatPromptTemplate.from_messages([
    ("system", """你是意图识别助手，判断用户输入是否包含「图片检索」意图。

判断标准：
- retrieval: 用户想找图片、搜图、查询图片、推荐图片、描述图片内容、上传图片找相似等
- chat: 打招呼、问名字、聊天、询问功能等非检索类对话

只输出一个词：retrieval 或 chat
不要解释，不要其他内容。"""),
])

# 动态构建最终提示词（运行时注入 Few-shot）
def _build_final_prompt(user_input: str):
    """
    构建包含 Few-shot 的完整提示词
    
    Args:
        user_input: 用户输入文本
        
    Returns:
        完整的消息列表
    """
    messages = []
    
    # 添加 system 消息
    messages.extend(intent_template.messages)
    
    # 添加 Few-shot 示例
    for example in intent_examples:
        messages.append(("human", example["input"]))
        messages.append(("ai", example["output"]))
    
    # 添加用户输入
    messages.append(("human", user_input))
    
    return messages


# ===================== 向后兼容接口 =====================

def get_intent_recognition_prompt(user_input: str) -> str:
    """
    生成意图识别提示词（兼容旧接口）
    
    Args:
        user_input: 用户输入文本
        
    Returns:
        格式化的意图识别提示词字符串
    """
    messages = _build_final_prompt(user_input)
    # 转换为字符串格式（保持向后兼容）
    result = "\n".join([f"{role}: {content}" for role, content in messages])
    return result


def get_intent_recognition_prompt_messages(user_input: str) -> list:
    """
    返回 LangChain 消息列表（推荐用法）
    
    Args:
        user_input: 用户输入文本
        
    Returns:
        消息列表，可直接传给 LLM 的 invoke 方法
    """
    return _build_final_prompt(user_input)
