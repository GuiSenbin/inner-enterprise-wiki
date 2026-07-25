"""
定位：后端配置模块。
职责：集中维护服务入口和查询接口共享的模型、Top K 与请求限制配置。
依赖：仅依赖 Python 标准库常量能力，不读取环境变量和业务数据。
"""

DEFAULT_LLM_MODEL = "qwen-plus-2025-07-28"
ALLOWED_LLM_MODELS = (
    "qwen-plus-2025-07-28",
    "qwen-plus",
    "qwen-turbo",
    "qwen-long",
    "qwen-max",
)
LLM_FALLBACK_MODELS = (
    "qwen-plus-2025-07-28",
    "qwen-turbo",
    "qwen-long",
    "qwen-max",
)
DEFAULT_EMBEDDING_MODEL = "qwen3.7-text-embedding"
EMBEDDING_DIMENSION = 1024
EMBEDDING_BATCH_SIZE = 20
DEFAULT_TOP_K = 5
MAX_JSON_BODY_BYTES = 64 * 1024
