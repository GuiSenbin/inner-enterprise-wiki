"""
定位：测试层。
职责：验证 Embedding 与生成模型统一由 src.config 管理，避免模型名散落在业务模块。
依赖：src.config、WikiEngine 的 Embedding 客户端和 AnswerService。
"""

import unittest

from src.answer_service import AnswerService
from src.config import DEFAULT_EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE, EMBEDDING_DIMENSION, LLM_FALLBACK_MODELS
from src.wiki_engine import DashScopeEmbeddingClient


class FakeEmbeddingEndpoint:
    """记录 Embedding 调用入参，避免测试依赖真实模型服务。"""

    def __init__(self):
        self.calls = []

    def create(self, model, input):
        self.calls.append({"model": model, "input": input})
        return type(
            "EmbeddingResponse",
            (),
            {"data": [type("EmbeddingItem", (), {"embedding": [0.0] * EMBEDDING_DIMENSION})() for _ in input]},
        )()


class FakeEmbeddingClient:
    """模拟 OpenAI 兼容客户端的 embeddings 入口。"""

    def __init__(self):
        self.embeddings = FakeEmbeddingEndpoint()


class FakeChatCompletions:
    """记录聊天模型调用顺序，并让最后一个 fallback 成功。"""

    def __init__(self):
        self.models = []

    def create(self, model, messages, temperature):
        self.models.append(model)
        if len(self.models) < 2:
            raise RuntimeError("first model unavailable")
        message = type("Message", (), {"content": "回答"})()
        choice = type("Choice", (), {"message": message})()
        return type("Completion", (), {"choices": [choice]})()


class FakeChatClient:
    """模拟 OpenAI 兼容客户端的 chat.completions 入口。"""

    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeChatCompletions()})()


class ModelConfigTest(unittest.TestCase):
    """确保换模型时只需要改 src.config。"""

    def test_embedding_client_uses_configured_embedding_model(self):
        fake_client = FakeEmbeddingClient()

        embeddings = DashScopeEmbeddingClient(fake_client).get_embeddings(["测试"])

        self.assertEqual([[0.0] * EMBEDDING_DIMENSION], embeddings)
        self.assertEqual(DEFAULT_EMBEDDING_MODEL, fake_client.embeddings.calls[0]["model"])

    def test_embedding_client_uses_configured_batch_size(self):
        fake_client = FakeEmbeddingClient()
        texts = [f"文本{i}" for i in range(EMBEDDING_BATCH_SIZE + 1)]

        DashScopeEmbeddingClient(fake_client).get_embeddings(texts)

        self.assertEqual(2, len(fake_client.embeddings.calls))
        self.assertEqual(EMBEDDING_BATCH_SIZE, len(fake_client.embeddings.calls[0]["input"]))
        self.assertEqual(1, len(fake_client.embeddings.calls[1]["input"]))

    def test_answer_service_uses_configured_fallback_models(self):
        fake_client = FakeChatClient()

        answer, used_model, failed = AnswerService(fake_client).generate("prompt", "temporary-model")

        self.assertEqual("回答", answer)
        self.assertEqual(LLM_FALLBACK_MODELS[0], used_model)
        self.assertFalse(failed)
        self.assertEqual(["temporary-model", LLM_FALLBACK_MODELS[0]], fake_client.chat.completions.models)
