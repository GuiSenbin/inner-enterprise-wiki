"""
定位：前端契约测试。
职责：验证原生前端符合宪法中的展示边界、文件说明和配置加载要求。
依赖：web/index.html、web/styles.css、web/app.js 三个静态文件。
"""

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "web"


def read_web_file(name):
    return (WEB_DIR / name).read_text(encoding="utf-8")


class FrontendContractTest(unittest.TestCase):
    def test_static_files_declare_responsibility(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")
        js_text = read_web_file("app.js")

        self.assertTrue(index_text.startswith("<!--"))
        self.assertIn("定位：前端页面结构。", index_text)
        self.assertTrue(css_text.startswith("/*"))
        self.assertIn("定位：前端视觉样式。", css_text)
        self.assertTrue(js_text.startswith("/*"))
        self.assertIn("定位：前端展示层。", js_text)

    def test_page_has_question_and_warning_output_regions(self):
        index_text = read_web_file("index.html")

        self.assertIn('id="activeQuestion"', index_text)
        self.assertIn('id="warningList"', index_text)
        self.assertIn('id="intentType"', index_text)
        self.assertIn('id="retrievalStrategy"', index_text)
        self.assertIn('id="rerankExplanation"', index_text)
        self.assertIn('id="confidenceLabel"', index_text)
        self.assertIn("当前问题", index_text)
        self.assertIn("运行提示", index_text)
        self.assertIn("证据置信度", index_text)
        self.assertIn("知识编译", index_text)

    def test_recommended_questions_use_business_questions_without_difficulty_labels(self):
        index_text = read_web_file("index.html")

        expected_queries = (
            "哪些系统要求操作留痕率达到 100%",
            "刘洋 都负责哪些项目？",
            "哪些项目提到了主要风险？",
        )
        for query in expected_queries:
            self.assertIn(f'data-query="{query}"', index_text)
            self.assertIn(f">{query}</button>", index_text)

        self.assertNotIn("简单验证：", index_text)
        self.assertNotIn("中等难度：", index_text)
        self.assertNotIn("高难度：", index_text)

    def test_frontend_loads_models_from_backend_config(self):
        index_text = read_web_file("index.html")
        js_text = read_web_file("app.js")

        self.assertNotIn('<option value="qwen-plus"', index_text)
        self.assertIn('requestJson("/api/config")', js_text)
        self.assertIn("renderConfig", js_text)

    def test_frontend_renders_query_route_and_rerank_fields(self):
        js_text = read_web_file("app.js")

        self.assertIn("payload.intent_type", js_text)
        self.assertIn("payload.retrieval_strategy", js_text)
        self.assertIn("payload.rerank_explanation", js_text)
        self.assertIn("payload.evidence_status", js_text)
        self.assertIn("payload.confidence_score", js_text)
        self.assertIn("payload.confidence_label", js_text)

    def test_frontend_keeps_retrieval_logic_out_of_page(self):
        js_text = read_web_file("app.js")

        forbidden_terms = [
            "faiss",
            "IndexFlatL2",
        ]
        lowered = js_text.lower()
        for term in forbidden_terms:
            self.assertNotIn(term.lower(), lowered)
        self.assertNotIn("function rerank", lowered)
        self.assertIsNone(re.search(r"\b(const|let|var)\s+prompt\s*=", js_text))
