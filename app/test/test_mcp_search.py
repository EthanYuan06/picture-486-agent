"""
MCP 搜索功能测试脚本
用于验证 Bing Search MCP 工具是否能正常加载和调用
"""
import asyncio
from app.mcp.mcp_client import get_mcp_tools
from app.agent.model.model import deepseek_chat_model
from langchain_core.messages import HumanMessage, SystemMessage


async def test_mcp_tools_loading():
    """测试 MCP 工具加载"""
    print("=" * 60)
    print("🔍 测试 1: MCP 工具加载")
    print("=" * 60)
    
    try:
        tools = await get_mcp_tools()
        print(f"✅ 成功加载 {len(tools)} 个工具")
        
        for tool in tools:
            print(f"   - 工具名: {tool.name}")
            print(f"     描述: {tool.description[:100]}...")
        
        return tools
    except Exception as e:
        print(f"❌ 工具加载失败: {str(e)}")
        raise


async def test_tool_invocation(tools):
    """测试工具调用"""
    print("\n" + "=" * 60)
    print("🔍 测试 2: 工具调用触发")
    print("=" * 60)
    
    # 绑定工具到模型
    model_with_tools = deepseek_chat_model.bind_tools(tools)
    
    # 构造需要搜索的测试问题
    test_cases = [
        "今天上海的天气怎么样？",
        "最新的 AI 技术发展趋势是什么？"
    ]
    
    for i, question in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i}: {question} ---")
        
        messages = [
            SystemMessage(content="你是一个智能助手，当用户询问实时信息或最新知识时，请使用搜索工具获取准确答案。"),
            HumanMessage(content=question)
        ]
        
        try:
            response = await model_with_tools.ainvoke(messages)
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print(f"✅ 触发了工具调用！")
                for tc in response.tool_calls:
                    print(f"   工具名: {tc.get('name', 'N/A')}")
                    print(f"   参数: {tc.get('args', {})}")
            else:
                print(f"️ 未触发工具调用，直接回复:")
                print(f"   {response.content[:200]}...")
                
        except Exception as e:
            print(f" 调用失败: {str(e)}")


async def main():
    """主测试流程"""
    print("\n" + "🚀 开始 MCP 搜索功能测试" + "\n")
    
    try:
        # 测试 1: 工具加载
        tools = await test_mcp_tools_loading()
        
        # 测试 2: 工具调用
        await test_tool_invocation(tools)
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ 测试过程中出现错误: {str(e)}")
        print("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(main())
