from langchain_chroma import Chroma
from pathlib import Path
from dotenv import load_dotenv
import chromadb

from app.agent.model.model import multi_embedding_model

load_dotenv()

# 路径必须和离线脚本一致
CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"
COLLECTION_NAME = "picture_vectors"

# 1. 检查离线写入的向量维度
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_collection(name=COLLECTION_NAME)

# 取一条离线向量看维度（必须显式指定 include=["embeddings"]）
sample = collection.get(
    limit=1,
    include=["embeddings"]  # 关键：必须显式指定要返回 embeddings
)

if len(sample["embeddings"]) == 0:
    print("❌ 未获取到离线向量数据，请检查数据是否已写入")
else:
    offline_embedding = sample["embeddings"][0]
    print(f"离线向量维度: {len(offline_embedding)}")

# 2. 检查在线查询生成的向量维度
embedding_fn = multi_embedding_model
query_embedding = embedding_fn.embed_query("安和昴")
print(f"查询向量维度: {len(query_embedding)}")

# 3. 初始化向量库，强制打印相似度分数
vector_store = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=embedding_fn,
    persist_directory=str(CHROMA_DIR)
)

def debug_search(query: str, top_k: int = 10):
    # 直接获取所有向量和相似度，看是不是分数都很高
    results = vector_store.similarity_search_with_score(query, k=top_k)
    print(f"\n查询词: {query}")
    print("="*50)
    if not results:
        print("❌ 没有任何结果")
        return
    for doc, score in results:
        print(f"相似度分数: {score:.4f} | 标签: {doc.metadata['tags']} | 名称: {doc.metadata['name']} | url: {doc.metadata['image_url']}")

debug_search("安和昴", top_k=10)