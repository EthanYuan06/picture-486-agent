import chromadb
from app.agent.chroma import chroma_vector_store
from pathlib import Path

CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"
COLLECTION_NAME = "picture_vectors"

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_collection(name=COLLECTION_NAME)
print(f"向量库总条数: {collection.count()}")

# 测试2：直接用测试文件的 query 搜索
results = chroma_vector_store.similarity_search("找几张黑发女孩的图片", k=3)
print(f"Direct search results: {len(results)}")
for doc in results:
    print(f"  Content: {doc.page_content[:50]}...")

# 测试3：用重写后的 query 搜索
results2 = chroma_vector_store.similarity_search("黑发 女孩 图片", k=3)
print(f"Rewritten query results: {len(results2)}")
