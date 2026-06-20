import os
from typing import List, Tuple, Optional
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
import dashscope
from app.utils.anime_trace import get_error_message, format_anime_result
from app.agent.chroma_init import chroma_vector_store
from app.agent.model.model import multi_embedding_model

load_dotenv()

# 配置 DashScope API 地址
dashscope.base_http_api_url = "https://dashscope.aliyuncs.com/api/v1"

@tool
def anime_analysis(image_url: str) -> str:
    """
    【工具名称】动漫画面识别工具
    
    识别动漫、二次元、Galgame类公网图片，溯源获取作品、角色等核心信息
    
    Args:
        image_url: 公网图片URL地址（必填）
    
    Returns:
        str: 识别结果或错误提示信息
            - 成功: "角色名 | 番剧名(日文)"
            - 失败: 对应的用户友好提示语
    """
    import requests
    
    # 参数验证
    if not image_url or not image_url.strip():
        return "请求参数错误，请检查图片URL是否有效"
    
    # 构造请求
    api_url = "https://api.animetrace.com/v1/search"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "url": image_url,
        "is_multi": 0,          # 固定参数：仅返回单条最优结果
        "model": "pre_stable"   # 固定参数：使用指定识别模型
    }
    
    try:
        # 发送POST请求
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        # 处理HTTP错误状态码
        if response.status_code != 200:
            return get_error_message(response.status_code, is_http=True)
        
        # 解析JSON响应
        try:
            result = response.json()
        except Exception:
            return "响应数据格式异常，请稍后重试"
        
        # 获取业务状态码
        code = result.get("code")
        
        # 识别成功（code=0 表示成功）
        if code == 0:
            return format_anime_result(result.get("data", []))
        
        # 其他已知错误码
        return get_error_message(code, is_http=False)
    
    except requests.exceptions.Timeout:
        return "请求超时，请稍后重试"
    except requests.exceptions.ConnectionError:
        return "网络连接失败，请检查网络"
    except Exception as e:
        return f"调用失败: {str(e)}"

# web搜索工具,LangChain已封装，不需要@tool
web_search = TavilySearch(
    max_results=3,
    topic="general",
    api_key=os.environ.get("TAVILY_API_KEY"),
)
