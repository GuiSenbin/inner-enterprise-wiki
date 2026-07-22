"""
定位：测试层。
职责：验证合晟资产 Raw/Wiki 知识库的一致性、范围边界、双链完整性和内容质量。
依赖：本地 Raw/Wiki/README/server 文件、正则解析和 unittest。
"""

import re
import unittest
from pathlib import Path
from datetime import date, datetime


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "Raw"
ENTITY_DIR = PROJECT_ROOT / "Wiki" / "entity"
CONCEPT_DIR = PROJECT_ROOT / "Wiki" / "concept"
MAX_DOC_DATE = date(2026, 7, 22)
DOC_TYPES = {"需求规格说明书", "技术方案", "项目管理计划", "系统测试报告", "内部验收报告"}


def read_text(path):
    """按 UTF-8 读取项目文本文件。"""
    return path.read_text(encoding="utf-8")


def wiki_links(text):
    """提取 Markdown 双链目标，兼容未来的 [[词条|别名]] 写法。"""
    links = set()
    for raw in re.findall(r"\[\[([^\]]+)\]\]", text):
        target = raw.split("|", 1)[0].strip()
        if target:
            links.add(target)
    return links


class HeshengKnowledgeBaseIntegrityTest(unittest.TestCase):
    """验证合晟资产知识库是否保持可追溯、可查询和范围一致。"""

    def test_raw_contains_exactly_60_hesheng_documents(self):
        raw_files = sorted(RAW_DIR.glob("*.md"))
        self.assertEqual(60, len(raw_files))
        project_doc_types = {}
        for path in raw_files:
            text = read_text(path)
            self.assertIn("[[合晟资产]]", text)
            self.assertNotIn("星辰数智", text)
            self.assertNotIn("用于用于", text)

            parts = path.stem.split("_")
            self.assertEqual(4, len(parts), path.name)
            company, project, doc_type, date_text = parts
            self.assertEqual("合晟资产", company)
            self.assertIn(doc_type, DOC_TYPES)
            doc_date = datetime.strptime(date_text, "%Y%m%d").date()
            self.assertLessEqual(doc_date, MAX_DOC_DATE, path.name)
            self.assertIn(doc_type.replace("内部验收报告", "验收"), text)
            project_doc_types.setdefault(project, set()).add(doc_type)

        self.assertEqual(12, len(project_doc_types))
        self.assertTrue(all(types == DOC_TYPES for types in project_doc_types.values()))

    def test_every_raw_link_has_entity_or_concept_page(self):
        entity_names = {path.stem for path in ENTITY_DIR.glob("*.md")}
        concept_names = {path.stem for path in CONCEPT_DIR.glob("*.md")}
        raw_doc_names = {path.stem for path in RAW_DIR.glob("*.md")}
        allowed = entity_names | concept_names | raw_doc_names

        missing = {}
        for path in sorted(RAW_DIR.glob("*.md")):
            unresolved = sorted(link for link in wiki_links(read_text(path)) if link not in allowed)
            if unresolved:
                missing[path.name] = unresolved

        self.assertEqual({}, missing)

    def test_knowledge_index_and_readme_match_hesheng_scope(self):
        index_text = read_text(PROJECT_ROOT / "Wiki" / "index.md")
        readme_text = read_text(PROJECT_ROOT / "README.md")
        server_text = read_text(PROJECT_ROOT / "server.py")
        page_text = read_text(PROJECT_ROOT / "web" / "index.html")

        for text in (index_text, readme_text, server_text, page_text):
            self.assertIn("合晟资产", text)
            self.assertNotIn("星辰数智", text)

        self.assertIn("原始文档 (Raw) | 60", index_text)
        self.assertIn("12 个内部数字化项目", readme_text)
        self.assertIn("当前版本 2.0", readme_text)
        self.assertNotIn("Streamlit", server_text)

    def test_core_entities_and_concepts_are_present(self):
        required_entities = {
            "合晟资产",
            "投研管理部",
            "风险管理部",
            "合规稽核部",
            "运营管理部",
            "信息技术部",
            "质量保障部",
            "投研数据中台",
            "组合风控预警平台",
            "资产估值管理系统",
            "知识库智能问答系统",
        }
        required_concepts = {
            "投研",
            "风控",
            "合规",
            "数据治理",
            "权限管理",
            "验收",
            "审计日志",
            "资产估值",
            "估值复核",
            "绩效归因",
            "客户适当性",
            "投资组合",
            "权限矩阵",
            "来源引用",
            "缺陷管理",
            "回归测试",
        }

        entity_names = {path.stem for path in ENTITY_DIR.glob("*.md")}
        concept_names = {path.stem for path in CONCEPT_DIR.glob("*.md")}

        self.assertTrue(required_entities <= entity_names)
        self.assertTrue(required_concepts <= concept_names)

    def test_every_concept_is_used_by_raw_documents(self):
        concept_names = {path.stem for path in CONCEPT_DIR.glob("*.md")}
        raw_links = set()
        for path in RAW_DIR.glob("*.md"):
            raw_links |= wiki_links(read_text(path))

        unused = sorted(concept_names - raw_links)
        self.assertEqual([], unused)

    def test_generated_content_has_expected_quality_markers(self):
        raw_texts = [read_text(path) for path in RAW_DIR.glob("*.md")]
        all_text = "\n".join(raw_texts)

        forbidden = [
            "中国移动",
            "国家电网",
            "浦发银行",
            "国泰君安",
            "物联网管理平台",
            "Kubernetes",
            "方便演示",
            "可验证",
            "后续问答",
            "若参考资料",
            "RAG]]问答",
            "录入、查询、导出和留痕",
            "信息技术部]]、[[信息技术部",
            "合规稽核部]]、[[合规稽核部",
            "TBD",
            "TODO",
        ]
        for word in forbidden:
            self.assertNotIn(word, all_text)

        for phrase in ["测试计划", "缺陷管理", "回归测试", "来源引用", "项目管理"]:
            self.assertIn(f"[[{phrase}]]", all_text)

    def test_requirement_metrics_are_not_reused_within_a_document(self):
        for path in RAW_DIR.glob("*_需求规格说明书_*.md"):
            text = read_text(path)
            metrics = re.findall(r"\| REQ-\d+ \| [^|]+ \| [^|]+ \| P0 \| ([^|]+) \|", text)
            self.assertEqual(len(metrics), len(set(metrics)), path.name)


if __name__ == "__main__":
    unittest.main()
