from redis import Redis
from langgraph.checkpoint.redis import RedisSaver

client = Redis(
    host="localhost",
    port=6379,
    password="",
    decode_responses=False
)

# 配置 TTL：单位 分钟
ttl_config = {
    "default_ttl": 30,        # 会话30分钟无操作自动过期
    "refresh_on_read": True   # 读取会话时刷新过期时间
}

checkpointer = RedisSaver(redis_client=client, ttl=ttl_config)
checkpointer.setup()