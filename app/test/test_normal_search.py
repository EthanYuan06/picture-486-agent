from langchain_chroma import Chroma
from pathlib import Path
from dotenv import load_dotenv

from app.agent.model.model import multi_embedding_model

load_dotenv()

# 路径要和离线脚本完全一致
CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"
COLLECTION_NAME = "picture_vectors"

# 初始化向量库
vector_store = Chroma(
    collection_name=COLLECTION_NAME,
    embedding_function=multi_embedding_model,
    persist_directory=str(CHROMA_DIR)
)

# 用自然语言描述特征，搜索图片
def search_pictures(query: str, top_k: int = 3):
    results = vector_store.similarity_search_with_score(query, k=top_k)
    print(f"查询词：{query}")
    print("-" * 50)
    for i, (doc, score) in enumerate(results, 1):
        print(f"Top {i} 相似度：{score:.4f}")
        print(f"图片名称：{doc.metadata['name']}")
        print(f"分类：{doc.metadata['category']}")
        print(f"标签：{doc.metadata['tags']}")
        print(f"图片链接：{doc.metadata['image_url']}")
        print("-" * 50)

if __name__ == "__main__":
    # 替换成你想测试的图片特征描述
    test_query = "黑发 女孩 图片"
    search_pictures(test_query, top_k=3)