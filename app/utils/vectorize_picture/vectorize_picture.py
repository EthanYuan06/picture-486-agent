import os

import chromadb
import pymysql
from dashscope import MultiModalEmbedding

# 配置
DB_CONFIG = {"host": "localhost",
             "port": 3306,
             "user": "root",
             "password": "1234",
             "database": "486_picture",
             "charset": "utf8mb4"}
chroma_client = chromadb.PersistentClient("../../../chroma_data")
coll = chroma_client.get_or_create_collection("picture_vectors")
API_KEY = os.getenv("DASHSCOPE_API_KEY")


# 取待向量化图片
def get_pics():
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT "
                "id,name,introduction,category,tags,url FROM picture "
                "WHERE isDelete=0 AND reviewStatus=1 AND is_vectorized=0")
            return cur.fetchall()


# 向量化
def get_emb(url, text):
    resp = MultiModalEmbedding.call(
        model="qwen3-vl-embedding",
        input=[{"image": url, "text": text}],
        api_key=API_KEY
    )
    return resp.output["embeddings"][0]["embedding"]


# 向MySQL的picture表标记已向量化的数据
def mark_done(pid):
    with pymysql.connect(**DB_CONFIG) as conn:
        conn.cursor().execute("UPDATE picture SET is_vectorized=1 WHERE id=%s", (pid,))
        conn.commit()


# 主逻辑
for pic in get_pics():
    try:
        text = f"{pic['name']} {pic['introduction']} {pic['category']} {pic['tags']}"
        emb = get_emb(pic["url"], text)

        coll.add(
            ids=[str(pic["id"])],
            embeddings=[emb],
            metadatas=[{"id": str(pic["id"]), "name": pic["name"], "url": pic["url"]}]
        )
        mark_done(pic["id"])
        print(f"✅ {pic['id']} 成功")
    except Exception as e:
        print(f"❌ {pic['id']} 失败：{e}")
