"""
AnimeTrace API 异常处理工具
提供状态码映射和错误信息获取功能
"""


# 业务状态码错误消息映射
# 注意：code=0 表示识别成功，不在错误映射中
BUSINESS_ERROR_MESSAGES = {
    17721: "未识别到对应内容",
    17701: "图片体积过大，请压缩图片后重试",
    17702: "服务器繁忙，请稍后再尝试调用",
    17703: "请求参数错误，请检查图片URL是否有效",
    17704: "API处于维护中，当前无法使用该工具",
    17705: "图片格式不支持，请更换图片重试",
    17706: "服务内部错误，请稍后重试",
    17707: "服务内部错误，请稍后重试",
    17708: "图片内人物数量超出限制，请更换图片",
    17722: "图片URL下载失败，请检查链接有效性",
    17728: "接口调用次数已达上限，停止调用",
    17731: "访问人数过多，请稍后重试",
}

# HTTP状态码错误消息映射
HTTP_ERROR_MESSAGES = {
    404: "接口地址失效",
    413: "图片体积过大，请压缩图片后重试",
    503: "服务器繁忙，请稍后再尝试调用",
    403: "API处于维护中，当前无法使用该工具",
}


def get_error_message(code: int, is_http: bool = False) -> str:
    """
    根据状态码获取错误提示消息
    
    Args:
        code: 状态码（业务码或HTTP状态码）
        is_http: 是否为HTTP状态码
    
    Returns:
        错误提示消息字符串
    """
    if is_http:
        return HTTP_ERROR_MESSAGES.get(
            code, 
            f"请求失败 (HTTP {code})，请稍后重试"
        )
    else:
        return BUSINESS_ERROR_MESSAGES.get(
            code, 
            f"未知错误 (code: {code})，请稍后重试"
        )


def format_anime_result(data: list) -> str:
    """
    格式化动漫识别成功结果
    
    Args:
        data: API返回的data字段（数组格式）
    
    Returns:
        格式化的识别结果字符串
    """
    # 改动：处理data为数组的情况
    if not data or not isinstance(data, list) or len(data) == 0:
        return "识别成功，但未获取到详细信息"
    
    # 取第一个元素（最优结果）
    first_item = data[0]
    if not isinstance(first_item, dict):
        return "识别成功，但数据格式异常"
    
    characters = first_item.get("character", [])
    
    # 取第一个角色（最准确的结果）
    if not characters or not isinstance(characters, list) or len(characters) == 0:
        return "识别成功，但未找到角色信息"
    
    first_character = characters[0]
    if not isinstance(first_character, dict):
        return "识别成功，但角色数据格式异常"
    
    # 提取作品名和角色名
    work = first_character.get("work", "")
    character_name = first_character.get("character", "")
    
    # 组合结果
    if work and character_name:
        return f"{character_name} | {work}"
    elif character_name:
        return f"角色：{character_name}"
    elif work:
        return f"番剧：{work}"
    else:
        return "识别成功，但未获取到详细信息"
