"""
图片上传 HITL 流程测试脚本
测试场景：用户提问"这个女孩叫安和昴，请帮我上传到公共图库"

流程说明：
1. 第一次请求：上传图片 + AI分析 → 触发HITL中断，返回upload_confirmation
2. 第二次请求：携带user_confirmed=true → 完成上传回调
"""
import requests
import time
import json

BASE_URL = "http://127.0.0.1:8024/api"

# 测试数据
TEST_IMAGE_URL = "https://yuluo-picture-1383397986.cos.ap-guangzhou.myqcloud.com/space/1994650152837120002/2025-12-04_13udd3iUt9BNJPf2.jpg"
TEST_QUERY = "这个女孩叫安和昴，请帮我上传到公共图库"
TEST_USER_ID = 1985558297927299073
TEST_SPACE_ID = None  # None表示公共图库
TEST_THREAD_ID = f"test-upload-{int(time.time())}"


def test_step1_upload_and_analyze():
    """
    步骤1：上传图片并触发AI分析
    预期：返回upload_confirmation，工作流中断等待用户确认
    """
    print("\n" + "="*60)
    print("📤 步骤1：上传图片并触发AI分析")
    print("="*60)
    
    payload = {
        "thread_id": TEST_THREAD_ID,
        "query": TEST_QUERY,
        "image_url": TEST_IMAGE_URL,
        "user_id": TEST_USER_ID,
        "space_id": TEST_SPACE_ID
    }
    
    print(f"🔗 请求URL: {BASE_URL}/chat")
    print(f"📝 用户提问: {TEST_QUERY}")
    print(f"🖼️  图片URL: {TEST_IMAGE_URL[:60]}...")
    print(f"👤 用户ID: {TEST_USER_ID}")
    print(f"📁 相册ID: {'公共图库' if TEST_SPACE_ID is None else TEST_SPACE_ID}")
    print()
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
        
        data = response.json()
        print(f"✅ HTTP状态码: {response.status_code}")
        print(f"📦 响应JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 验证响应格式
        if data.get("code") != 200:
            print(f"❌ 业务错误: code={data.get('code')}, message={data.get('message')}")
            return None
        
        response_data = data.get("data", {})
        
        # 检查是否有upload_confirmation（HITL中断标志）
        upload_confirmation = response_data.get("upload_confirmation")
        if not upload_confirmation:
            print("⚠️  未检测到upload_confirmation，可能HITL未启用或意图识别失败")
            print(f"AI回复: {response_data.get('reply', '无')}")
            return None
        
        print("\n✅ HITL中断成功！")
        print(f"📊 AI分析结果:")
        print(f"   - 名称: {upload_confirmation.get('name')}")
        print(f"   - 分类: {upload_confirmation.get('category')}")
        print(f"   - 标签: {upload_confirmation.get('tags')}")
        print(f"   - 简介: {upload_confirmation.get('introduction', '')[:50]}...")
        print(f"   - 提示: {upload_confirmation.get('message')}")
        
        return upload_confirmation
        
    except requests.exceptions.Timeout:
        print("❌ 请求超时（60秒）")
        return None
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return None


def test_step2_confirm_upload(upload_confirmation):
    """
    步骤2：确认上传（使用AI分析结果）
    预期：完成回调，返回上传成功消息
    """
    print("\n" + "="*60)
    print("✅ 步骤2：确认上传（使用AI分析结果）")
    print("="*60)
    
    payload = {
        "thread_id": TEST_THREAD_ID,
        "query": "",  # 第二次请求不需要query
        "user_confirmed": True,
        "modified_data": None  # 使用AI分析的原始结果
    }
    
    print(f"🔗 请求URL: {BASE_URL}/chat")
    print(f"📝 用户确认: True")
    print(f"📊 使用数据: AI分析结果（未修改）")
    print()
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
        
        data = response.json()
        print(f"✅ HTTP状态码: {response.status_code}")
        print(f"📦 响应JSON:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        # 验证响应格式
        if data.get("code") != 200:
            print(f"❌ 业务错误: code={data.get('code')}, message={data.get('message')}")
            return False
        
        response_data = data.get("data", {})
        reply = response_data.get("reply", "")
        
        print(f"\n💬 AI回复:")
        print(reply if reply else "(空)")
        
        # 检查是否有 upload_confirmation（说明工作流重新执行了）
        if response_data.get("upload_confirmation"):
            print("\n❌ 错误：检测到 upload_confirmation，说明工作流重新执行而非恢复")
            print("   可能原因：LangGraph checkpoint 恢复失败")
            return False
        
        # 验证是否上传成功
        if not reply:
            print("\n⚠️  回复为空，可能工作流未正确执行")
            return False
        elif "上传成功" in reply or "✅" in reply:
            print("\n✅ 上传成功！")
            return True
        elif "取消" in reply or "❌" in reply:
            print("\n⚠️  上传被取消或失败")
            return False
        else:
            print(f"\n⚠️  无法判断上传状态（回复内容：{reply[:50]}...）")
            return False
        
    except requests.exceptions.Timeout:
        print("❌ 请求超时（60秒）")
        return False
    except Exception as e:
        print(f"❌ 请求异常: {str(e)}")
        return False


def test_step3_confirm_with_modification():
    """
    步骤3（可选）：修改后确认上传
    演示如何修改AI分析结果后再上传
    """
    print("\n" + "="*60)
    print("📝 步骤3（可选）：修改后确认上传")
    print("="*60)
    
    modified_thread_id = f"test-upload-modify-{int(time.time())}"
    
    # 第一次请求
    print("\n📤 3.1 第一次请求（触发分析）...")
    payload1 = {
        "thread_id": modified_thread_id,
        "query": TEST_QUERY,
        "image_url": TEST_IMAGE_URL,
        "user_id": TEST_USER_ID,
        "space_id": TEST_SPACE_ID
    }
    
    response1 = requests.post(f"{BASE_URL}/chat", json=payload1, timeout=60)
    data1 = response1.json()
    upload_confirmation = data1.get("data", {}).get("upload_confirmation")
    
    if not upload_confirmation:
        print("❌ 未获取到upload_confirmation")
        return False
    
    print(f"✅ AI分析结果: name={upload_confirmation.get('name')}")
    
    # 第二次请求（修改数据）
    print("\n📤 3.2 第二次请求（修改后确认）...")
    modified_data = {
        "name": "安和昴-自定义名称",
        "introduction": "这是用户修改后的简介...",
        "category": "人物",
        "tags": ["安和昴", "角色", "自定义"],
        "space_id": None  # 保持公共图库
    }
    
    payload2 = {
        "thread_id": modified_thread_id,
        "query": "",
        "user_confirmed": True,
        "modified_data": modified_data
    }
    
    print(f"📝 修改后的数据:")
    print(json.dumps(modified_data, indent=2, ensure_ascii=False))
    
    response2 = requests.post(f"{BASE_URL}/chat", json=payload2, timeout=60)
    data2 = response2.json()
    reply = data2.get("data", {}).get("reply", "")
    
    print(f"\n💬 AI回复:")
    print(reply)
    
    if "上传成功" in reply:
        print("\n✅ 修改后上传成功！")
        return True
    else:
        print("\n⚠️  上传可能失败")
        return False


if __name__ == "__main__":
    print("\n" + "🚀"*30)
    print("图片上传 HITL 流程测试")
    print("🚀"*30)
    print(f"测试会话ID: {TEST_THREAD_ID}")
    print(f"后端地址: {BASE_URL}")
    print()
    
    try:
        # 步骤1：上传图片并触发AI分析
        upload_confirmation = test_step1_upload_and_analyze()
        
        if not upload_confirmation:
            print("\n❌ 步骤1失败，终止测试")
            exit(1)
        
        # 等待用户确认（模拟前端展示时间）
        print("\n⏳ 等待3秒（模拟用户查看确认界面）...")
        time.sleep(3)
        
        # 步骤2：确认上传
        success = test_step2_confirm_upload(upload_confirmation)
        
        if success:
            print("\n" + "✅"*30)
            print("主要测试流程通过！")
            print("✅"*30)
            
            # 询问是否执行步骤3
            choice = input("\n是否执行步骤3（修改后上传测试）？(y/n): ").strip().lower()
            if choice == 'y':
                test_step3_confirm_with_modification()
        else:
            print("\n❌ 步骤2失败")
            exit(1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
