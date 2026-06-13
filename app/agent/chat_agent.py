from langchain.agents import create_agent

from app.agent.model.model import deepseek_chat_model, qwen_vision_model, multi_embedding_model
from app.agent.system_prompt import get_system_prompt
from app.agent.tools import web_search, multimodal_retrieve

# 【初始化主模型】使用qwen_vision_model作为主要推理引擎
# 该模型支持多模态输入，能够理解图片内容并生成结构化输出
main_llm = qwen_vision_model

# 【加载系统提示词】包含详细的工作流程指导和输出规范
# 必须先调用multimodal_retrieve工具，然后从metadata提取image_url
system_prompt = get_system_prompt()

# 【创建RAG Agent】
chat_rag_agent = create_agent(
    model=main_llm,
    tools=[web_search, multimodal_retrieve],  # 工具列表，Agent会根据需要选择调用
    system_prompt=system_prompt  # 系统提示词，指导Agent的行为规范
)

