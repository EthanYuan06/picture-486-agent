import json
import sys
from pathlib import Path

import chromadb
import pymysql

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.models.embedding_llm import init_embedding_llm

# 配置
DB_CONFIG = {"host": "localhost",
             "port": 3306,
             "user": "root",
             "password": "1234",
             "database": "486_picture",
             "charset": "utf8mb4"}
chroma_client = chromadb.PersistentClient("../../../chroma_data")
coll = chroma_client.get_or_create_collection("picture_vectors")
embedding_model = init_embedding_llm()


# 取待向量化图片
def get_pics():
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT "
                "id,name,introduction,category,tags,thumbnailUrl,picWidth,picHeight FROM picture "
                "WHERE isDelete=0 AND reviewStatus=1 AND is_vectorized=0")
            return cur.fetchall()


# 向量化
def get_emb(url, text):
    return embedding_model.embed(url, text)


# 向MySQL的picture表标记已向量化的数据
def mark_done(pid):
    with pymysql.connect(**DB_CONFIG) as conn:
        conn.cursor().execute("UPDATE picture SET is_vectorized=1 WHERE id=%s", (pid,))
        conn.commit()


def normalize_metadata_value(value):
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def build_metadata(pic):
    return {
        "id": str(pic["id"]),
        "name": normalize_metadata_value(pic.get("name")),
        "introduction": normalize_metadata_value(pic.get("introduction")),
        "category": normalize_metadata_value(pic.get("category")),
        "tags": normalize_metadata_value(pic.get("tags")),
        "thumbnailUrl": normalize_metadata_value(pic.get("thumbnailUrl")),
        "picWidth": int(pic["picWidth"]) if pic.get("picWidth") is not None else 0,
        "picHeight": int(pic["picHeight"]) if pic.get("picHeight") is not None else 0
    }


# 主逻辑
for pic in get_pics():
    try:
        text = (
            f"name: {pic.get('name', '')}; "
            f"introduction: {pic.get('introduction', '')}; "
            f"category: {pic.get('category', '')}; "
            f"tags: {pic.get('tags', '')}; "
            f"thumbnailUrl: {pic.get('thumbnailUrl', '')}; "
            f"picWidth: {pic.get('picWidth', '')}; "
            f"picHeight: {pic.get('picHeight', '')}"
        )
        emb = get_emb(pic["thumbnailUrl"], text)

        coll.add(
            ids=[str(pic["id"])],
            embeddings=[emb],
            metadatas=[build_metadata(pic)]
        )
        mark_done(pic["id"])
        print(f"✅ {pic['id']} 成功")
    except Exception as e:
        print(f"❌ {pic['id']} 失败：{e}")
