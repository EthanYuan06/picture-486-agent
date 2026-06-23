import os
from langchain_tavily import TavilySearch
from dotenv import load_dotenv

load_dotenv()
# web搜索工具,LangChain已封装，不需要@tool
web_search = TavilySearch(
    max_results=3,
    topic="general",
    api_key=os.environ.get("TAVILY_API_KEY"),
)