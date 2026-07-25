"""
定位：关键词索引层。
职责：为已编译切片构建本地 BM25 索引，并返回关键词召回候选。
依赖：Python 标准库数学、正则和 DocumentChunk；不调用模型和外部服务。
"""

import math
import re
from collections import Counter


class BM25KeywordStore:
    """使用纯 Python BM25 补充编号、术语和短关键词召回。"""

    def __init__(self, k1=1.5, b=0.75):
        """设置 BM25 参数并初始化内存索引。"""
        self.k1 = k1
        self.b = b
        self.chunks = []
        self.doc_terms = []
        self.doc_freq = Counter()
        self.avg_doc_len = 0.0

    def build(self, chunks):
        """根据切片文本构建 BM25 统计信息，索引可由 chunks.json 快速重建。"""
        self.chunks = list(chunks)
        self.doc_terms = []
        self.doc_freq = Counter()

        total_terms = 0
        for chunk in self.chunks:
            terms = self.tokenize(f"{chunk.doc_name} {chunk.doc_type} {chunk.text}")
            term_counts = Counter(terms)
            self.doc_terms.append(term_counts)
            self.doc_freq.update(term_counts.keys())
            total_terms += sum(term_counts.values())

        self.avg_doc_len = total_terms / len(self.doc_terms) if self.doc_terms else 0.0

    def search(self, query, top_k=15):
        """按 BM25 分数返回关键词相关切片。"""
        if not self.chunks or not self.doc_terms:
            return []

        query_terms = self.tokenize(query)
        if not query_terms:
            return []

        scored = []
        for index, term_counts in enumerate(self.doc_terms):
            score = self.score(query_terms, term_counts)
            if score > 0:
                scored.append((self.chunks[index], score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def score(self, query_terms, term_counts):
        """计算一个切片对当前 query 的 BM25 分数。"""
        doc_len = sum(term_counts.values())
        if doc_len == 0 or self.avg_doc_len == 0:
            return 0.0

        total_docs = len(self.doc_terms)
        score = 0.0
        for term in query_terms:
            freq = term_counts.get(term, 0)
            if freq == 0:
                continue
            doc_freq = self.doc_freq.get(term, 0)
            idf = math.log(1 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
            denom = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
            score += idf * freq * (self.k1 + 1) / denom
        return score

    @classmethod
    def tokenize(cls, text):
        """切分中英文混合文本；英文编号保留整体，中文使用相邻二字词。"""
        text = text.lower()
        tokens = re.findall(r"[a-z0-9][a-z0-9_-]*|[\u4e00-\u9fff]+", text)
        normalized = []
        for token in tokens:
            if cls.is_cjk(token):
                normalized.extend(cls.cjk_bigrams(token))
            else:
                normalized.append(token)
        return normalized

    @staticmethod
    def is_cjk(token):
        """判断 token 是否为连续中文文本。"""
        return all("\u4e00" <= char <= "\u9fff" for char in token)

    @staticmethod
    def cjk_bigrams(token):
        """中文优先用二字词，单字词保留原样。"""
        if len(token) <= 1:
            return [token]
        return [token[index : index + 2] for index in range(len(token) - 1)]
