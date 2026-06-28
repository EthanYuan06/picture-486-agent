"""MCP服务器配置管理"""
import json
from pathlib import Path
from typing import Dict, Any


def load_mcp_servers() -> Dict[str, Any]:
    """
    从JSON文件加载MCP服务器配置并转换为MultiServerMCPClient格式
    
    Returns:
        Dict[str, Any]: MCP服务器配置字典，格式为 {server_name: config}
    """
    config_path = Path(__file__).parent / "mcp_servers.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"MCP配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_config = json.load(f)
    
    # 转换格式：{"mcpServers": {...}} -> {...}
    servers_config = raw_config.get("mcpServers", {})
    
    if not servers_config:
        raise ValueError("MCP配置文件中未找到有效的服务器配置")
    
    return servers_config


# 导出配置供客户端使用
MCP_SERVERS = load_mcp_servers()
