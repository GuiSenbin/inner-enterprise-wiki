"""
定位：向量索引层。
职责：封装 Embedding 调用、FAISS 索引构建、保存、加载和语义搜索。
依赖：FAISS、NumPy、本地索引文件和 OpenAI 兼容 Embedding 客户端。
"""

import json
from pathlib import Path

import faiss
import numpy as np

from src.config import EMBEDDING_DIMENSION
from src.models import DocumentChunk


class FaissVectorStore:
    """管理 LLM Wiki 编译切片的本地向量索引。"""

    def __init__(self, index_dir, embedding_client, dimension=EMBEDDING_DIMENSION):
        """设置索引目录、Embedding 客户端和向量维度。"""
        self.index_dir = Path(index_dir)
        self.faiss_path = self.index_dir / "faiss.index"
        self.chunks_path = self.index_dir / "chunks.json"
        self.dimension = dimension
        self.embedding_client = embedding_client
        self.index = None
        self.chunks = []

    def build(self, chunks, texts_to_embed):
        """用给定切片和文本构建 FAISS 索引并持久化。"""
        self.index_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.faiss_path, self.chunks_path):
            if path.exists():
                path.unlink()

        embeddings = self.embedding_client.get_embeddings(texts_to_embed)
        faiss_index = faiss.IndexFlatL2(self.dimension)
        faiss_index.add(np.array(embeddings).astype("float32"))
        faiss.write_index(faiss_index, str(self.faiss_path))

        self.chunks_path.write_text(
            json.dumps([chunk.to_dict() for chunk in chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self.index = faiss_index
        self.chunks = list(chunks)

    def load(self):
        """载入本地 FAISS 索引和切片元数据，失败返回 False。"""
        if not self.faiss_path.exists() or not self.chunks_path.exists():
            return False
        try:
            self.index = faiss.read_index(str(self.faiss_path))
            payload = json.loads(self.chunks_path.read_text(encoding="utf-8"))
            self.chunks = [DocumentChunk.from_dict(item) for item in payload]
            return True
        except Exception as exc:
            print(f"载入向量索引失败: {exc}")
            return False

    def search(self, query, top_k=15):
        """向量召回候选切片，Embedding 失败时由调用方降级处理。"""
        if self.index is None or not self.chunks:
            raise Exception("尚未载入或构建索引！")

        query_emb = self.embedding_client.get_embeddings([query])[0]
        query_emb_np = np.array([query_emb]).astype("float32")
        distances, indices = self.index.search(query_emb_np, top_k)

        results = []
        for rank, idx in enumerate(indices[0]):
            if idx == -1:
                continue
            dist = float(distances[0][rank])
            sim_score = 1.0 / (1.0 + dist)
            results.append((self.chunks[idx], sim_score))
        return results
