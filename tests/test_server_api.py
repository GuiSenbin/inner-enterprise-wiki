"""
定位：测试层。
职责：验证本地 HTTP 服务接口、参数校验、索引重建保护和静态文件托管行为。
依赖：server.py 的 AppState/create_handler、FakeEngine 和 unittest。
"""

import json
import tempfile
import unittest
from pathlib import Path

from src.config import ALLOWED_LLM_MODELS, DEFAULT_LLM_MODEL


class FakeEngine:
    """替代真实 WikiEngine，保证 API 测试不依赖外部模型和索引文件。"""

    def __init__(self):
        self.index = object()
        self.chunks = [{"id": 1}, {"id": 2}]
        self.all_nodes = {"合晟资产", "RAG", "来源引用"}
        self.graph = type("FakeGraph", (), {"number_of_edges": lambda self: 4})()
        self.compiled_at = "2026-07-22T10:00:00"
        self.build_called = False
        self.last_question = None

    def load_index(self):
        """模拟本地索引加载成功。"""
        return True

    def build_index(self):
        """模拟索引重建，并更新切片数量用于状态断言。"""
        self.build_called = True
        self.chunks.append({"id": 3})
        return None

    def answer_question(self, query, top_k=5, model=DEFAULT_LLM_MODEL):
        """返回固定问答结果，验证服务层是否正确传参和透传响应。"""
        self.last_question = (query, top_k, model)
        return {
            "query": query,
            "answer": "答案来自知识库。",
            "prompt": "参考信息",
            "intent_type": "concept_summary",
            "retrieval_strategy": "concept_graph_first",
            "rerank_explanation": ["图谱命中：RAG", "文档类型匹配：技术方案"],
            "evidence_status": "ok",
            "confidence_score": 0.86,
            "confidence_label": "高",
            "matched_nodes": ["RAG"],
            "related_docs": ["合晟资产_知识库智能问答系统_技术方案_20260126"],
            "retrieved_results": [
                {
                    "chunk": {
                        "doc_name": "合晟资产_知识库智能问答系统_技术方案_20260126",
                        "category": "raw",
                        "text": "系统使用 [[RAG]] 和 [[来源引用]]。",
                        "mentions": ["RAG", "来源引用"],
                    },
                    "score": 0.88,
                    "vector_score": 0.53,
                    "graph_hit": True,
                }
            ],
            "used_model": model,
            "embedding_failed": False,
            "llm_failed": False,
        }


class ServerApiTest(unittest.TestCase):
    """验证 HTTP 服务层在不启动真实端口时的核心接口行为。"""

    def setUp(self):
        import server

        self.server = server
        self.temp_dir = tempfile.TemporaryDirectory()
        self.web_dir = Path(self.temp_dir.name)
        (self.web_dir / "index.html").write_text("<h1>合晟资产 Wiki</h1>", encoding="utf-8")
        self.state = server.AppState(web_dir=self.web_dir, engine_factory=FakeEngine)
        self.handler_cls = server.create_handler(self.state)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_handler(self):
        """构造最小化请求处理器，直接调用 handler 方法并收集响应。"""
        handler_cls = self.handler_cls

        class Harness(handler_cls):
            def __init__(self):
                self.status = None
                self.headers = {}
                self.body = b""
                self.request_headers = {}
                self.rfile = None

            @property
            def headers(self):
                return self.request_headers

            @headers.setter
            def headers(self, value):
                self.response_headers = value

            def send_header(self, keyword, value):
                self.response_headers[keyword] = value

            def send_response(self, code, message=None):
                self.status = code

            def end_headers(self):
                pass

            def wfile_write(self, data):
                self.body += data

        return Harness()

    def test_status_reports_loaded_index_metrics(self):
        handler = self.make_handler()

        handler.handle_status()

        payload = json.loads(handler.body.decode("utf-8"))
        self.assertEqual(200, handler.status)
        self.assertTrue(payload["index_loaded"])
        self.assertEqual(2, payload["chunk_count"])
        self.assertEqual(3, payload["node_count"])
        self.assertEqual(4, payload["graph_edge_count"])
        self.assertEqual("2026-07-22T10:00:00", payload["compiled_at"])

    def test_config_reports_model_choices_from_central_config(self):
        handler = self.make_handler()

        handler.handle_config()

        payload = json.loads(handler.body.decode("utf-8"))
        self.assertEqual(200, handler.status)
        self.assertEqual(DEFAULT_LLM_MODEL, payload["default_model"])
        self.assertEqual(list(ALLOWED_LLM_MODELS), payload["models"])
        self.assertNotIn("top_k", payload)
        self.assertNotIn("max_json_body_bytes", payload)

    def test_answer_requires_non_empty_query(self):
        handler = self.make_handler()
        handler.read_json = lambda: {"query": "   "}

        handler.handle_answer()

        payload = json.loads(handler.body.decode("utf-8"))
        self.assertEqual(400, handler.status)
        self.assertEqual("请输入问题后再检索。", payload["error"])

    def test_answer_delegates_to_engine(self):
        handler = self.make_handler()
        selected_model = ALLOWED_LLM_MODELS[2]
        handler.read_json = lambda: {"query": "知识库智能问答系统为什么适合用 RAG？", "model": selected_model}

        handler.handle_answer()

        payload = json.loads(handler.body.decode("utf-8"))
        engine = self.state.get_engine()
        self.assertEqual(200, handler.status)
        self.assertEqual("答案来自知识库。", payload["answer"])
        self.assertEqual("concept_summary", payload["intent_type"])
        self.assertEqual("concept_graph_first", payload["retrieval_strategy"])
        self.assertEqual("ok", payload["evidence_status"])
        self.assertEqual(0.86, payload["confidence_score"])
        self.assertEqual("高", payload["confidence_label"])
        self.assertEqual(["图谱命中：RAG", "文档类型匹配：技术方案"], payload["rerank_explanation"])
        self.assertEqual(("知识库智能问答系统为什么适合用 RAG？", 5, selected_model), engine.last_question)
        self.assertEqual("nosniff", handler.response_headers["X-Content-Type-Options"])

    def test_static_index_file_is_served(self):
        handler = self.make_handler()
        handler.path = "/"

        handler.serve_static()

        self.assertEqual(200, handler.status)
        self.assertIn("text/html", handler.response_headers["Content-Type"])
        self.assertIn("合晟资产 Wiki", handler.body.decode("utf-8"))

    def test_static_path_escape_falls_back_to_index(self):
        outside = self.web_dir.parent / f"{self.web_dir.name}_backup"
        outside.mkdir()
        (outside / "secret.txt").write_text("不应该被读取", encoding="utf-8")
        handler = self.make_handler()
        handler.path = f"/../{outside.name}/secret.txt"

        handler.serve_static()

        self.assertEqual(200, handler.status)
        self.assertIn("合晟资产 Wiki", handler.body.decode("utf-8"))
        self.assertNotIn("不应该被读取", handler.body.decode("utf-8"))

    def test_rebuild_rejects_cross_origin_requests(self):
        handler = self.make_handler()
        handler.request_headers = {"Origin": "https://example.com"}

        handler.handle_rebuild()

        payload = json.loads(handler.body.decode("utf-8"))
        self.assertEqual(403, handler.status)
        self.assertEqual("拒绝跨站触发重建索引。", payload["error"])
        self.assertFalse(self.state.get_engine().build_called)

    def test_read_json_rejects_large_body(self):
        from io import BytesIO

        handler = self.make_handler()
        handler.request_headers = {"Content-Length": str(self.server.MAX_JSON_BODY_BYTES + 1)}
        handler.rfile = BytesIO(b"{}")

        payload = handler.read_json()

        self.assertEqual({"_error": "请求体过大。", "_status": 413}, payload)

    def test_answer_rejects_unknown_model(self):
        handler = self.make_handler()
        handler.read_json = lambda: {"query": "测试", "model": "unknown-model"}

        handler.handle_answer()

        payload = json.loads(handler.body.decode("utf-8"))
        self.assertEqual(400, handler.status)
        self.assertEqual("不支持的模型：unknown-model", payload["error"])
