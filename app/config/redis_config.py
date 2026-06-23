from redis.asyncio import Redis
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

# 创建异步 Redis 客户端
client = Redis(
    host="localhost",
    port=6379,
    password="",
    decode_responses=False
)

# 配置 TTL：单位 分钟
ttl_config = {
    "default_ttl": 10080,        # 会话7天无操作自动过期
    "refresh_on_read": False   # 不刷新过期时间
}

# 创建异步 checkpointer（支持 astream/ainvoke）
# 注意：需要在应用启动时调用 await checkpointer.asetup() 初始化索引
checkpointer = AsyncRedisSaver(redis_client=client, ttl=ttl_config)
