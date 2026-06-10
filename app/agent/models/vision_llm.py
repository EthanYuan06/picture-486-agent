import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

# 加载环境变量
load_dotenv()


def init_vision_llm():
    llm = init_chat_model(
        model="qwen3.7-plus",
        api_key=os.environ.get('DASHSCOPE_API_KEY'),
        base_url=os.environ.get('DASHSCOPE_BASE_URL')
    )
    return llm


vision_llm = init_vision_llm()

