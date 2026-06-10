from typing import List, Dict

from langchain.messages import HumanMessage, SystemMessage
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, END

from app.agent.models.embedding_llm import embedding_llm
from app.agent.models.vision_llm import vision_llm

# 1. 定义全局状态 (State)
class AgentState(TypedDict):
    user_text: str                  # 用户输入的文字
    image_url: str               # 用户输入的图片url，无图为空
    extracted_attributes: str       # Qwen3.7-plus 提取的图片属性 JSON
    search_query: str               # 拼接后的搜索文本
    search_vector: List[float]      # Qwen3-VL-Embedding 生成的向量
    retrieved_items: List[Dict]     # 向量库检索返回的 Top K 结果
    final_response: str             # DeepSeek 生成的最终回复

# 2. 定义各个节点函数 (Nodes)
def extract_attributes(state: AgentState) -> AgentState:
    """节点1: 调用 qwen3.7-plus 提取图片属性 (仅在有图时执行)"""
    response = vision_llm.invoke(
        [
            SystemMessage(
                content=(
                    "你是图片属性提取助手。"
                    '只返回 JSON 对象，格式为 {"main_object": string, "attributes": string[]}。'
                )
            ),
            HumanMessage(
                content=[
                    {"type": "text", "text": state["user_text"]},
                    {"type": "image_url", "image_url": {"url": state["image_url"]}},
                ]
            ),
        ],
        response_format={"type": "json_object"},
        max_tokens=180,
    )
    if not isinstance(response.content, str):
        raise TypeError("qwen3.7-plus 返回内容不是 JSON 字符串")
    return {"extracted_attributes": response.content}

def build_search_query(state: AgentState) -> AgentState:
    """节点2: 构建统一的搜索文本"""
    if state["extracted_attributes"]:
        # 图文混合：拼接用户文字与提取的属性
        query = f"用户需求：{state['user_text']} | 图片属性：{state['extracted_attributes']}"
    else:
        # 纯文本：直接使用用户文字
        query = f"图片查询：{state['user_text']}"
    return {"search_query": query}

def generate_embedding(state: AgentState) -> AgentState:
    """节点3: 调用 qwen3-vl-embedding 生成向量"""
    vector = embedding_llm.embed(
        image_url=state.get("image_url"),
        text=state["search_query"],
    )
    return {"search_vector": vector}

def vector_search(state: AgentState) -> AgentState:
    """节点4: 向量库检索"""
    # TODO: 使用 search_vector 在向量库中检索 Top 5
    # 返回包含商品信息的字典列表
    items = [
        {"id": "A001", "title": "浅蓝色雪纺连衣裙", "price": 199},
        {"id": "A002", "title": "米白色碎花连衣裙", "price": 259}
    ]
    return {"retrieved_items": items}

def generate_response(state: AgentState) -> AgentState:
    """节点5: 调用 deepseek-v4-flash 生成最终回复"""
    # TODO: 将 retrieved_items 和 user_text 组装成 Prompt
    # 调用 deepseek-v4-flash API
    response = "根据您的需求，为您推荐这两款颜色较浅的连衣裙..."
    return {"final_response": response}

# 3. 定义路由条件 (Conditional Edge)
def route_by_image(state: AgentState) -> str:
    """判断是否有图片输入，决定走哪条分支"""
    if state.get("image_url"):
        return "extract_attributes"  # 有图：先提取属性
    else:
        return "build_search_query"  # 无图：直接构建查询

# 4. 构建 LangGraph 工作流
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("extract_attributes", extract_attributes)
workflow.add_node("build_search_query", build_search_query)
workflow.add_node("generate_embedding", generate_embedding)
workflow.add_node("vector_search", vector_search)
workflow.add_node("generate_response", generate_response)

# 设置入口与条件分支
workflow.set_conditional_entry_point(
    route_by_image,
    {
        "extract_attributes": "extract_attributes",
        "build_search_query": "build_search_query"
    }
)

# 定义固定边 (Edges)
# 提取属性后 -> 构建查询
workflow.add_edge("extract_attributes", "build_search_query")
# 构建查询后 -> 生成向量
workflow.add_edge("build_search_query", "generate_embedding")
# 生成向量后 -> 检索
workflow.add_edge("generate_embedding", "vector_search")
# 检索后 -> 生成回复
workflow.add_edge("vector_search", "generate_response")
# 生成回复后 -> 结束
workflow.add_edge("generate_response", END)

# 编译图
app = workflow.compile()
