import chromadb
from pathlib import Path

# 和离线脚本一致的路径
CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"
COLLECTION_NAME = "picture_vectors"

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_collection(name=COLLECTION_NAME)

print(f"向量库总条数: {collection.count()}")
print("前3条数据预览:")
print(collection.peek(3))