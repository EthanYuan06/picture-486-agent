from logging import Logger
import logging

from langchain_chroma import Chroma
from pathlib import Path
from app.agent.model.model import multi_embedding_model

# 配置日志
logger = logging.getLogger(__name__)

# 使用绝对路径，避免工作目录变化导致指向错误位置
CHROMA_DIR = Path(__file__).resolve().parent.parent.parent / "chroma_data"

# 初始化 Chroma 向量库
chroma_vector_store = Chroma(
    collection_name="picture_vectors",
    embedding_function=multi_embedding_model,
    persist_directory=str(CHROMA_DIR)
)

