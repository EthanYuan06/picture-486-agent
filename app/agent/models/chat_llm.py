import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model


# 加载环境变量
load_dotenv()


def init_text_llm():
    llm = init_chat_model(
        model="deepseek-v4-flash",
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url=os.environ.get('DEEPSEEK_BASE_URL')
    )
    return llm




