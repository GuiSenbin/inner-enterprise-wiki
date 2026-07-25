"""
定位：知识编译加载层。
职责：扫描 Raw/Wiki 文档，解析双链、文档类型和 Wiki 节点元数据。
依赖：本地 Markdown 知识库、pathlib、正则和 chunker。
"""

import re
from pathlib import Path

from src.chunker import MarkdownChunker
from src.models import DocumentChunk, WikiNode


WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")
DOC_TYPES = ("需求规格说明书", "技术方案", "项目管理计划", "系统测试报告", "内部验收报告")


def parse_wiki_links(text):
    """提取 Markdown 双链目标，兼容 [[词条|别名]] 写法。"""
    links = []
    for raw in WIKI_LINK_PATTERN.findall(text):
        target = raw.split("|", 1)[0].strip()
        if target:
            links.append(target)
    return links


def infer_doc_type(file_name):
    """从合晟资产 Raw 文件名中识别文档类型，Wiki 词条返回空字符串。"""
    for doc_type in DOC_TYPES:
        if doc_type in file_name:
            return doc_type
    return ""


class KnowledgeLoader:
    """把 Raw/Wiki 文件编译为 DocumentChunk 和 WikiNode。"""

    def __init__(self, raw_dir, concept_dir, entity_dir, chunker=None):
        """设置知识库目录和可替换切片器。"""
        self.raw_dir = Path(raw_dir)
        self.concept_dir = Path(concept_dir)
        self.entity_dir = Path(entity_dir)
        self.chunker = chunker or MarkdownChunker()

    def load_wiki_nodes(self):
        """扫描 concept/entity 目录，返回 Wiki 节点列表和分类集合。"""
        concept_files = sorted(self.concept_dir.glob("*.md")) if self.concept_dir.exists() else []
        entity_files = sorted(self.entity_dir.glob("*.md")) if self.entity_dir.exists() else []
        nodes = [WikiNode(path.stem, "concept", path.name) for path in concept_files]
        nodes.extend(WikiNode(path.stem, "entity", path.name) for path in entity_files)
        return nodes, {path.stem for path in concept_files}, {path.stem for path in entity_files}

    def compile_chunks(self):
        """扫描 Raw、concept、entity 文档并产出统一切片。"""
        chunks = []
        texts_to_embed = []
        raw_mentions_by_doc = {}

        for path in sorted(self.raw_dir.glob("*.md")) if self.raw_dir.exists() else []:
            content = path.read_text(encoding="utf-8")
            mentions = parse_wiki_links(content)
            raw_mentions_by_doc[path.stem] = mentions
            for chunk_text in self.chunker.split(content):
                chunk = DocumentChunk(
                    id=len(chunks),
                    doc_name=path.stem,
                    file_name=path.name,
                    category="raw",
                    text=chunk_text,
                    mentions=mentions,
                    doc_type=infer_doc_type(path.name),
                    source_path=str(path),
                )
                chunks.append(chunk)
                texts_to_embed.append(chunk_text)

        for path in sorted(self.concept_dir.glob("*.md")) if self.concept_dir.exists() else []:
            content = path.read_text(encoding="utf-8")
            for chunk_text in self.chunker.split(content):
                chunk = DocumentChunk(len(chunks), path.stem, path.name, "concept", chunk_text, [], "", str(path))
                chunks.append(chunk)
                texts_to_embed.append(chunk_text)

        for path in sorted(self.entity_dir.glob("*.md")) if self.entity_dir.exists() else []:
            content = path.read_text(encoding="utf-8")
            for chunk_text in self.chunker.split(content):
                chunk = DocumentChunk(len(chunks), path.stem, path.name, "entity", chunk_text, [], "", str(path))
                chunks.append(chunk)
                texts_to_embed.append(chunk_text)

        return chunks, texts_to_embed, raw_mentions_by_doc
