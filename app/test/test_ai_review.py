"""
AI审核模块测试脚本
验证模块导入和基本功能
"""
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)


def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("🧪 测试1: 模块导入")
    print("=" * 60)
    
    try:
        from app.agent.ai_review.state import AIReviewState
        print("✅ state.py 导入成功")
        
        from app.agent.ai_review.config import AIReviewConfig
        print("✅ config.py 导入成功")
        
        from app.agent.ai_review.nodes.content_safety import check_content_safety
        print("✅ content_safety.py 导入成功")
        
        from app.agent.ai_review.nodes.validation import validate_result
        print("✅ validation.py 导入成功")
        
        from app.agent.ai_review import ai_review_graph, execute_ai_review
        print("✅ workflow.py 导入成功")
        
        from app.agent.ai_review import callback_backend
        print("✅ callback.py 导入成功")
        
        from app.agent.ai_review.consumer import start_ai_review_consumer, stop_ai_review_consumer
        print("✅ consumer.py 导入成功")
        
        print("\n✅ 所有模块导入成功!\n")
        return True
    
    except Exception as e:
        print(f"\n❌ 模块导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """测试配置加载"""
    print("=" * 60)
    print("🧪 测试2: 配置加载")
    print("=" * 60)
    
    try:
        from app.agent.ai_review.config import AIReviewConfig
        
        print(f"RABBITMQ_HOST: {AIReviewConfig.RABBITMQ_HOST}")
        print(f"RABBITMQ_PORT: {AIReviewConfig.RABBITMQ_PORT}")
        print(f"BACKEND_URL: {AIReviewConfig.BACKEND_URL}")
        print(f"DASHSCOPE_API_KEY: {'已配置' if AIReviewConfig.DASHSCOPE_API_KEY else '未配置'}")
        print(f"CONTENT_SAFETY_MODEL: {AIReviewConfig.CONTENT_SAFETY_MODEL}")
        
        print("\n✅ 配置加载成功!\n")
        return True
    
    except Exception as e:
        print(f"\n❌ 配置加载失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_structure():
    """测试工作流结构"""
    print("=" * 60)
    print("🧪 测试3: 工作流结构")
    print("=" * 60)
    
    try:
        from app.agent.ai_review import ai_review_graph
        
        # 检查工作流是否有预期的节点
        nodes = list(ai_review_graph.nodes.keys())
        print(f"工作流节点: {nodes}")
        
        expected_nodes = ['check_content_safety', 'validate_result']
        for node in expected_nodes:
            if node in nodes:
                print(f"✅ 节点 '{node}' 存在")
            else:
                print(f"❌ 节点 '{node}' 缺失")
                return False
        
        print("\n✅ 工作流结构正确!\n")
        return True
    
    except Exception as e:
        print(f"\n❌ 工作流结构测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 AI审核模块测试开始")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("模块导入", test_imports()))
    results.append(("配置加载", test_config()))
    results.append(("工作流结构", test_workflow_structure()))
    
    # 汇总结果
    print("=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 60)
    if all_passed:
        print("🎉 所有测试通过!")
    else:
        print("⚠️  部分测试失败,请检查错误信息")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
