import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from .server_config import MCP_SERVERS

load_dotenv()


async def get_mcp_tools():
    """
    获取所有MCP工具
    
    Returns:
        list: LangChain工具列表，可用于Agent的工具调用
    """
    client = MultiServerMCPClient(MCP_SERVERS)
    return await client.get_tools()

