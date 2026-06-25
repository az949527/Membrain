import os

from sentence_transformers import CrossEncoder
from app.core.logger import logger


class Reranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self.model_name = model_name
        self.model = None

        # 国内用户用 hf-mirror.com 加速下载
        if "HF_ENDPOINT" not in os.environ:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        try:
            self.model = CrossEncoder(model_name, local_files_only=True)
            logger.info("【Reranker】模型 %s 加载成功（本地缓存）", model_name)
        except Exception as e:
            logger.warning("【Reranker】模型 %s 加载失败: %s，回退到 FAISS 分数排序", model_name, e)

    def rerank(self, query: str, candidates: list[tuple[str, float]], top_n: int = 3):
        """候选格式：[(chunk_text, faiss_score),...]"""
        if self.model is None or not candidates:
            # 模型不可用 → 按 FAISS 分数降序取 top_n
            ranked = sorted(candidates, key=lambda x: x[1], reverse=True)
            return [(c, 0.0) for c in ranked[:top_n]]

        pairs = [(query, text) for text, _ in candidates]
        scores = self.model.predict(pairs)  # 算相关性分数
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]