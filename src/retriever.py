"""
定位：混合检索层。
职责：执行向量召回、Wiki 双链图谱召回，并合并为统一候选证据。
依赖：vector_store、LinkGraph、QueryPlan 和 RetrievalCandidate。
"""

from src.models import RetrievalCandidate


class HybridRetriever:
    """根据查询计划执行向量优先、图谱优先或混合召回。"""

    def __init__(self, vector_store, link_graph, keyword_store=None):
        """设置向量索引、双链图谱和可选 BM25 关键词索引。"""
        self.vector_store = vector_store
        self.link_graph = link_graph
        self.keyword_store = keyword_store

    def retrieve(self, query_plan, vector_top_k=None):
        """返回候选证据、关联 Raw 文档和向量降级状态。"""
        vector_top_k = vector_top_k or query_plan.candidate_top_k
        graph_related_docs = self.related_docs(query_plan.matched_nodes)
        candidates_by_id = {}
        embedding_failed = False

        try:
            for chunk, vector_score in self.vector_store.search(query_plan.query, top_k=vector_top_k):
                candidates_by_id[chunk.id] = RetrievalCandidate(
                    chunk=chunk,
                    vector_score=vector_score,
                    graph_hit=chunk.doc_name in graph_related_docs,
                )
        except Exception as exc:
            print(f"Embedding 向量检索失败，将降级为纯本地图谱检索: {exc}")
            embedding_failed = True

        if self.keyword_store is not None:
            for chunk, keyword_score in self.keyword_store.search(query_plan.query, top_k=vector_top_k):
                candidate = candidates_by_id.get(chunk.id)
                if candidate is None:
                    candidates_by_id[chunk.id] = RetrievalCandidate(
                        chunk=chunk,
                        keyword_score=keyword_score,
                        keyword_hit=True,
                        graph_hit=chunk.doc_name in graph_related_docs,
                    )
                else:
                    candidate.keyword_score = max(candidate.keyword_score, keyword_score)
                    candidate.keyword_hit = True

        for chunk in self.vector_store.chunks:
            if chunk.doc_name in graph_related_docs and chunk.id not in candidates_by_id:
                candidates_by_id[chunk.id] = RetrievalCandidate(
                    chunk=chunk,
                    vector_score=0.30,
                    graph_hit=True,
                )

        return list(candidates_by_id.values()), list(graph_related_docs), embedding_failed

    def related_docs(self, matched_nodes):
        """沿命中的 Wiki 节点查找关联 Raw 文档。"""
        graph = self.link_graph.graph
        related = set()
        for node in matched_nodes:
            if node not in graph:
                continue
            for neighbor in graph.neighbors(node):
                node_attrs = graph.nodes[neighbor]
                if node_attrs.get("type") == "raw_doc":
                    related.add(neighbor)
        return related
