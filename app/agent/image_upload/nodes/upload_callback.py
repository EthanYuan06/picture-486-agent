"""
昴云助手 - 图片上传回调节点
负责调用后端接口完成图片入库（含HITL确认和超时处理）
"""
import time
from langsmith import traceable

from app.common.logger import logger
from app.utils.callback_backend import callback_backend_sync

# HITL 超时配置（秒）
CONFIRMATION_TIMEOUT = 60


@traceable(run_type="chain", name="image_upload_callback")
async def image_upload_callback(state: dict) -> dict:
    """
    图片上传回调节点
    
    HITL流程：
    1. 检查用户是否确认
    2. 检查是否超时（60秒）
    3. 使用用户修改后的数据（如果有）
    4. 调用后端接口完成入库
    
    Args:
        state: 包含 user_id, space_id, image_url, analysis_result, user_confirmed, modified_data 的字典
        
    Returns:
        callback_result: 后端返回的结果
    """
    user_id = state.get("user_id")
    space_id = state.get("space_id")
    image_url = state.get("image_url")
    
    # ========== HITL：检查用户确认状态 ==========
    user_confirmed = state.get("user_confirmed")
    confirmation_timestamp = state.get("confirmation_timestamp")
    
    # 情况1：用户未确认（首次到达此节点，触发 interrupt）
    if user_confirmed is None:
        logger.info("[image_upload_callback] 等待用户确认（触发HITL中断）")
        # 这个return不会执行，因为interrupt_before会在此节点前中断
        return {}
    
    # 情况2：用户取消上传
    if user_confirmed is False:
        logger.info("[image_upload_callback] 用户取消上传")
        return {
            "callback_result": {
                "code": -1,
                "message": "用户取消上传",
                "data": None
            },
            "response_text": "❌ 已取消上传"
        }
    
    # 情况3：用户已确认，检查是否超时
    if confirmation_timestamp:
        elapsed_time = time.time() - confirmation_timestamp
        if elapsed_time > CONFIRMATION_TIMEOUT:
            logger.warning(f"[image_upload_callback] 确认超时：{elapsed_time:.1f}秒 > {CONFIRMATION_TIMEOUT}秒")
            return {
                "callback_result": {
                    "code": -1,
                    "message": f"确认超时（{CONFIRMATION_TIMEOUT}秒），请重新上传",
                    "data": None
                },
                "response_text": f"⏰ 确认超时（超过{CONFIRMATION_TIMEOUT}秒），请重新上传图片"
            }
        
        logger.info(f"[image_upload_callback] 用户确认通过（耗时{elapsed_time:.1f}秒）")
    
    # ========== 使用用户修改后的数据（如果有）==========
    modified_data = state.get("modified_data")
    if modified_data:
        logger.info("[image_upload_callback] 使用用户修改的数据")
        analysis_result = {
            "name": modified_data.get("name", "未命名图片"),
            "introduction": modified_data.get("introduction", "暂无描述"),
            "category": modified_data.get("category", "其他"),
            "tags": modified_data.get("tags", ["未识别"])
        }
        # 用户可能修改了上传位置
        if "space_id" in modified_data:
            space_id = modified_data["space_id"]
            logger.info(f"[image_upload_callback] 用户修改上传位置为: space_id={space_id}")
    else:
        analysis_result = state.get("analysis_result", {})
    
    # 参数校验
    if not user_id:
        logger.error("[image_upload_callback] 缺少 user_id")
        return {
            "callback_result": {
                "code": -1,
                "message": "缺少用户ID",
                "data": None
            },
            "response_text": "❌ 上传失败：缺少用户ID"
        }
    
    if not image_url:
        logger.error("[image_upload_callback] 缺少 image_url")
        return {
            "callback_result": {
                "code": -1,
                "message": "缺少图片URL",
                "data": None
            },
            "response_text": "❌ 上传失败：缺少图片URL"
        }
    
    try:
        logger.info(f"[image_upload_callback] 开始回调: user_id={user_id}, space_id={space_id}")
        
        # 调用后端回调（使用异步版本）
        from app.utils.callback_backend import _async_callback_backend
        result = await _async_callback_backend(
            user_id=user_id,
            space_id=space_id,
            image_url=image_url,
            analysis_result=analysis_result
        )
        
        logger.info(f"[image_upload_callback] 回调成功")
        
        # 构建成功消息
        data = result.get("data", {})
        success_msg = (
            f"✅ 图片上传成功！\n\n"
            f"名称：{data.get('name', analysis_result.get('name', '未命名'))}\n"
            f"分类：{data.get('category', analysis_result.get('category', '其他'))}\n\n"
            f"已保存到{'个人相册' if data.get('spaceId') or space_id else '公共图库'}"
        )
        
        # ✅ 只保留可序列化的字段（避免 dataclass 等不可序列化对象）
        callback_result = {
            "code": result.get("code"),
            "message": result.get("message"),
            "data": {
                "id": data.get("id"),
                "url": data.get("url"),
                "name": data.get("name"),
                "category": data.get("category"),
                "spaceId": data.get("spaceId")
            }
        }
        
        return {
            "callback_result": callback_result,
            "response_text": success_msg
        }
        
    except Exception as e:
        logger.error(f"[image_upload_callback] 回调失败: {str(e)}")
        error_msg = f"❌ 上传失败：{str(e)}"
        
        # ✅ 确保返回可序列化的字典
        return {
            "callback_result": {
                "code": -1,
                "message": f"回调失败: {str(e)}",
                "data": None
            },
            "response_text": error_msg
        }
