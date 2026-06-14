"""
FastAPI 接口调用测试脚本
使用前请确保服务已启动：uvicorn app.main:app --reload
"""
import requests

BASE_URL = "http://127.0.0.1:8024/api"

def test_create_thread():
    """测试接口1：新建会话"""
    print("\n=== 测试1：新建会话 ===")
    response = requests.get(f"{BASE_URL}/create-thread")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    if response.status_code == 200:
        data = response.json()
        return data["thread_id"]
    return None


def test_check_thread(thread_id):
    """测试接口2：校验会话（新会话应该不存在）"""
    print(f"\n=== 测试2：校验会话 {thread_id[:8]}... ===")
    response = requests.get(f"{BASE_URL}/check-thread/{thread_id}")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")


def test_chat(thread_id, query):
    """测试接口3：对话交互"""
    print(f"\n=== 测试3：对话交互 ===")
    print(f"用户: {query}")
    
    payload = {
        "thread_id": thread_id,
        "query": query
    }
    response = requests.post(f"{BASE_URL}/chat", json=payload)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"AI回复: {data['reply']}")
        return True
    else:
        print(f"错误: {response.text}")
        return False


def test_check_thread_after_chat(thread_id):
    """测试接口2：校验会话（对话后应该存在）"""
    print(f"\n=== 测试4：校验会话（对话后） ===")
    response = requests.get(f"{BASE_URL}/check-thread/{thread_id}")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")


def test_delete_thread(thread_id):
    """测试接口4：删除会话"""
    print(f"\n=== 测试5：删除会话 ===")
    response = requests.delete(f"{BASE_URL}/delete-thread/{thread_id}")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")


def test_check_thread_after_delete(thread_id):
    """测试接口2：校验会话（删除后应该不存在）"""
    print(f"\n=== 测试6：校验会话（删除后） ===")
    response = requests.get(f"{BASE_URL}/check-thread/{thread_id}")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")


if __name__ == "__main__":
    try:
        # 1. 创建新会话
        thread_id = test_create_thread()
        if not thread_id:
            print("❌ 创建会话失败，终止测试")
            exit(1)
        
        # 2. 校验新会话（应不存在）
        test_check_thread(thread_id)
        
        # 3. 进行对话
        success = test_chat(thread_id, "你好，介绍一下你自己")
        if not success:
            print("❌ 对话失败，终止测试")
            exit(1)
        
        # 4. 再次对话（测试多轮上下文）
        test_chat(thread_id, "你能帮我做什么？")
        
        # 5. 校验会话（对话后应存在）
        test_check_thread_after_chat(thread_id)
        
        # 6. 删除会话
        test_delete_thread(thread_id)
        
        # 7. 校验会话（删除后应不存在）
        test_check_thread_after_delete(thread_id)
        
        print("\n✅ 所有测试完成！")
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 连接失败，请确保服务已启动：uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")
