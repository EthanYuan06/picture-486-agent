import os
import chromadb
from dashscope import MultiModalEmbedding

CHROMA_PATH = "../../../chroma_data"
COLLECTION_NAME = "picture_vectors"
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


def search_pictures(query, top_k=5):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    text_resp = MultiModalEmbedding.call(
        model="qwen3-vl-embedding",
        input=[{"text": query}],
        api_key=DASHSCOPE_API_KEY
    )
    if text_resp.output is None:
        raise ValueError(f"Query embedding failed: {text_resp.code} - {text_resp.message}")

    output = text_resp.output
    if isinstance(output, dict):
        if "embeddings" in output:
            query_embedding = output["embeddings"][0]["embedding"]
        elif "embedding" in output:
            query_embedding = output["embedding"]
        else:
            query_embedding = output.get("text_embedding")
    else:
        query_embedding = output.embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    return results


def main():
    query = "有一个黑色长发白色发带的女孩，叫安和昴，请帮我找出她的图片"
    print(f"Query: {query}\n")

    results = search_pictures(query, top_k=3)

    for i, (doc, metadata, distance) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    )):
        print(f"Result {i + 1}:")
        print(f"  ID: {metadata.get('id', 'N/A')}")
        print(f"  Name: {metadata.get('name', 'N/A')}")
        print(f"  URL: {metadata.get('url', 'N/A')}")
        print(f"  Category: {metadata.get('category', 'N/A')}")
        print(f"  Tags: {metadata.get('tags', 'N/A')}")
        print(f"  Distance: {distance:.4f}")
        print()


if __name__ == "__main__":
    main()
