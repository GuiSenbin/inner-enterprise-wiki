"""
定位：测试层。
职责：验证 LLM Wiki 知识编译中间件的切片、意图识别和轻量重排规则。
依赖：src 知识编译模块、unittest 和本地纯内存测试数据。
"""

import unittest
import tempfile
from pathlib import Path

from src.chunker import MarkdownChunker
from src.bm25_store import BM25KeywordStore
from src.answer_service import AnswerService
from src.config import DEFAULT_LLM_MODEL
from src.knowledge_loader import KnowledgeLoader
from src.models import DocumentChunk, LinkGraph, QueryIntent, QueryPlan, RetrievalCandidate
from src.query_router import QueryRouter
from src.reranker import LightweightReranker
from src.retriever import HybridRetriever
import networkx as nx


class KnowledgeCompilationTest(unittest.TestCase):
    """验证 Raw/Wiki 文档先被编译成稳定知识单元，而不是问答时临时处理。"""

    def test_short_document_stays_as_single_chunk(self):
        chunker = MarkdownChunker(chunk_size=2000, overlap=300)

        chunks = chunker.split("短文档" * 100)

        self.assertEqual(1, len(chunks))
        self.assertEqual("短文档" * 100, chunks[0])

    def test_fallback_splitter_uses_2000_window_and_300_overlap(self):
        chunker = MarkdownChunker(chunk_size=2000, overlap=300, use_langchain=False)
        text = "".join(str(i % 10) for i in range(4100))

        chunks = chunker.split(text)

        self.assertEqual(3, len(chunks))
        self.assertEqual(2000, len(chunks[0]))
        self.assertEqual(text[1700:2000], chunks[1][:300])
        self.assertEqual(text[3400:3700], chunks[2][:300])

    def test_bm25_keyword_store_finds_exact_business_terms(self):
        chunks = [
            DocumentChunk(1, "项目A", "a.md", "raw", "普通验收内容", [], "内部验收报告"),
            DocumentChunk(2, "项目B", "b.md", "raw", "REQ-017 规定估值复核通过率不得低于 99.5%", [], "需求规格说明书"),
        ]
        store = BM25KeywordStore()
        store.build(chunks)

        results = store.search("REQ-017 是什么？", top_k=2)

        self.assertEqual(2, results[0][0].id)
        self.assertGreater(results[0][1], 0)

    def test_hybrid_retriever_merges_bm25_keyword_candidates(self):
        class FakeVectorStore:
            def __init__(self, chunks):
                self.chunks = chunks

            def search(self, query, top_k=15):
                return [(self.chunks[0], 0.40)]

        chunks = [
            DocumentChunk(1, "项目A", "a.md", "raw", "普通验收内容", [], "内部验收报告"),
            DocumentChunk(2, "项目B", "b.md", "raw", "RISK-WARN-003 触发组合风控预警", [], "技术方案"),
        ]
        bm25_store = BM25KeywordStore()
        bm25_store.build(chunks)
        graph = nx.Graph()
        query_plan = QueryPlan("RISK-WARN-003 是什么？", QueryIntent.GENERAL, "hybrid", [])

        candidates, _, _ = HybridRetriever(FakeVectorStore(chunks), LinkGraph(graph), bm25_store).retrieve(query_plan)

        bm25_candidate = next(candidate for candidate in candidates if candidate.chunk.id == 2)
        self.assertTrue(bm25_candidate.keyword_hit)
        self.assertGreater(bm25_candidate.keyword_score, 0)

    def test_answer_service_skips_llm_for_out_of_scope_query(self):
        class NoCallChatClient:
            chat = None

        query_plan = QueryPlan("今天北京天气怎么样？", QueryIntent.GENERAL, "vector_with_graph_supplement", [])

        answer, prompt, evidences, used_model, llm_failed, evidence_status, confidence = AnswerService(NoCallChatClient()).answer(query_plan, [])

        self.assertEqual("out_of_scope", evidence_status)
        self.assertEqual("", prompt)
        self.assertEqual([], evidences)
        self.assertIsNone(used_model)
        self.assertFalse(llm_failed)
        self.assertEqual("无证据", confidence["label"])
        self.assertIn("不在当前合晟资产内部 Wiki 的知识范围内", answer)

    def test_answer_service_skips_llm_for_low_confidence_evidence(self):
        class NoCallChatClient:
            chat = None

        query_plan = QueryPlan("项目A有什么风险？", QueryIntent.GENERAL, "vector_with_graph_supplement", ["项目A"])
        candidate = RetrievalCandidate(
            chunk=DocumentChunk(1, "项目A", "a.md", "raw", "无关内容", ["项目A"], "项目管理计划"),
            vector_score=0.01,
            keyword_score=0.0,
            score=0.03,
        )

        answer, prompt, evidences, used_model, llm_failed, evidence_status, confidence = AnswerService(NoCallChatClient()).answer(query_plan, [candidate])

        self.assertEqual("low_confidence", evidence_status)
        self.assertEqual("低", confidence["label"])
        self.assertEqual("", prompt)
        self.assertEqual([], evidences)
        self.assertIsNone(used_model)
        self.assertFalse(llm_failed)
        self.assertIn("没有找到足够可靠的证据", answer)

    def test_answer_service_returns_product_confidence_for_good_evidence(self):
        class FakeChatCompletions:
            def create(self, **kwargs):
                message = type("Message", (), {"content": "基于证据的回答"})()
                choice = type("Choice", (), {"message": message})()
                return type("Completion", (), {"choices": [choice]})()

        class FakeChat:
            completions = FakeChatCompletions()

        class FakeChatClient:
            chat = FakeChat()

        query_plan = QueryPlan("项目A验收指标有哪些？", QueryIntent.PROJECT_FACT, "hybrid", ["项目A"], "内部验收报告")
        candidate = RetrievalCandidate(
            chunk=DocumentChunk(1, "项目A", "a.md", "raw", "验收指标为通过率 99%", ["项目A"], "内部验收报告"),
            vector_score=0.52,
            keyword_score=0.8,
            keyword_hit=True,
            graph_hit=True,
            score=1.08,
        )

        answer, _, evidences, used_model, llm_failed, evidence_status, confidence = AnswerService(FakeChatClient()).answer(
            query_plan, [candidate]
        )

        self.assertEqual("基于证据的回答", answer)
        self.assertEqual("ok", evidence_status)
        self.assertEqual("高", confidence["label"])
        self.assertEqual(1, len(evidences))
        self.assertEqual(DEFAULT_LLM_MODEL, used_model)
        self.assertFalse(llm_failed)

    def test_answer_prompt_requires_conclusion_before_evidence(self):
        prompt = AnswerService.build_prompt("哪些系统要求操作留痕率达到 100%？", "证据内容")

        self.assertIn("## 结论", prompt)
        self.assertIn("## 证据依据", prompt)
        self.assertIn("结论必须放在回答第一部分", prompt)

    def test_exact_numeric_fact_evidence_gets_high_confidence(self):
        class FakeChatCompletions:
            def create(self, **kwargs):
                message = type("Message", (), {"content": "命中的系统要求操作留痕率达到 100%。"})()
                choice = type("Choice", (), {"message": message})()
                return type("Completion", (), {"choices": [choice]})()

        class FakeChat:
            completions = FakeChatCompletions()

        class FakeChatClient:
            chat = FakeChat()

        query = "哪些系统要求操作留痕率达到 100%"
        query_plan = QueryPlan(query, QueryIntent.PROJECT_FACT, "hybrid", [])
        candidate = RetrievalCandidate(
            chunk=DocumentChunk(
                1,
                "系统要求汇总",
                "requirements.md",
                "raw",
                "客户适当性管理系统要求操作留痕率达到 100%。",
                [],
                "需求规格说明书",
            ),
            vector_score=0.52,
            keyword_score=0.8,
            keyword_hit=True,
            score=0.98,
        )

        LightweightReranker().rank([candidate], query_plan, top_k=1)

        answer = AnswerService(FakeChatClient()).answer(query_plan, [candidate])

        self.assertEqual("高", answer[-1]["label"])
        self.assertGreaterEqual(answer[-1]["score"], 0.75)
        self.assertIn("直接事实命中", "；".join(candidate.rerank_reasons))

    def test_raw_wiki_links_are_compiled_into_chunk_mentions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_dir = root / "Raw"
            concept_dir = root / "Wiki" / "concept"
            entity_dir = root / "Wiki" / "entity"
            raw_dir.mkdir(parents=True)
            concept_dir.mkdir(parents=True)
            entity_dir.mkdir(parents=True)
            (raw_dir / "合晟资产_投研数据中台_需求规格说明书_20250106.md").write_text(
                "本项目由 [[李娜]] 负责，涉及 [[投研]] 和 [[指标口径]]。",
                encoding="utf-8",
            )
            (concept_dir / "投研.md").write_text("# 投研", encoding="utf-8")
            (entity_dir / "李娜.md").write_text("# 李娜", encoding="utf-8")

            chunks, _, raw_mentions_by_doc = KnowledgeLoader(raw_dir, concept_dir, entity_dir).compile_chunks()

            raw_chunk = next(chunk for chunk in chunks if chunk.category == "raw")
            self.assertEqual(["李娜", "投研", "指标口径"], raw_chunk.mentions)
            self.assertEqual(["李娜", "投研", "指标口径"], raw_mentions_by_doc["合晟资产_投研数据中台_需求规格说明书_20250106"])
            self.assertEqual("需求规格说明书", raw_chunk.doc_type)

    def test_query_router_detects_entity_profile_question(self):
        router = QueryRouter(all_nodes={"李娜", "投研数据中台"}, concept_names={"投研"}, entity_names={"李娜", "投研数据中台"})

        intent = router.classify("李娜参与过哪些项目？")

        self.assertEqual(QueryIntent.ENTITY_PROFILE, intent.intent_type)
        self.assertEqual("entity_graph_first", intent.retrieval_strategy)
        self.assertIn("李娜", intent.matched_nodes)

    def test_query_router_detects_project_acceptance_question(self):
        router = QueryRouter(all_nodes={"投研数据中台", "验收"}, concept_names={"验收"}, entity_names={"投研数据中台"})

        intent = router.classify("投研数据中台的验收指标有哪些？")

        self.assertEqual(QueryIntent.PROJECT_FACT, intent.intent_type)
        self.assertEqual("hybrid_with_doc_type_boost", intent.retrieval_strategy)
        self.assertEqual("内部验收报告", intent.preferred_doc_type)

    def test_query_router_detects_requirement_fact_question(self):
        router = QueryRouter(all_nodes=set(), concept_names=set(), entity_names=set())

        intent = router.classify("哪些系统要求操作留痕率达到 100%？")

        self.assertEqual(QueryIntent.PROJECT_FACT, intent.intent_type)
        self.assertEqual("需求规格说明书", intent.preferred_doc_type)

    def test_query_router_extracts_business_keywords_and_numeric_facts(self):
        router = QueryRouter(all_nodes=set(), concept_names=set(), entity_names=set())

        intent = router.classify("哪些系统要求操作留痕率达到 100%？")

        self.assertIn("操作留痕率", intent.keywords)
        self.assertIn("100%", intent.keywords)

    def test_query_router_detects_project_risk_question(self):
        router = QueryRouter(all_nodes=set(), concept_names=set(), entity_names=set())

        intent = router.classify("哪些项目提到了主要风险？")

        self.assertEqual(QueryIntent.PROJECT_FACT, intent.intent_type)
        self.assertEqual("项目管理计划", intent.preferred_doc_type)

    def test_query_router_detects_comparison_question(self):
        router = QueryRouter(
            all_nodes={"客户适当性管理系统", "合规审查工作台", "权限管理"},
            concept_names={"权限管理"},
            entity_names={"客户适当性管理系统", "合规审查工作台"},
        )

        intent = router.classify("对比客户适当性管理系统和合规审查工作台在权限上的设计差异。")

        self.assertEqual(QueryIntent.COMPARISON, intent.intent_type)
        self.assertEqual("multi_node_hybrid", intent.retrieval_strategy)
        self.assertIn("客户适当性管理系统", intent.matched_nodes)
        self.assertIn("合规审查工作台", intent.matched_nodes)

    def test_query_router_falls_back_to_vector_question(self):
        router = QueryRouter(all_nodes={"李娜"}, concept_names=set(), entity_names={"李娜"})

        intent = router.classify("公司知识库有什么价值？")

        self.assertEqual(QueryIntent.GENERAL, intent.intent_type)
        self.assertEqual("vector_with_graph_supplement", intent.retrieval_strategy)

    def test_reranker_boosts_preferred_document_type(self):
        intent = QueryRouter(all_nodes={"投研数据中台", "验收"}, concept_names={"验收"}, entity_names={"投研数据中台"}).classify(
            "投研数据中台的验收指标有哪些？"
        )
        candidates = [
            RetrievalCandidate(
                chunk=DocumentChunk(
                    id=1,
                    doc_name="合晟资产_投研数据中台_技术方案_20250127",
                    file_name="技术方案.md",
                    category="raw",
                    text="技术方案内容",
                    mentions=["投研数据中台"],
                    doc_type="技术方案",
                ),
                vector_score=0.80,
            ),
            RetrievalCandidate(
                chunk=DocumentChunk(
                    id=2,
                    doc_name="合晟资产_投研数据中台_内部验收报告_20250512",
                    file_name="验收报告.md",
                    category="raw",
                    text="验收指标内容",
                    mentions=["投研数据中台", "验收"],
                    doc_type="内部验收报告",
                ),
                vector_score=0.72,
                graph_hit=True,
            ),
        ]

        ranked = LightweightReranker().rank(candidates, intent, top_k=2)

        self.assertEqual("内部验收报告", ranked[0].chunk.doc_type)
        self.assertGreater(ranked[0].score, ranked[1].score)
        self.assertIn("文档类型匹配", "；".join(ranked[0].rerank_reasons))

    def test_reranker_boosts_person_mentions_for_entity_profile(self):
        router = QueryRouter(all_nodes={"李娜"}, concept_names=set(), entity_names={"李娜"})
        intent = router.classify("李娜参与过哪些项目？")
        candidates = [
            RetrievalCandidate(
                chunk=DocumentChunk(1, "项目A", "a.md", "raw", "未提到人员", [], "项目管理计划"),
                vector_score=0.77,
            ),
            RetrievalCandidate(
                chunk=DocumentChunk(2, "项目B", "b.md", "raw", "由李娜确认", ["李娜"], "项目管理计划"),
                vector_score=0.70,
                graph_hit=True,
            ),
        ]

        ranked = LightweightReranker().rank(candidates, intent, top_k=2)

        self.assertEqual("项目B", ranked[0].chunk.doc_name)
        self.assertIn("图谱命中", "；".join(ranked[0].rerank_reasons))
