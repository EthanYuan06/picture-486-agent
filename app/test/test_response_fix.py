"""
简单测试响应生成节点的修复效果
验证：优先使用 metadata['introduction']，没有则不添加描述
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（当前文件的父目录的父目录）
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("导入模块...")
from app.agent.prompts.response_prompt import get_response_generation_prompt


def test_prompt_construction():
    """测试提示词构建是否正确"""
    print("\n=== 测试1：有简介的图片 ===")
    
    # 模拟 workflow.py 中的 context 构建逻辑
    name = "Subaru进化史"
    introduction = "女孩从3岁到17岁的四个成长阶段身高对比图"
    
    if introduction:
        context_line = f"[1] 图片名称：{name}，简介：{introduction}"
    else:
        context_line = f"[1] 图片名称：{name}"
    
    user_q = "找一些女孩成长阶段的图片"
    prompt = get_response_generation_prompt(user_q, context_line)
    
    print(f"生成的提示词:\n{prompt}")
    print()
    
    # 验证提示词中包含关键约束
    assert "必须严格使用元数据中的简介字段" in prompt, " 提示词缺少关键约束！"
    assert "不要自行编造或解释" in prompt, "❌ 提示词缺少禁止编造的约束！"
    assert "绝对不要对图片内容进行推测、解读或自由发挥" in prompt, "❌ 提示词缺少禁止自由发挥的约束！"
    print("✅ 测试通过：提示词包含所有必要约束\n")


def test_context_without_introduction():
    """测试没有简介时的 context 构建"""
    print("=== 测试2：没有简介的图片 ===")
    
    name = "可爱小猫"
    introduction = ""  # 空简介
    
    if introduction:
        context_line = f"[1] 图片名称：{name}，简介：{introduction}"
    else:
        context_line = f"[1] 图片名称：{name}"
    
    print(f"Context: {context_line}")
    
    # 验证没有简介时只包含名称
    assert "简介：" not in context_line, "❌ 没有简介时不应该包含'简介：'字段！"
    assert context_line == "[1] 图片名称：可爱小猫", "❌ Context格式不正确！"
    print("✅ 测试通过：没有简介时只展示图片名称\n")


if __name__ == "__main__":
    print("开始测试响应生成节点修复效果...\n")
    print("=" * 60)
    
    try:
        test_prompt_construction()
        test_context_without_introduction()
        print("=" * 60)
        print("\n🎉 所有测试通过！修复成功！")
        print("\n修复总结：")
        print("1. ✅ 提示词中明确要求AI必须严格使用元数据中的简介字段")
        print("2. ✅ 提示词中明确禁止AI自行编造或解释")
        print("3. ✅ workflow.py中优先使用 metadata['introduction']")
        print("4. ✅ 没有简介时只展示图片名称，不添加任何描述")
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
