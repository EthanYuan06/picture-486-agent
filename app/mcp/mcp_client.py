import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()
async def get_mcp_tools():
    client = MultiServerMCPClient()
    return await client.get_tools()

