"""
工作流通用工具函数
提供工作流中使用的通用辅助功能
"""
import json
from typing import Optional


def parse_filters(filters) -> Optional[dict]:
    """
    通用过滤器解析函数
    
    Args:
        filters: 可能是 dict、JSON 字符串或 None
        
    Returns:
        解析后的 dict 或 None
    """
    if not filters:
        return None
    
    if isinstance(filters, dict):
        return filters
    
    if isinstance(filters, str):
        try:
            return json.loads(filters)
        except json.JSONDecodeError:
            print(f"[parse_filters] Failed to parse filters JSON: {filters}")
            return None
    
    return None
