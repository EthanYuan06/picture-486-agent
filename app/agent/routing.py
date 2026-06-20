"""
昴云助手 - 路由模块
负责意图识别和一级路由决策
"""
from typing import List

from langchain_core.messages import HumanMessage, AIMessage
from langsmith import traceable

from app.agent.config import workflow_config as config
from app.agent.model.model import deepseek_chat_model
from app.agent.prompts import get_intent_recognition_prompt
from app.common.logger import logger


# ===================== 意图识别节点 =====================

@traceable(run_type="chain", name="intent_recognizer")  # 改动:添加 LangSmith 追踪
def intent_recognizer(state: dict) -> dict:
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
    for msg in reversed(all_messages):
        msg_type = None
        # 场景1：序列化后字典消息（线上/Checkpoint/Playground 主流场景）
        if isinstance(msg, dict):
            msg_type = msg.get("type", "").lower()
        # 场景2：内存中原生 Message 对象（本地调试场景）
        elif isinstance(msg, (HumanMessage, AIMessage)):
            msg_type = "human" if isinstance(msg, HumanMessage) else "ai"

        # 匹配人类消息，终止遍历
        if msg_type == "human":
            last_human_msg = msg
            break

    if not last_human_msg:
        return {"intent": "other", "user_input": "", "image_url": None}

    # ========== 核心修改：统一解析 字典/原生对象 的 content 内容 ==========
    content = None
    # 分支1：消息是序列化字典
    if isinstance(last_human_msg, dict):
        content = last_human_msg.get("content")
    # 分支2：消息是原生 Message 对象
    else:
        content = last_human_msg.content

    user_text = ""
    image_urls = []

    # 解析纯文本 content
    if isinstance(content, str):
        user_text = content
    # 解析 LangChain 标准多模态数组 content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    user_text += block.get("text", "")
                elif block_type == "image_url":
                    img_url_data = block.get("image_url", {})
                    if isinstance(img_url_data, dict):
                        url = img_url_data.get("url")
                        if url:
                            image_urls.append(url)
                    elif isinstance(img_url_data, str):
                        image_urls.append(img_url_data)
                    else:
                        url = block.get("url")
                        if url:
                            image_urls.append(url)

    # 去除首尾空白，过滤纯空输入
    user_input = user_text.strip()
    image_url = image_urls[0] if image_urls else None

    # 有图片URL时，调用 DeepSeek 判断是检索、分析还是闲聊
    if image_url:
        # 改动：使用 DeepSeek 模型智能判断图片意图（支持检索/分析/闲聊三种意图）
        intent_prompt = f"""你是意图识别助手。用户上传了一张图片并提问，请判断用户意图：

用户问题：{user_input}

判断标准：
- retrieval（检索）：用户想找相似图片、搜索相关图片、推荐类似内容等
- analysis（分析）：用户想知道图片内容、识别角色/地点、询问这是什么等
- chat（闲聊）：打招呼、评价图片、日常聊天等非检索非分析的对话

只输出一个词：retrieval、analysis 或 chat
不要解释，不要其他内容。"""
        
        try:
            resp = deepseek_chat_model.invoke(intent_prompt)
            intent_result = resp.content.strip().lower()
            
            # 改动：记录 DeepSeek 原始返回结果
            logger.info(f"[图片意图识别] 用户输入: '{user_input}', DeepSeek原始返回: '{intent_result}'")
            
            if "analysis" in intent_result:
                intent = "image_analysis"
            elif "chat" in intent_result:
                intent = "other"  # 闲聊意图
            else:
                intent = "image_retrieval"
            
            # 改动：记录最终判定的意图
            logger.info(f"[图片意图识别] 判定结果: {intent}")
        except Exception as e:
            # 改动：记录异常情况
            logger.error(f"[图片意图识别] DeepSeek调用失败: {str(e)}, 降级为图文检索")
            # 降级：默认视为图文检索
            intent = "image_retrieval"
        
        return {"intent": intent, "user_input": user_input, "image_url": image_url}

    # 无图片 → 调用 LLM 判断意图
    
    # 改动：使用提示词模块
    intent_prompt = get_intent_recognition_prompt(user_input)
    
    try:
        resp = deepseek_chat_model.invoke(intent_prompt)
        intent_result = resp.content.strip().lower()
        
        # 改动：记录纯文本意图识别结果
        logger.info(f"[纯文本意图识别] 用户输入: '{user_input}', DeepSeek原始返回: '{intent_result}'")
        
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
        # 改动：记录异常情况
        logger.error(f"[纯文本意图识别] DeepSeek调用失败: {str(e)}, 降级为关键词匹配")
        # 降级方案:关键词匹配
        if any(kw in user_input for kw in config.SEARCH_KEYWORDS):  # 改动：使用配置常量
            intent = "text_retrieval"
        else:
            intent = "other"

    return {"intent": intent, "user_input": user_input, "image_url": image_url}


# ===================== 一级路由函数 =====================

def route_after_intent(state: dict) -> str:
    """意图路由：根据意图分发到不同链路"""
    intent = state.get("intent", "other")
    if intent in ("text_retrieval", "image_retrieval"):
        return "retrieval_chain"
    elif intent == "image_analysis":
        return "image_analysis_chain"  # 改动：新增图片分析分支
    else:
        return "chat_chain"  # 闲聊
