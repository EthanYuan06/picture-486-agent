import os

from dashscope import MultiModalEmbedding
from dotenv import load_dotenv

load_dotenv()


class DashScopeEmbeddingClient:
    def __init__(self):
        self.api_key = os.environ.get("DASHSCOPE_API_KEY")

    def embed(self, image_url, text):
        # 默认只使用文本进行嵌入，如果提供了图片 URL 则也包含在 payload 中
        payload = {"text": text}
        if image_url:
            payload["image"] = image_url

        response = MultiModalEmbedding.call(
            model="qwen3-vl-embedding",
            input=[payload],
            api_key=self.api_key,
        )
        return response.output["embeddings"][0]["embedding"]


def init_embedding_llm():
    return DashScopeEmbeddingClient()


def init_embedding_model():
    return init_embedding_llm()


embedding_llm = init_embedding_llm()

