"""
定位：查询意图路由层。
职责：根据问题文本和 Wiki 节点命中选择检索策略与文档类型偏好。
依赖：models.QueryIntent 和本地图谱节点集合。
"""

import re

from src.models import QueryIntent, QueryPlan


class QueryRouter:
    """使用可测试规则识别问题意图，不额外调用大模型。"""

    SOURCE_KEYWORDS = ("怎么写", "原文", "条款", "规定", "第几条")
    ENTITY_PROFILE_KEYWORDS = ("参与", "负责", "哪些项目", "是谁", "画像")
    COMPARISON_KEYWORDS = ("对比", "比较", "差异", "不同")
    ACCEPTANCE_KEYWORDS = ("验收", "验收指标", "结论")
    REQUIREMENT_KEYWORDS = ("需求", "要求", "范围", "背景")
    RISK_KEYWORDS = ("风险", "主要风险")
    TECH_KEYWORDS = ("技术", "架构", "组件", "接口")
    PLAN_KEYWORDS = ("计划", "负责人", "周期", "预算", "里程碑")
    TEST_KEYWORDS = ("测试", "缺陷", "回归")
    QUERY_STOPWORDS = (
        "哪些系统",
        "哪些项目",
        "哪些",
        "哪个",
        "什么",
        "怎么",
        "如何",
        "是否",
        "有没有",
        "项目",
        "系统",
        "要求",
        "达到",
        "提到",
        "主要",
        "都",
        "负责",
    )

    def __init__(self, all_nodes, concept_names=None, entity_names=None):
        """设置可匹配的 Wiki 节点及节点类型集合。"""
        self.all_nodes = set(all_nodes or [])
        self.concept_names = set(concept_names or [])
        self.entity_names = set(entity_names or [])

    def classify(self, query):
        """返回问题意图、检索策略、命中节点和文档类型偏好。"""
        matched_nodes = self.match_nodes(query)
        preferred_doc_type = self.preferred_doc_type(query)
        keywords = self.extract_keywords(query, matched_nodes)

        if self.has_any(query, self.COMPARISON_KEYWORDS) and len(matched_nodes) >= 2:
            return QueryPlan(query, QueryIntent.COMPARISON, "multi_node_hybrid", matched_nodes, preferred_doc_type, keywords)

        if self.has_any(query, self.SOURCE_KEYWORDS):
            return QueryPlan(query, QueryIntent.SOURCE_LOOKUP, "vector_first_source_lookup", matched_nodes, preferred_doc_type, keywords)

        matched_entities = [node for node in matched_nodes if node in self.entity_names]
        matched_concepts = [node for node in matched_nodes if node in self.concept_names]

        if matched_entities and self.has_any(query, self.ENTITY_PROFILE_KEYWORDS):
            return QueryPlan(query, QueryIntent.ENTITY_PROFILE, "entity_graph_first", matched_nodes, preferred_doc_type, keywords)

        if preferred_doc_type:
            return QueryPlan(query, QueryIntent.PROJECT_FACT, "hybrid_with_doc_type_boost", matched_nodes, preferred_doc_type, keywords)

        if matched_concepts:
            return QueryPlan(query, QueryIntent.CONCEPT_SUMMARY, "concept_graph_first", matched_nodes, preferred_doc_type, keywords)

        return QueryPlan(query, QueryIntent.GENERAL, "vector_with_graph_supplement", matched_nodes, preferred_doc_type, keywords)

    def match_nodes(self, query):
        """从用户问题中匹配已存在的 Wiki 图谱节点。"""
        norm_query = query.lower()
        matched = []
        for node in sorted(self.all_nodes, key=len, reverse=True):
            norm_node = node.lower().replace("_", "/")
            if norm_node in norm_query or node.lower() in norm_query:
                matched.append(node)
        return matched

    def preferred_doc_type(self, query):
        """根据问题关键词推断优先证据文档类型。"""
        if self.has_any(query, self.ACCEPTANCE_KEYWORDS):
            return "内部验收报告"
        if self.has_any(query, self.REQUIREMENT_KEYWORDS):
            return "需求规格说明书"
        if self.has_any(query, self.RISK_KEYWORDS):
            return "项目管理计划"
        if self.has_any(query, self.TECH_KEYWORDS):
            return "技术方案"
        if self.has_any(query, self.PLAN_KEYWORDS):
            return "项目管理计划"
        if self.has_any(query, self.TEST_KEYWORDS):
            return "系统测试报告"
        return ""

    @classmethod
    def extract_keywords(cls, query, matched_nodes):
        """提取图谱节点之外的业务词和数字事实，供页面解释问题重点。"""
        keywords = list(matched_nodes)
        normalized = str(query).lower()
        numbers = re.findall(r"\d+(?:\.\d+)?%?", normalized)
        keywords.extend(numbers)

        business_text = re.sub(r"\d+(?:\.\d+)?%?", " ", normalized)
        for stopword in sorted(cls.QUERY_STOPWORDS, key=len, reverse=True):
            business_text = business_text.replace(stopword, " ")
        business_terms = re.findall(r"[\u4e00-\u9fff]{2,}", business_text)
        keywords.extend(business_terms)

        result = []
        for keyword in keywords:
            if keyword and keyword not in result:
                result.append(keyword)
        return result[:8]

    @staticmethod
    def has_any(text, keywords):
        """判断文本是否包含任一关键词。"""
        return any(keyword in text for keyword in keywords)
