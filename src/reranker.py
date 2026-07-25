"""
定位：轻量证据重排层。
职责：根据意图、图谱命中、文档类型和日期权重为候选证据排序。
依赖：models.QueryPlan、RetrievalCandidate 和正则日期解析。
"""

import re


class LightweightReranker:
    """用可解释规则替代模型 rerank，保证排序原因能展示给用户。"""

    def rank(self, candidates, query_plan, top_k=5):
        """为候选证据计算最终分并返回 Top K。"""
        ranked = []
        for candidate in candidates:
            score = max(float(candidate.vector_score), float(candidate.keyword_score) * 0.35)
            reasons = []

            direct_match_score, direct_match_reason = self.direct_fact_match(
                query_plan.query,
                candidate.chunk.text,
            )
            candidate.direct_match_score = direct_match_score
            if direct_match_reason:
                score += direct_match_score * 0.28
                reasons.append(direct_match_reason)

            if candidate.keyword_hit:
                score += 0.18
                reasons.append("BM25关键词召回")

            if candidate.graph_hit:
                score += 0.35
                reasons.append("图谱命中")

            matched_mentions = [node for node in query_plan.matched_nodes if node in candidate.chunk.mentions]
            if matched_mentions:
                score += 0.20
                reasons.append(f"命中双链：{'、'.join(matched_mentions[:3])}")

            if query_plan.preferred_doc_type and candidate.chunk.doc_type == query_plan.preferred_doc_type:
                score += 0.30
                reasons.append(f"文档类型匹配：{query_plan.preferred_doc_type}")

            if candidate.chunk.category in ("entity", "concept"):
                score += 0.08
                reasons.append("Wiki 词条")

            date_boost = self.date_boost(candidate.chunk.doc_name)
            if date_boost:
                score += date_boost
                reasons.append("日期较新")

            if not reasons:
                reasons.append("语义召回")

            candidate.score = score
            candidate.rerank_reasons = reasons
            ranked.append(candidate)

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    @classmethod
    def direct_fact_match(cls, query, text):
        """识别精确短语和数字事实，避免明确事实被普通语义分低估。"""
        normalized_query = cls.normalize_fact_text(query)
        normalized_text = cls.normalize_fact_text(text)
        if normalized_query and normalized_query in normalized_text:
            return 1.0, "直接事实命中：完整短语"

        numbers = cls.extract_numbers(query)
        if not numbers:
            return 0.0, ""

        matched_numbers = [number for number in numbers if number in normalized_text]
        if len(matched_numbers) != len(numbers):
            return 0.0, ""

        query_number = numbers[-1]
        number_position = normalized_query.rfind(query_number)
        prefix = normalized_query[:number_position]
        context_hit = any(
            len(prefix[-size:]) >= 4 and prefix[-size:] in normalized_text
            for size in range(min(12, len(prefix)), 3, -1)
        )
        if context_hit:
            return 1.0, "直接事实命中：短语与数字一致"
        return 0.45, "数字事实命中"

    @staticmethod
    def normalize_fact_text(text):
        """统一空白和标点，便于比较原文中的数字事实。"""
        return re.sub(r"[\s，。！？、：；（）()\[\]【】]", "", str(text).lower())

    @staticmethod
    def extract_numbers(text):
        """提取百分比、整数和小数，保留事实问题中的关键数值。"""
        normalized = re.sub(r"\s+", "", str(text).lower())
        return re.findall(r"\d+(?:\.\d+)?%?", normalized)

    @staticmethod
    def date_boost(doc_name):
        """从文档名抽取年份并给 2020 年后的资料轻微加权。"""
        match = re.search(r"(\d{8})", doc_name)
        if not match:
            return 0.0
        try:
            year = int(match.group(1)[:4])
        except ValueError:
            return 0.0
        if year <= 2020:
            return 0.0
        return (year - 2020) * 0.005
