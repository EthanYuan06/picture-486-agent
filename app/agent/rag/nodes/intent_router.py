"""
昴云助手 - 路由模块
负责意图识别和一级路由决策
"""
from typing import List

from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from app.agent.config import workflow_config as config
from app.agent.model.model import qwen_vision_model  # 改动：从 deepseek_chat_model 改为 qwen_vision_model
# 改动：从本地 prompts 目录导入提示词
from app.agent.rag.prompts.intent_prompt import get_intent_recognition_prompt
from app.common.logger import logger


# ===================== 意图识别节点 =====================

@traceable(run_type="chain", name="intent_recognizer")  # 改动:添加 LangSmith 追踪
async def intent_recognizer(state: dict) -> dict:
    """
    节点1:从 HumanMessage 提取输入并识别意图 (兼容原生对象 + LangGraph序列化字典消息)
    - 有图片URL → 直接判定为 image_retrieval
    - 无图片 → 调用 deepseek 判断是否为检索意图
    
    支持的输入格式:
    1. 纯文本: HumanMessage(content="你好")
    2. 标准图文: HumanMessage(content=[{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}}])
    3. 序列化字典: {"type": "human", "content": ...} (Checkpoint/Playground场景)
    """
    all_messages = list(state.get("messages", []))
    last_human_msg = None

    # ========== 核心修改：兼容序列化字典 + 原生Message对象，通过type字段判断 ==========
    # 倒序遍历，取最后一条人类消息
    logger.info(f"[意图识别] 收到 {len(all_messages)} 条消息")
    for idx, msg in enumerate(reversed(all_messages)):
        msg_type = None
        # 场景1：序列化后字典消息（线上/Checkpoint/Playground 主流场景）
        if isinstance(msg, dict):
            msg_type = msg.get("type", "").lower()
            logger.info(f"[意图识别] 消息{idx} 类型: dict, type字段: '{msg_type}'")
        # 场景2：内存中原生 Message 对象（本地调试场景）
        elif isinstance(msg, (HumanMessage, AIMessage)):
            msg_type = "human" if isinstance(msg, HumanMessage) else "ai"
            logger.info(f"[意图识别] 消息{idx} 类型: {type(msg).__name__}, 判定为: '{msg_type}'")

        # 匹配人类消息，终止遍历
        if msg_type == "human":
            last_human_msg = msg
            logger.info(f"[意图识别] 找到最后一条人类消息")
            break

    if not last_human_msg:
        logger.warning(f"[意图识别] 未找到人类消息，返回other意图")
        return {"intent": "other", "user_input": "", "image_url": None}

    # ========== 核心修改：统一解析 字典/原生对象 的 content 内容 ==========
    content = None
    # 分支1：消息是序列化字典
    if isinstance(last_human_msg, dict):
        content = last_human_msg.get("content")
        logger.info(f"[意图识别] 消息是字典格式，content类型: {type(content).__name__}")
    # 分支2：消息是原生 Message 对象
    else:
        content = last_human_msg.content
        logger.info(f"[意图识别] 消息是原生对象，content类型: {type(content).__name__}")

    user_text = ""
    image_urls = []

    # 解析纯文本 content
    if isinstance(content, str):
        user_text = content
        logger.info(f"[意图识别] content是字符串: '{user_text[:50]}...'")
    # 解析 LangChain 标准多模态数组 content
    elif isinstance(content, list):
        logger.info(f"[意图识别] content是列表，包含 {len(content)} 个元素")
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    text_content = block.get("text", "")
                    user_text += text_content
                    logger.info(f"[意图识别] 提取文本块: '{text_content[:50]}...'")
                elif block_type == "image_url":
                    img_url_data = block.get("image_url", {})
                    if isinstance(img_url_data, dict):
                        url = img_url_data.get("url")
                        if url:
                            image_urls.append(url)
                            logger.info(f"[意图识别] 提取图片URL (dict格式): {url[:80]}...")
                    elif isinstance(img_url_data, str):
                        image_urls.append(img_url_data)
                        logger.info(f"[意图识别] 提取图片URL (str格式): {img_url_data[:80]}...")
                    else:
                        url = block.get("url")
                        if url:
                            image_urls.append(url)
                            logger.info(f"[意图识别] 提取图片URL (block.url): {url[:80]}...")

    # 去除首尾空白，过滤纯空输入
    user_input = user_text.strip()
    image_url = image_urls[0] if image_urls else None
    
    logger.info(f"[意图识别] 最终解析结果 - user_input: '{user_input}', image_url: {'有' if image_url else '无'}")

    # 有图片URL时，调用 qwen_vision_model 判断是检索、分析还是闲聊
    if image_url:
        # 改动：使用 qwen_vision_model 多模态模型智能判断图片意图（支持检索/分析/上传/闲聊四种意图）
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": f"""你是意图识别助手。请根据用户的文字描述和图片综合判断意图。

⚠️ 重要原则：用户的文字描述优先级高于图片内容！

用户问题：{user_input}

判断标准（按优先级排序）：
1. upload（上传）：用户明确表达上传、保存、存图意图，如"上传到公共图库"、"保存到相册"、"存到我的xx相册"等 → **只要出现这类关键词，直接判定为upload**
2. retrieval（检索）：用户想找相似图片、搜索相关图片、推荐类似内容等
3. analysis（分析）：用户想知道图片内容、识别角色/地点、询问这是什么等
4. chat（闲聊）：打招呼、评价图片、日常聊天等非检索非分析的对话

只输出一个词：retrieval、analysis、upload 或 chat
不要解释，不要其他内容。"""},
                {"type": "image_url", "image_url": {"url": image_url}}
            ])
        ]
        
        try:
            resp = await qwen_vision_model.ainvoke(messages)  # 改动：传入多模态消息
            intent_result = resp.content.strip().lower()
            
            # 改动：记录 Qwen 原始返回结果
            logger.info(f"[图片意图识别] 用户输入: '{user_input}', Qwen原始返回: '{intent_result}'")
            
            # 【关键修复】提取最后一个非空单词作为意图，避免 LLM 输出推理过程导致误判
            # LLM 可能返回 "<think>...</think>\n\nretrieval"，我们只需要最后的 "retrieval"
            words = intent_result.split()
            final_word = words[-1] if words else ""  # 取最后一个词
            
            # 精确匹配最终意图词
            if final_word == "upload":
                intent = "image_upload"
            elif final_word == "analysis":
                intent = "image_analysis"
            elif final_word == "retrieval":
                intent = "image_retrieval"
            elif final_word == "chat":
                intent = "other"  # 闲聊意图
            else:
                # 兜底：如果最后一个词不匹配，尝试在整个内容中查找关键词（按优先级）
                if "upload" in intent_result and "retrieval" not in intent_result:
                    intent = "image_upload"
                elif "analysis" in intent_result:
                    intent = "image_analysis"
                elif "retrieval" in intent_result:
                    intent = "image_retrieval"
                elif "chat" in intent_result:
                    intent = "other"
                else:
                    # 最终兜底：默认视为检索意图（更安全）
                    intent = "image_retrieval"
            
            # 改动：记录最终判定的意图
            logger.info(f"[图片意图识别] 判定结果: {intent}")
        except Exception as e:
            # 改动：调用失败时返回错误提示，不再降级
            logger.error(f"[图片意图识别] Qwen调用失败: {str(e)}")
            return {
                "intent": "error",  # 新增：错误意图标识
                "user_input": user_input,
                "image_url": image_url,
                "error_message": f"❌ 图片分析服务暂时不可用，请稍后重试\n\n错误信息：{str(e)}"
            }
        
        return {"intent": intent, "user_input": user_input, "image_url": image_url}

    # 无图片 → 调用 LLM 判断意图
    
    # 改动：使用提示词模块 + qwen_vision_model
    intent_prompt = get_intent_recognition_prompt(user_input)
    
    try:
        messages = [HumanMessage(content=intent_prompt)]  # 改动：构建消息对象
        resp = await qwen_vision_model.ainvoke(messages)  # 改动：使用 qwen_vision_model 替代 deepseek_chat_model
        intent_result = resp.content.strip().lower()
        
        # 改动：记录纯文本意图识别结果
        logger.info(f"[纯文本意图识别] 用户输入: '{user_input}', Qwen原始返回: '{intent_result}'")
        
        # 解析 LLM 返回结果
        if "retrieval" in intent_result:
            intent = "text_retrieval"
        elif "chat" in intent_result:
            intent = "other"
        else:
            # 兜底:默认视为闲聊
            intent = "other"
        
        # 改动：记录最终判定的意图
        logger.info(f"[纯文本意图识别] 判定结果: {intent}")
            
    except Exception as e:
        # 改动：调用失败时返回错误提示，不再降级
        logger.error(f"[纯文本意图识别] Qwen调用失败: {str(e)}")
        return {
            "intent": "error",  # 新增：错误意图标识
            "user_input": user_input,
            "image_url": None,
            "error_message": f"❌ 意图识别服务暂时不可用，请稍后重试\n\n错误信息：{str(e)}"
        }

    return {"intent": intent, "user_input": user_input, "image_url": image_url}


# ===================== 一级路由函数 =====================

def route_after_intent(state: dict) -> str:
    """意图路由：根据意图分发到不同链路"""
    intent = state.get("intent", "other")
    if intent in ("text_retrieval", "image_retrieval"):
        return "retrieval_chain"
    elif intent == "image_analysis":
        return "image_analysis_chain"  # 改动：新增图片分析分支
    elif intent == "image_upload":
        return "image_upload_chain"  # 新增：图片上传分支
    else:
        return "chat_chain"  # 闲聊
