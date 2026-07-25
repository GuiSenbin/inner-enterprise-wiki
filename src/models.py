"""
定位：知识编译模型层。
职责：定义 LLM Wiki 编译、检索、重排和回答阶段共享的数据结构。
依赖：Python dataclasses、枚举和标准类型。
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class QueryIntent(str, Enum):
    """描述用户问题的轻量意图类型，用于路由召回和重排策略。"""

    SOURCE_LOOKUP = "source_lookup"
    ENTITY_PROFILE = "entity_profile"
    CONCEPT_SUMMARY = "concept_summary"
    COMPARISON = "comparison"
    PROJECT_FACT = "project_fact"
    GENERAL = "general"


@dataclass
class DocumentChunk:
    """表示 Raw/Wiki 文档经过知识编译后可检索的稳定切片。"""

    id: int
    doc_name: str
    file_name: str
    category: str
    text: str
    mentions: list[str] = field(default_factory=list)
    doc_type: str = ""
    source_path: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DocumentChunk":
        """兼容旧版 chunks.json，把缺失字段按默认值补齐。"""
        return cls(
            id=int(payload.get("id", 0)),
            doc_name=str(payload.get("doc_name", "")),
            file_name=str(payload.get("file_name", "")),
            category=str(payload.get("category", "")),
            text=str(payload.get("text", "")),
            mentions=list(payload.get("mentions", [])),
            doc_type=str(payload.get("doc_type", "")),
            source_path=str(payload.get("source_path", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 和索引文件沿用的字典结构。"""
        return asdict(self)


@dataclass(frozen=True)
class WikiNode:
    """表示来自 Wiki/concept 或 Wiki/entity 的知识节点。"""

    name: str
    node_type: str
    file_name: str


@dataclass
class LinkGraph:
    """封装双链图谱对象及节点分类信息。"""

    graph: Any
    concept_names: set[str] = field(default_factory=set)
    entity_names: set[str] = field(default_factory=set)


@dataclass
class QueryPlan:
    """表示一次问题经过意图识别后的检索计划。"""

    query: str
    intent_type: QueryIntent
    retrieval_strategy: str
    matched_nodes: list[str] = field(default_factory=list)
    preferred_doc_type: str = ""


@dataclass
class RetrievalCandidate:
    """表示多路召回阶段的候选证据及可解释排序特征。"""

    chunk: DocumentChunk
    vector_score: float = 0.0
    keyword_score: float = 0.0
    graph_hit: bool = False
    keyword_hit: bool = False
    score: float = 0.0
    rerank_reasons: list[str] = field(default_factory=list)
    direct_match_score: float = 0.0


@dataclass
class AnswerEvidence:
    """表示最终进入 Prompt 和 API 返回的证据单元。"""

    chunk: DocumentChunk
    score: float
    vector_score: float
    graph_hit: bool
    keyword_score: float = 0.0
    keyword_hit: bool = False
    rerank_reasons: list[str] = field(default_factory=list)
    direct_match_score: float = 0.0

    def to_api_dict(self) -> dict[str, Any]:
        """转换为前端证据轨道可渲染的响应结构。"""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "vector_score": self.vector_score,
            "keyword_score": self.keyword_score,
            "graph_hit": self.graph_hit,
            "keyword_hit": self.keyword_hit,
            "direct_match_score": self.direct_match_score,
            "rerank_reasons": list(self.rerank_reasons),
        }
