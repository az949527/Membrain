from __future__ import annotations

import os

from sentence_transformers import SentenceTransformer
import numpy as np


class Embedder:
    def __init__(self, model_name: str):
        # 设置 HuggingFace 镜像（国内用户用 hf-mirror.com 加速下载）
        # 如果已经设置了 HF_ENDPOINT 环境变量，优先使用
        if "HF_ENDPOINT" not in os.environ:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        self.model = SentenceTransformer(model_name, local_files_only=True)

    def embed(self, texts: list[str]) -> np.ndarray:
        # 把文本列表转成向量矩阵
        # normalize_embeddings = True 让向量长度为1
        # FAISS用内积（IP）计算余弦相似度
        return self.model.encode(texts, normalize_embeddings=True)

    def embed_query(self, text: str) -> np.ndarray:
        # 单条查询，返回一维向量
        return self.embed([text])[0]