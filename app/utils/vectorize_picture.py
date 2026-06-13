import json
import os
from pathlib import Path
import chromadb
import dashscope
import pymysql
from dotenv import load_dotenv

load_dotenv()
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "1234",
    "database": "486_picture",
    "charset": "utf8mb4",
}
CHROMA_DIR = Path(__file__).resolve().parent.parent/ "chroma_data"
COLLECTION_NAME = "picture_vectors"

def get_pics():
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT id, name, introduction, category, tags, thumbnailUrl "
                "FROM picture WHERE isDelete=0 AND reviewStatus=1 AND is_vectorized=0"
            )
            return cur.fetchall()


def embed_picture(pic):
    # 向量入库文本：只用名称和简介，自然语言格式
    text = f"图片名称：{pic['name']}，描述：{pic['introduction']}"

    resp = dashscope.MultiModalEmbedding.call(
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        model="qwen3-vl-embedding",
        input=[{"text": text}, {"image": pic["thumbnailUrl"]}],
        enable_fusion=True,
    )
    if getattr(resp, "status_code", 200) != 200:
        raise RuntimeError(str(resp))
    embedding = resp.output["embeddings"][0]["embedding"]

    # 元数据：存入所有结构化信息，供后续过滤用
    metadata = {
        "id": pic["id"],
        "name": pic["name"] or "",
        "introduction": pic["introduction"] or "",
        "category": pic["category"] or "",
        "tags": pic["tags"] or "",
        "image_url": pic["thumbnailUrl"]
    }
    return embedding, text, metadata


def mark_vectorized(pic_id):
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE picture SET is_vectorized=1 WHERE id=%s", (pic_id,))
        conn.commit()


def main():
    if not os.getenv("DASHSCOPE_API_KEY"):
        raise RuntimeError("缺少环境变量 DASHSCOPE_API_KEY")
    collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_or_create_collection(
        name=COLLECTION_NAME
    )
    for pic in get_pics():
        if not pic["thumbnailUrl"]:
            continue
        embedding, text, metadata = embed_picture(pic)
        collection.upsert(
            ids=[str(pic["id"])],
            embeddings=[embedding],
            documents=[text],  # 只存自然语言文本，不存JSON
            metadatas=[metadata]  # 所有结构化信息在这里
        )
        mark_vectorized(pic["id"])
        print(f"✅vectorized {pic['name']}")


if __name__ == "__main__":
    main()
