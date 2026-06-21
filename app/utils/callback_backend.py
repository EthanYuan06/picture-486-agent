"""
昴云助手 - 后端回调工具模块
负责异步调用后端接口完成图片入库
"""
import os
import asyncio
import httpx
import json
from typing import Optional, List
from dataclasses import dataclass
from app.common.logger import logger


# ==================== 响应DTO类 ====================

@dataclass
class PictureVo:
    """图片视图对象（后端返回的data字段结构）"""
    id: int
    url: str
    thumbnailUrl: Optional[str] = None
    name: Optional[str] = None
    introduction: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None  # JSON字符串格式
    picSize: Optional[int] = None
    picWidth: Optional[int] = None
    picHeight: Optional[int] = None
    picScale: Optional[float] = None
    picFormat: Optional[str] = None
    userId: Optional[int] = None
    spaceId: Optional[int] = None
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
    
    def get_tags_list(self) -> List[str]:
        """将tags JSON字符串转换为列表"""
        if self.tags:
            try:
                return json.loads(self.tags)
            except Exception:
                return []
        return []


@dataclass
class BaseResponse:
    """统一响应对象"""
    code: int
    data: Optional[PictureVo] = None
    message: Optional[str] = None
    
    def is_success(self) -> bool:
        """判断请求是否成功"""
        return self.code == 0 and self.data is not None


def _parse_response(response_json: dict) -> BaseResponse:
    """
    解析JSON响应为BaseResponse对象
    
    Args:
        response_json: 后端返回的JSON字典
        
    Returns:
        BaseResponse对象
    """
    code = response_json.get("code", -1)
    message = response_json.get("message", "unknown")
    
    data = None
    if code == 0 and "data" in response_json:
        data_dict = response_json["data"]
        data = PictureVo(
            id=data_dict.get("id"),
            url=data_dict.get("url"),
            thumbnailUrl=data_dict.get("thumbnailUrl"),
            name=data_dict.get("name"),
            introduction=data_dict.get("introduction"),
            category=data_dict.get("category"),
            tags=data_dict.get("tags"),
            picSize=data_dict.get("picSize"),
            picWidth=data_dict.get("picWidth"),
            picHeight=data_dict.get("picHeight"),
            picScale=data_dict.get("picScale"),
            picFormat=data_dict.get("picFormat"),
            userId=data_dict.get("userId"),
            spaceId=data_dict.get("spaceId"),
            createTime=data_dict.get("createTime"),
            updateTime=data_dict.get("updateTime")
        )
    
    return BaseResponse(code=code, data=data, message=message)


async def _async_callback_backend(
    user_id: int,
    space_id: Optional[int],
    image_url: str,
    analysis_result: dict
) -> dict:
    """
    异步回调后端接口，完成图片入库
    
    Args:
        user_id: 用户ID
        space_id: 相册ID（null表示公共图库）
        image_url: 图片URL（COS临时目录地址）
        analysis_result: AI分析结果（包含name/introduction/category/tags）
        
    Returns:
        后端返回的结果字典
        
    Raises:
        Exception: 回调失败时抛出异常
    """
    backend_url = os.getenv("BACKEND_URL")
    api_key = os.getenv("AI_SERVICE_API_KEY")
    
    if not backend_url or not api_key:
        raise ValueError("BACKEND_URL 或 AI_SERVICE_API_KEY 未配置")
    
    # 组装回调数据
    payload = {
        "userId": user_id,
        "spaceId": space_id,
        "url": image_url,
        "name": analysis_result.get("name", "未命名图片"),
        "introduction": analysis_result.get("introduction", "暂无描述"),
        "category": analysis_result.get("category", "其他"),
        "tags": analysis_result.get("tags", ["未识别"]),
        "apiKey": api_key
    }
    
    logger.info(f"[回调后端] 开始回调: userId={user_id}, spaceId={space_id}")
    logger.debug(f"[回调后端] 请求体: {payload}")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{backend_url}/api/picture/ai/callback",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                # 检查HTTP状态码
                response.raise_for_status()
                
                result = response.json()
                logger.info(f"[回调后端] HTTP状态码: {response.status_code}, 响应: {result}")
                
                # 解析为结构化响应对象（用于日志和调试）
                base_response = _parse_response(result)
                
                # 检查业务状态码
                if base_response.is_success():
                    logger.info(f"[回调成功] 图片ID: {base_response.data.id}, URL: {base_response.data.url}")
                    # 保持向后兼容：仍返回原始dict格式，附加解析后的对象
                    result["_parsed_data"] = base_response  # 可选：供未来使用
                    return result
                else:
                    error_msg = base_response.message or "未知错误"
                    logger.warning(f"[回调失败] 第{attempt + 1}次尝试: {error_msg}")
                    
                    # 如果不是最后一次尝试，等待后重试
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数退避：2s, 4s
                        logger.info(f"[回调后端] 等待{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        raise Exception(f"后端返回错误: {error_msg}")
                        
        except httpx.HTTPStatusError as e:
            logger.error(f"[回调HTTP错误] 第{attempt + 1}次尝试: {e.response.status_code} - {e.response.text}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise Exception(f"HTTP请求失败: {e.response.status_code}")
                
        except httpx.TimeoutException as e:
            logger.error(f"[回调超时] 第{attempt + 1}次尝试: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise Exception("请求超时，请稍后重试")
                
        except Exception as e:
            logger.error(f"[回调异常] 第{attempt + 1}次尝试: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise Exception(f"回调后端失败: {str(e)}")
    
    raise Exception("回调后端失败，已达最大重试次数")


def callback_backend_sync(
    user_id: int,
    space_id: Optional[int],
    image_url: str,
    analysis_result: dict
) -> dict:
    """
    同步包装器：在同步函数中调用异步回调
    
    Args:
        user_id: 用户ID
        space_id: 相册ID（null表示公共图库）
        image_url: 图片URL
        analysis_result: AI分析结果
        
    Returns:
        后端返回的结果字典
    """
    try:
        result = asyncio.run(_async_callback_backend(user_id, space_id, image_url, analysis_result))
        return result
    except Exception as e:
        logger.error(f"[回调后端同步包装] 失败: {str(e)}")
        raise
