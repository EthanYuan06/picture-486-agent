import redis

# 连接本地 Redis，默认地址 127.0.0.1:6379，无密码
r = redis.Redis(host='127.0.0.1', port=6379, decode_responses=True)

# 查看服务端版本
info = r.info('server')
print("Redis 服务端版本号：", info.get('redis_version'))