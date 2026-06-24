"""
昴云助手 - 图片上传分析器模块
负责图片上传时的智能分析（生成 name/introduction/category/tags）
"""
import time
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langsmith import traceable

from app.agent.model.model import qwen_vision_model
from app.agent.schemas import ImageUploadAnalysis
# 改动：从本地 prompts 目录导入提示词
from app.agent.image_upload.prompts.image_upload_prompt import get_image_upload_analysis_prompt
from app.common.logger import logger

# 初始化 Parser（模块级复用）
upload_analysis_parser = JsonOutputParser(pydantic_object=ImageUploadAnalysis)


@traceable(run_type="chain", name="image_upload_analyzer")
async def image_upload_analyzer(state: dict) -> dict:
    """
    图片上传智能分析节点
    
    调用多模态LLM（qwen_vision_model）分析图片，生成入库所需的智能字段：
    - name: 图片名称
    - introduction: 图片简介
    - category: 图片分类
    - tags: 标签列表
    
    Args:
        state: 包含 image_url 的字典
        
    Returns:
        analysis_result: 标准化的分析结果（dict格式）
        upload_confirmation: HITL确认信息
        confirmation_timestamp: 时间戳（用于超时判断）
    """
    image_url = state.get("image_url")
    
    if not image_url:
        logger.warning("[image_upload_analyzer] 缺少图片URL，返回默认值")
        analysis_result = {
            "name": "未命名图片",
            "introduction": "暂无描述",
            "category": "其他",
            "tags": ["未识别"]
        }
        upload_confirmation = {
            "name": analysis_result["name"],
            "introduction": analysis_result["introduction"],
            "category": analysis_result["category"],
            "tags": analysis_result["tags"],
            "space_id": state.get("space_id"),
            "message": "请确认是否上传此图片？您可以修改以下字段"
        }
        return {
            "analysis_result": analysis_result,
            "upload_confirmation": upload_confirmation,
            "confirmation_timestamp": time.time()
        }
    
    try:
        logger.info(f"[image_upload_analyzer] 开始分析图片: {image_url[:50]}...")
        
        # 构建多模态消息
        prompt = get_image_upload_analysis_prompt()
        messages = [
            SystemMessage(content="你是云相册智能助手的图片分析专家。"),
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ])
        ]
        
        # 调用多模态模型 + Output Parser
        response = await qwen_vision_model.ainvoke(messages)
        logger.info(f"[image_upload_analyzer] LLM原始返回完整内容:\n{response.content}")
        
        # 使用 Output Parser 自动解析和校验
        try:
            result = upload_analysis_parser.parse(response.content)
            logger.info(f"[image_upload_analyzer] Parser 解析成功")
        except Exception as e:
            logger.warning(f"[image_upload_analyzer] Parser 解析失败: {str(e)}，尝试手动提取JSON")
            # 降级：尝试手动提取 JSON（保持向后兼容）
            import json, re
            result = None
            
            # 尝试匹配 ```json ... ``` 或 ``` ... ``` 格式
            json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            match = re.search(json_pattern, response.content, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1))
                    logger.info("[image_upload_analyzer] 从Markdown代码块中提取JSON成功")
                except Exception as e2:
                    logger.warning(f"[image_upload_analyzer] 从代码块提取JSON失败: {str(e2)}")
            
            # 尝试直接查找最外层的 {...}
            if not result:
                brace_match = re.search(r'\{.*\}', response.content, re.DOTALL)
                if brace_match:
                    try:
                        result = json.loads(brace_match.group(0))
                        logger.info("[image_upload_analyzer] 从文本中提取JSON对象成功")
                    except Exception as e3:
                        logger.warning(f"[image_upload_analyzer] 提取JSON对象失败: {str(e3)}")
            
            # 如果都失败，使用默认值
            if not result:
                logger.error("[image_upload_analyzer] 所有解析方式均失败，使用默认值")
                result = {}
        
        # 构建标准化结果（Pydantic 已校验字段类型）
        analysis_result = {
            "name": result.get("name", "未命名图片"),
            "introduction": result.get("introduction", "暂无描述"),
            "category": result.get("category", "其他"),
            "tags": result.get("tags", ["未识别"])
        }
        
        # 确保tags是列表
        if not isinstance(analysis_result["tags"], list):
            analysis_result["tags"] = [str(analysis_result["tags"])]
        
        logger.info(f"[image_upload_analyzer] 分析完成: name={analysis_result['name']}, category={analysis_result['category']}")
        
        # HITL：构建确认信息
        upload_confirmation = {
            "name": analysis_result["name"],
            "introduction": analysis_result["introduction"],
            "category": analysis_result["category"],
            "tags": analysis_result["tags"],
            "space_id": state.get("space_id"),
            "message": "请确认是否上传此图片？您可以修改以下字段"
        }
        
        return {
            "analysis_result": analysis_result,
            "upload_confirmation": upload_confirmation,
            "confirmation_timestamp": time.time()  # 记录时间戳用于超时判断
        }
        
    except Exception as e:
        logger.error(f"[image_upload_analyzer] 分析失败: {str(e)}")
        analysis_result = {
            "name": "未命名图片",
            "introduction": "分析失败，请稍后重试",
            "category": "其他",
            "tags": ["未识别"]
        }
        
        # HITL：即使分析失败，也返回确认信息（让用户决定是否继续）
        upload_confirmation = {
            "name": analysis_result["name"],
            "introduction": analysis_result["introduction"],
            "category": analysis_result["category"],
            "tags": analysis_result["tags"],
            "space_id": state.get("space_id"),
            "message": "图片分析失败，您可以手动修改字段后上传"
        }
        
        return {
            "analysis_result": analysis_result,
            "upload_confirmation": upload_confirmation,
            "confirmation_timestamp": time.time()
        }
