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

        self.assertIn('id="intentType"', index_text)
        self.assertIn('id="retrievalStrategy"', index_text)
        self.assertIn('id="confidenceLabel"', index_text)
        self.assertIn("证据置信度", index_text)
        self.assertIn("知识编译", index_text)
        self.assertNotIn('id="activeQuestion"', index_text)
        self.assertNotIn('id="warningList"', index_text)
        self.assertNotIn("当前问题", index_text)
        self.assertNotIn("运行提示", index_text)

    def test_recommended_questions_use_business_questions_without_difficulty_labels(self):
        index_text = read_web_file("index.html")

        expected_queries = (
            "哪些系统要求操作留痕率达到 100%",
            "组合风控预警平台的主要风险是什么？",
            "刘洋 都负责哪些项目？",
            "哪些项目提到了主要风险？",
            "财务预算管理系统内部验收报告，验收范围是什么？",
        )
        for query in expected_queries:
            self.assertIn(f'data-query="{query}"', index_text)
            self.assertIn(f">{query}</button>", index_text)

        self.assertNotIn("简单验证：", index_text)
        self.assertNotIn("中等难度：", index_text)
        self.assertNotIn("高难度：", index_text)

    def test_frontend_renders_query_keywords_without_persistent_status_panels(self):
        index_text = read_web_file("index.html")
        js_text = read_web_file("app.js")

        self.assertIn('id="matchedNodes"', index_text)
        self.assertIn("payload.keywords", js_text)
        self.assertNotIn("activeQuestion", js_text)
        self.assertNotIn("warningList", js_text)

    def test_question_form_uses_compact_controls(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")

        self.assertIn('id="query" rows="1"', index_text)
        self.assertIn("min-height: 56px", css_text)
        self.assertIn("max-height: 120px", css_text)
        self.assertIn("justify-self: end", css_text)
        self.assertIn("min-width: 180px", css_text)

    def test_question_form_is_a_compact_command_bar_and_clears_on_page_show(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")
        js_text = read_web_file("app.js")

        self.assertIn('class="ask-title"', index_text)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", css_text)
        self.assertIn("align-items: end", css_text)
        self.assertIn("pageshow", js_text)
        self.assertIn('els.query.value = ""', js_text)

    def test_answer_and_question_bar_use_clear_priority_layout(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")
        js_text = read_web_file("app.js")

        self.assertIn('class="ask-title"', index_text)
        self.assertIn('class="question-label"', index_text)
        self.assertIn(".ask-panel {\n  display: grid;\n  grid-template-columns: 1fr;", css_text)
        self.assertIn("grid-template-columns: minmax(0, 1fr) auto", css_text)
        self.assertIn("question-label", css_text)
        self.assertIn("renderAnswerMarkdown", js_text)

    def test_wiki_answer_label_stays_with_title_above_input(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")

        self.assertIn('<div class="ask-title">', index_text)
        self.assertIn('<span class="question-label">Wiki answer</span>', index_text)
        self.assertNotIn('<label class="question-label" for="query">Wiki answer</label>', index_text)
        self.assertIn(".question-form {\n  display: grid;\n  grid-template-columns: minmax(0, 1fr) auto;", css_text)

    def test_question_placeholder_and_title_label_match_requested_copy(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")

        self.assertIn(">基于已编译 Wiki 证据回答</h2>\n              <span class=\"question-label\">Wiki answer</span>", index_text)
        self.assertIn('placeholder="请输入问题"', index_text)
        self.assertIn("justify-content: flex-start", css_text)

    def test_query_metadata_and_retrieval_methods_have_scan_friendly_labels(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")
        js_text = read_web_file("app.js")

        self.assertIn("关键词", index_text)
        self.assertIn("retrieval-methods", js_text)
        self.assertIn("intentLabels", js_text)
        self.assertIn("strategyLabels", js_text)
        self.assertIn("metadata-tags", css_text)
        self.assertIn("retrieval-badge", css_text)

    def test_long_metadata_and_evidence_use_summary_details_pattern(self):
        index_text = read_web_file("index.html")
        css_text = read_web_file("styles.css")
        js_text = read_web_file("app.js")

        self.assertIn('id="relatedDocs"', index_text)
        self.assertIn('id="resultSummary"', index_text)
        self.assertNotIn('id="rerankExplanation"', index_text)
        self.assertIn("renderCollapsibleList", js_text)
        self.assertIn("查看证据详情", js_text)
        self.assertIn("查看其余", js_text)
        self.assertIn('<details class="evidence-details" open>', js_text)
        self.assertIn("evidence-details", js_text)
        self.assertIn("metadata-detail", css_text)

    def test_evidence_rail_centers_rank_and_category(self):
        css_text = read_web_file("styles.css")

        self.assertIn(".rail-mark {", css_text)
        self.assertIn("justify-items: center", css_text)
        self.assertIn("transform: translateX(-15px)", css_text)

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
