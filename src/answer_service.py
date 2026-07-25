"""
定位：问答编排层。
职责：把重排证据组装为 Prompt，调用大模型并返回兼容前端的答案结构。
依赖：OpenAI 兼容聊天客户端、QueryPlan 和 AnswerEvidence。
"""

from src.config import DEFAULT_LLM_MODEL, LLM_FALLBACK_MODELS
from src.models import AnswerEvidence


class AnswerService:
    """负责有证据回答，不承担检索和排序职责。"""

    MIN_CONFIDENCE_SCORE = 0.12
    OOS_MESSAGE = "这个问题不在当前合晟资产内部 Wiki 的知识范围内。请改问合晟资产内部项目、部门、人员、系统、需求、验收、测试或技术方案相关问题。"
    NO_EVIDENCE_MESSAGE = "知识库中没有找到足够证据回答这个问题。请换一个更具体的项目、文档类型、人员、部门或业务概念。"
    LOW_CONFIDENCE_MESSAGE = "知识库中没有找到足够可靠的证据回答这个问题。为避免编造，系统没有调用大模型生成答案。"
    FALLBACK_CONFIDENCE = {
        "out_of_scope": {"score": 0.0, "label": "无证据"},
        "no_evidence": {"score": 0.0, "label": "无证据"},
        "low_confidence": {"score": 0.05, "label": "低"},
    }

    def __init__(self, chat_client):
        """设置 OpenAI 兼容聊天客户端。"""
        self.chat_client = chat_client

    def answer(self, query_plan, ranked_candidates, top_k=5, model=DEFAULT_LLM_MODEL):
        """组装参考信息、调用模型，并返回答案、Prompt 和证据。"""
        evidence_status = self.evidence_status(query_plan, ranked_candidates)
        confidence = self.estimate_confidence(evidence_status, ranked_candidates)
        if evidence_status != "ok":
            return self.fallback_answer(evidence_status, confidence)

        evidences = [
            AnswerEvidence(
                chunk=candidate.chunk,
                score=candidate.score,
                vector_score=candidate.vector_score,
                keyword_score=candidate.keyword_score,
                graph_hit=candidate.graph_hit,
                keyword_hit=candidate.keyword_hit,
                rerank_reasons=candidate.rerank_reasons,
                direct_match_score=candidate.direct_match_score,
            )
            for candidate in ranked_candidates[:top_k]
        ]
        context_str = self.build_context(evidences)
        prompt = self.build_prompt(query_plan.query, context_str)
        answer, used_model, llm_failed = self.generate(prompt, model)
        return answer, prompt, evidences, used_model, llm_failed, evidence_status, confidence

    def evidence_status(self, query_plan, ranked_candidates):
        """判断是否有足够证据进入 LLM，避免领域外或低置信问题浪费调用。"""
        if not ranked_candidates:
            if not query_plan.matched_nodes and not self.has_project_scope_keyword(query_plan.query):
                return "out_of_scope"
            return "no_evidence"

        best = ranked_candidates[0]
        has_reliable_signal = (
            best.score >= self.MIN_CONFIDENCE_SCORE
            or best.vector_score >= 0.08
            or best.keyword_hit
            or best.graph_hit
        )
        if not has_reliable_signal:
            return "low_confidence"
        return "ok"

    def estimate_confidence(self, evidence_status, ranked_candidates):
        """把检索证据强度转换成可展示的产品置信度。"""
        if evidence_status != "ok":
            return self.FALLBACK_CONFIDENCE[evidence_status]

        best = ranked_candidates[0]
        raw_score = min(best.score / 1.2, 0.55)
        vector_score = min(best.vector_score, 1.0) * 0.25
        keyword_score = min(best.keyword_score, 1.0) * 0.12
        graph_score = 0.08 if best.graph_hit else 0.0
        direct_fact_score = min(best.direct_match_score, 1.0) * 0.25
        score = max(0.0, min(raw_score + vector_score + keyword_score + graph_score + direct_fact_score, 0.98))

        if score >= 0.75:
            label = "高"
        elif score >= 0.35:
            label = "中"
        else:
            label = "低"
        return {"score": round(score, 3), "label": label}

    def fallback_answer(self, evidence_status, confidence):
        """返回不调用 LLM 的兜底答案。"""
        messages = {
            "out_of_scope": self.OOS_MESSAGE,
            "no_evidence": self.NO_EVIDENCE_MESSAGE,
            "low_confidence": self.LOW_CONFIDENCE_MESSAGE,
        }
        return messages[evidence_status], "", [], None, False, evidence_status, confidence

    @staticmethod
    def has_project_scope_keyword(query):
        """识别明显属于企业 Wiki 范围的宽泛问题。"""
        scope_keywords = (
            "合晟",
            "项目",
            "系统",
            "需求",
            "验收",
            "测试",
            "技术",
            "架构",
            "部门",
            "人员",
            "风控",
            "合规",
            "投研",
            "权限",
            "审计",
            "预算",
        )
        return any(keyword in query for keyword in scope_keywords)

    def build_context(self, evidences):
        """把最终证据转换为 LLM 可阅读的已知参考信息。"""
        contexts = []
        for index, evidence in enumerate(evidences):
            chunk = evidence.chunk
            meta_info = f"【信息源 {index + 1}】文档：{chunk.doc_name} | 类别：{chunk.category}"
            if chunk.doc_type:
                meta_info += f" | 文档类型：{chunk.doc_type}"
            if evidence.rerank_reasons:
                meta_info += f" | 排序依据：{'；'.join(evidence.rerank_reasons)}"
            contexts.append(f"{meta_info}\n内容：{chunk.text}")
        return "\n\n".join(contexts)

    @staticmethod
    def build_prompt(query, context_str):
        """构造严格基于已编译 Wiki 证据回答的中文 Prompt。"""
        return f"""你是一个专业的企业内部 LLM Wiki 问答助手。系统已经提前把 Raw 文档、Wiki 实体、Wiki 概念和双链关系编译成结构化知识单元。请严格基于以下【已编译 Wiki 证据】回答用户提问。如果证据中没有提到，请诚实回答不知道，严禁编造和捏造事实。

【已编译 Wiki 证据】：
{context_str}

【用户提问】：
{query}

请给出严谨且结构清晰的中文回答，并优先说明答案依据："""

    def generate(self, prompt, model):
        """调用通义千问大模型，并按固定模型序列自动回退。"""
        fallback_models = [model, *LLM_FALLBACK_MODELS]
        models_to_try = []
        for candidate_model in fallback_models:
            if candidate_model not in models_to_try:
                models_to_try.append(candidate_model)

        last_exception = None
        for candidate_model in models_to_try:
            try:
                completion = self.chat_client.chat.completions.create(
                    model=candidate_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个严谨的企业 LLM Wiki 问答助手，所有回答必须基于已编译 Wiki 证据，禁止使用外部知识与幻觉。",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                )
                return completion.choices[0].message.content, candidate_model, False
            except Exception as exc:
                print(f"使用模型 {candidate_model} 失败，自动尝试回退下一个: {exc}")
                last_exception = exc

        answer = f"由于您的 API 账户状态欠费或发生其他错误，大模型无法生成最终回答。原因为：{last_exception}"
        return answer, None, True
