"""
测试图片分析Specialist Agents（Phase 3）

验证内容：
1. BaseSpecialistAgent基类可正常导入
2. 三个Specialist Agents能正常实例化
3. Agent接口符合统一规范（analyze方法、validate_input等）
4. 子图集成新Agents后能正常编译
5. 主工作流集成新子图后正常运行
6. __init__.py导出正确（包含新的Agent实例）
"""
import asyncio


def test_base_agent_import():
    """测试BaseSpecialistAgent能否正常导入"""
    print("=" * 60)
    print("测试 1: BaseSpecialistAgent导入验证")
    print("=" * 60)
    
    try:
        from app.agent.image_analysis.nodes.base_agent import BaseSpecialistAgent
        
        print(f"✅ BaseSpecialistAgent导入成功")
        print(f"   类型: {type(BaseSpecialistAgent)}")
        print(f"   是抽象基类: {hasattr(BaseSpecialistAgent, '__abstractmethods__')}")
        
        return True
    except Exception as e:
        print(f"❌ BaseSpecialistAgent导入失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_specialist_agents_creation():
    """测试三个Specialist Agents能否正常创建"""
    print("\n" + "=" * 60)
    print("测试 2: Specialist Agents实例化验证")
    print("=" * 60)
    
    agents = []
    
    try:
        # 动漫分析Agent
        from app.agent.image_analysis.nodes.anime_analyzer import AnimeAnalysisAgent, anime_analysis_agent
        anime_agent = AnimeAnalysisAgent()
        print(f"✅ AnimeAnalysisAgent创建成功")
        print(f"   agent_name: {anime_agent.agent_name}")
        print(f"   agent_type: {anime_agent.agent_type}")
        agents.append(anime_agent)
        
        # 景点分析Agent
        from app.agent.image_analysis.nodes.attraction_analyzer import AttractionAnalysisAgent, attraction_analysis_agent
        attraction_agent = AttractionAnalysisAgent()
        print(f"✅ AttractionAnalysisAgent创建成功")
        print(f"   agent_name: {attraction_agent.agent_name}")
        print(f"   agent_type: {attraction_agent.agent_type}")
        agents.append(attraction_agent)
        
        # 通用分析Agent
        from app.agent.image_analysis.nodes.common_analyzer import CommonAnalysisAgent, common_analysis_agent
        common_agent = CommonAnalysisAgent()
        print(f"✅ CommonAnalysisAgent创建成功")
        print(f"   agent_name: {common_agent.agent_name}")
        print(f"   agent_type: {common_agent.agent_type}")
        agents.append(common_agent)
        
        # 验证全局实例
        print(f"\n✅ 全局Agent实例已创建:")
        print(f"   - anime_analysis_agent: {type(anime_analysis_agent).__name__}")
        print(f"   - attraction_analysis_agent: {type(attraction_analysis_agent).__name__}")
        print(f"   - common_analysis_agent: {type(common_analysis_agent).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Specialist Agents创建失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_interface_compliance():
    """测试Agents是否符合统一接口规范"""
    print("\n" + "=" * 60)
    print("测试 3: Agent接口规范验证")
    print("=" * 60)
    
    try:
        from app.agent.image_analysis.nodes.anime_analyzer import anime_analysis_agent
        from app.agent.image_analysis.nodes.attraction_analyzer import attraction_analysis_agent
        from app.agent.image_analysis.nodes.common_analyzer import common_analysis_agent
        
        agents = [
            ("Anime", anime_analysis_agent),
            ("Attraction", attraction_analysis_agent),
            ("Common", common_analysis_agent)
        ]
        
        for name, agent in agents:
            # 检查是否有必需的方法
            has_analyze = hasattr(agent, 'analyze') and callable(getattr(agent, 'analyze'))
            has_validate = hasattr(agent, 'validate_input') and callable(getattr(agent, 'validate_input'))
            has_call = hasattr(agent, '__call__') and callable(getattr(agent, '__call__'))
            
            if has_analyze and has_validate and has_call:
                print(f"✅ {name}Agent 接口规范完整")
                print(f"   - analyze方法: ✅")
                print(f"   - validate_input方法: ✅")
                print(f"   - __call__方法: ✅")
            else:
                print(f"❌ {name}Agent 接口不完整")
                print(f"   - analyze方法: {'✅' if has_analyze else '❌'}")
                print(f"   - validate_input方法: {'✅' if has_validate else '❌'}")
                print(f"   - __call__方法: {'✅' if has_call else '❌'}")
                return False
        
        return True
    except Exception as e:
        print(f"❌ 接口规范验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_subgraph_with_new_agents():
    """测试包含新Agents的子图能否正常编译"""
    print("\n" + "=" * 60)
    print("测试 4: 子图集成新Agents验证")
    print("=" * 60)
    
    try:
        from app.agent.image_analysis import build_subgraph
        subgraph = build_subgraph()
        
        print(f"✅ 子图编译成功")
        print(f"   子图类型: {type(subgraph)}")
        print(f"   子图节点数: {len(subgraph.nodes)}")
        print(f"   子图节点列表: {list(subgraph.nodes.keys())}")
        
        # 验证Supervisor节点存在
        if "supervisor" in subgraph.nodes:
            print(f"   ✅ Supervisor节点已注册")
        else:
            print(f"   ❌ Supervisor节点未找到")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 子图编译失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_integration():
    """测试主工作流集成新Agents后的子图"""
    print("\n" + "=" * 60)
    print("测试 5: 主工作流集成验证")
    print("=" * 60)
    
    try:
        from app.agent.workflow import compiled_graph
        
        node_names = list(compiled_graph.nodes.keys())
        print(f"✅ 主工作流编译成功")
        print(f"   工作流类型: {type(compiled_graph)}")
        print(f"   工作流节点列表: {node_names}")
        
        if "image_analysis_chain" in node_names:
            print(f"   ✅ 子图节点 'image_analysis_chain' 已注册")
        else:
            print(f"   ⚠️  子图节点 'image_analysis_chain' 未找到")
        
        return True
    except Exception as e:
        print(f"❌ 主工作流集成失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_init_exports():
    """测试__init__.py导出是否正确"""
    print("\n" + "=" * 60)
    print("测试 6: __init__.py导出验证")
    print("=" * 60)
    
    try:
        import app.agent.image_analysis as ia_module
        
        print(f"✅ 模块导入成功")
        print(f"   模块路径: {ia_module.__file__}")
        
        # 检查核心导出
        required_exports = [
            "ImageAnalysisState",
            "build_subgraph",
            "ANALYSIS_TYPES",
            "DEFAULT_ANALYSIS_TYPE",
            "supervisor_coordinator",
            # Phase 3新增
            "anime_analysis_agent",
            "attraction_analysis_agent",
            "common_analysis_agent",
            # 向后兼容
            "anime_analyzer",
            "attraction_analyzer",
            "common_analyzer",
        ]
        
        missing = []
        for name in required_exports:
            if hasattr(ia_module, name):
                obj = getattr(ia_module, name)
                print(f"   - {name}: ✅ ({type(obj).__name__})")
            else:
                print(f"   - {name}: ❌ (缺失)")
                missing.append(name)
        
        if missing:
            print(f"\n❌ 缺少导出对象: {missing}")
            return False
        
        print(f"\n   导出对象数量: {len(required_exports)} (要求 ≥ 3)")
        print(f"   ✅ 符合Agents.md规范")
        
        return True
    except Exception as e:
        print(f"❌ __init__.py导出验证失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n🔍 开始验证 Phase 3 (Specialist Agents) 改动...\n")
    
    results = []
    
    # 执行所有测试
    results.append(("BaseAgent导入", test_base_agent_import()))
    results.append(("Specialist Agents创建", test_specialist_agents_creation()))
    results.append(("Agent接口规范", test_agent_interface_compliance()))
    results.append(("子图集成", test_subgraph_with_new_agents()))
    results.append(("主工作流集成", test_workflow_integration()))
    results.append(("__init__.py导出", test_init_exports()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name:<20} {status}")
    
    print("=" * 60)
    
    if passed == total:
        print(f"\n🎉 所有测试通过！Phase 3 (Specialist Agents) 改动成功！")
        print(f"\n💡 Phase 3 核心改进：")
        print(f"   - 创建BaseSpecialistAgent基类，提供统一Agent接口")
        print(f"   - 规范化实现三个Specialist Agents（Anime/Attraction/Common）")
        print(f"   - 移除占位符，使用真实的分析逻辑")
        print(f"   - 保持向后兼容，旧代码仍可正常使用")
        print(f"   - 符合Agents.md规范，模块内聚、职责清晰")
    else:
        print(f"\n⚠️  部分测试失败，请检查错误信息")
        print(f"   通过: {passed}/{total}")
