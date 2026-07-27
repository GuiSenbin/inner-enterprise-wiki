"""
定位：后端查询门面层。
职责：协调知识编译、向量索引、双链检索、意图路由、轻量重排和有证据回答。
依赖：本地 Raw/Wiki 知识库、FAISS、NetworkX、DashScope OpenAI 兼容接口和 src 分层模块。
"""

import os
import pickle
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.answer_service import AnswerService
from src.bm25_store import BM25KeywordStore
from src.chunker import MarkdownChunker
from src.config import DEFAULT_EMBEDDING_MODEL, DEFAULT_LLM_MODEL, EMBEDDING_BATCH_SIZE, EMBEDDING_DIMENSION
from src.graph_builder import GraphBuilder
from src.knowledge_loader import KnowledgeLoader
from src.models import DocumentChunk
from src.query_router import QueryRouter
from src.reranker import LightweightReranker
from src.retriever import HybridRetriever
from src.vector_store import FaissVectorStore


load_dotenv()


class DashScopeEmbeddingClient:
    """隔离通义千问 Embedding 调用，供向量索引层复用。"""

    def __init__(self, client, embedding_model=DEFAULT_EMBEDDING_MODEL, batch_size=EMBEDDING_BATCH_SIZE):
        """设置 OpenAI 兼容客户端、Embedding 模型和批量大小。"""
        self.client = client
        self.embedding_model = embedding_model
        self.batch_size = batch_size

    def get_embeddings(self, texts):
        """调用配置的 Embedding 模型获取文本向量，失败时重试后抛出异常。"""
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]
            retries = 3
            while retries > 0:
                try:
                    response = self.client.embeddings.create(
                        model=self.embedding_model,
                        input=batch_texts,
                    )
                    embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(embeddings)
                    break
                except Exception as exc:
                    print(f"获取 Embedding 出错，重试中: {exc}")
                    retries -= 1
                    time.sleep(2)
            if retries == 0:
                raise Exception("无法调用通义千问 Embedding API，重试失败。")
            time.sleep(0.2)

        return all_embeddings


class WikiEngine:
    """企业 LLM Wiki 门面，封装知识编译、混合检索和基于证据的回答生成。"""

    def __init__(self):
        """初始化项目路径、模型客户端、索引组件和运行时知识状态。"""
        self.project_dir = Path(__file__).resolve().parents[1]
        self.raw_dir = self.project_dir / "Raw"
        self.concept_dir = self.project_dir / "Wiki" / "concept"
        self.entity_dir = self.project_dir / "Wiki" / "entity"

        self.index_save_dir = self.project_dir / "data" / "wiki_index"
        self.graph_path = self.index_save_dir / "graph.pkl"
        self.meta_path = self.index_save_dir / "metadata.json"

        api_key = os.getenv("DASHSCOPE_API_KEY")
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        self.chunker = MarkdownChunker(chunk_size=2000, overlap=300)
        self.loader = KnowledgeLoader(self.raw_dir, self.concept_dir, self.entity_dir, self.chunker)
        self.embedding_client = DashScopeEmbeddingClient(self.client)
        self.vector_store = FaissVectorStore(self.index_save_dir, self.embedding_client, dimension=EMBEDDING_DIMENSION)
        self.keyword_store = BM25KeywordStore()
        self.reranker = LightweightReranker()
        self.answer_service = AnswerService(self.client)

        self.index = None
        self.chunks = []
        self.graph = None
        self.all_nodes = set()
        self.concept_names = set()
        self.entity_names = set()
        self.compiled_at = None

    def build_index(self):
        """扫描 Raw/Wiki 文档，编译切片、双链图谱和 FAISS 向量索引并持久化。"""
        self.index_save_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.graph_path, self.meta_path):
            if path.exists():
                path.unlink()

        print("开始编译 Raw/Wiki 文档为 LLM Wiki 知识中间件...")
        wiki_nodes, concept_names, entity_names = self.loader.load_wiki_nodes()
        chunks, texts_to_embed, raw_mentions_by_doc = self.loader.compile_chunks()
        link_graph = GraphBuilder().build(wiki_nodes, raw_mentions_by_doc)

        print(f"编译出 {len(chunks)} 个知识切片，开始构建向量索引...")
        self.vector_store.build(chunks, texts_to_embed)
        self.keyword_store.build(chunks)

        with self.graph_path.open("wb") as out_g:
            pickle.dump(link_graph.graph, out_g)

        self.compiled_at = datetime.now().isoformat(timespec="seconds")
        self.meta_path.write_text(
            (
                "{\n"
                f'  "compiled_at": "{self.compiled_at}",\n'
                f'  "concept_count": {len(concept_names)},\n'
                f'  "entity_count": {len(entity_names)}\n'
                "}\n"
            ),
            encoding="utf-8",
        )

        print("所有本地知识中间件和索引保存完成！")
        self._set_runtime_state(link_graph, self.vector_store.chunks, self.compiled_at)

    def load_index(self):
        """载入本地持久化索引、切片和双链图谱，缺失或损坏时返回 False。"""
        if not self.graph_path.exists():
            return False
        if not self.vector_store.load():
            return False

        try:
            with self.graph_path.open("rb") as graph_file:
                graph = pickle.load(graph_file)
            wiki_nodes, concept_names, entity_names = self.loader.load_wiki_nodes()
            compiled_at = self._load_compiled_at()
            link_graph = GraphBuilder().build(wiki_nodes, {})
            link_graph.graph = graph
            link_graph.concept_names = concept_names
            link_graph.entity_names = entity_names
            self._set_runtime_state(link_graph, self.vector_store.chunks, compiled_at)
            return True
        except Exception as exc:
            print(f"载入索引失败: {exc}")
            return False

    def retrieve(self, query, top_k=5):
        """执行意图路由、混合召回和轻量重排，返回可解释证据切片。"""
        if self.index is None or not self.chunks or self.graph is None:
            raise Exception("尚未载入或构建索引！")

        query_plan = self._query_plan(query)
        retriever = HybridRetriever(self.vector_store, self._link_graph(), self.keyword_store)
        candidates, related_docs, embedding_failed = retriever.retrieve(query_plan)
        ranked = self.reranker.rank(candidates, query_plan, top_k=top_k)

        return ranked, query_plan, related_docs, embedding_failed

    def answer_question(self, query, top_k=5, model=DEFAULT_LLM_MODEL):
        """基于已编译 Wiki 证据回答问题，并返回意图、策略、来源和降级状态。"""
        ranked, query_plan, related_docs, embedding_failed = self.retrieve(query, top_k=top_k)
        answer, prompt, evidences, used_model, llm_failed, evidence_status, confidence = self.answer_service.answer(
            query_plan,
            ranked,
            top_k=top_k,
            model=model,
        )

        rerank_explanation = self._rerank_explanation(evidences)

        return {
            "query": query,
            "answer": answer,
            "prompt": prompt,
            "intent_type": query_plan.intent_type.value,
            "retrieval_strategy": query_plan.retrieval_strategy,
            "rerank_explanation": rerank_explanation,
            "evidence_status": evidence_status,
            "confidence_score": confidence["score"],
            "confidence_label": confidence["label"],
            "matched_nodes": query_plan.matched_nodes,
            "keywords": query_plan.keywords,
            "related_docs": related_docs,
            "retrieved_results": [evidence.to_api_dict() for evidence in evidences],
            "used_model": used_model,
            "embedding_failed": embedding_failed,
            "llm_failed": llm_failed,
        }

    def _query_plan(self, query):
        """创建当前问题的轻量意图检索计划。"""
        return QueryRouter(self.all_nodes, self.concept_names, self.entity_names).classify(query)

    def _link_graph(self):
        """把运行时图谱状态包装为检索层需要的 LinkGraph。"""
        from src.models import LinkGraph

        return LinkGraph(self.graph, self.concept_names, self.entity_names)

    def _set_runtime_state(self, link_graph, chunks, compiled_at):
        """同步门面暴露的旧字段和新分层组件状态。"""
        self.graph = link_graph.graph
        self.all_nodes = set(self.graph.nodes)
        self.concept_names = set(link_graph.concept_names)
        self.entity_names = set(link_graph.entity_names)
        self.chunks = [chunk.to_dict() if isinstance(chunk, DocumentChunk) else chunk for chunk in chunks]
        self.vector_store.chunks = [chunk if isinstance(chunk, DocumentChunk) else DocumentChunk.from_dict(chunk) for chunk in chunks]
        self.keyword_store.build(self.vector_store.chunks)
        self.index = self.vector_store.index
        self.compiled_at = compiled_at

    def _load_compiled_at(self):
        """读取索引编译时间，兼容没有 metadata.json 的旧索引。"""
        if not self.meta_path.exists():
            return None
        try:
            import json

            return json.loads(self.meta_path.read_text(encoding="utf-8")).get("compiled_at")
        except Exception:
            return None

    @staticmethod
    def _rerank_explanation(evidences):
        """汇总 Top 证据的排序说明，供 API 和前端展示。"""
        explanations = []
        for evidence in evidences:
            reasons = "；".join(evidence.rerank_reasons)
            if reasons:
                explanations.append(f"{evidence.chunk.doc_name}：{reasons}")
        return explanations
