"""
AnimeTrace API 测试脚本
用于查看API实际返回的JSON结构
"""
import requests
import json


def test_anime_api(image_url: str):
    """
    测试 AnimeTrace API 调用
    
    Args:
        image_url: 要测试的图片URL
    """
    url = "https://api.animetrace.com/v1/search"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "url": image_url,
        "is_multi": 0,
        "model": "pre_stable"
    }
    
    print("=" * 60)
    print("AnimeTrace API 测试")
    print("=" * 60)
    print(f"请求URL: {image_url}")
    print("-" * 60)
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=10
        )
        
        print(f"HTTP状态码: {response.status_code}")
        print("-" * 60)
        print("原始响应:")
        print(response.text)
        print("-" * 60)
        
        try:
            result = response.json()
            print("JSON格式化输出:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            code = result.get("code")
            data = result.get("data", {})
            
            print("-" * 60)
            print("关键字段:")
            print(f"  code: {code}")
            print(f"  data keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            if isinstance(data, dict):
                for key, value in data.items():
                    print(f"  {key}: {value}")
                    
        except Exception as e:
            print(f"JSON解析失败: {e}")
            
    except Exception as e:
        print(f"请求失败: {e}")
    
    print("=" * 60)


if __name__ == "__main__":
    test_url = input("请输入要测试的图片URL: ").strip()
    
    if test_url:
        test_anime_api(test_url)
    else:
        print("未输入URL，退出测试")
