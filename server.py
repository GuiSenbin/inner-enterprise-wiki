"""
定位：服务入口层。
职责：提供合晟资产内部 Wiki 的 HTTP API、索引状态、问答请求、索引重建和静态页面托管。
依赖：WikiEngine、web 静态目录和 Python 标准库 HTTP 服务。
"""

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from src.config import ALLOWED_LLM_MODELS, DEFAULT_LLM_MODEL, DEFAULT_TOP_K, MAX_JSON_BODY_BYTES


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_WEB_DIR = PROJECT_DIR / "web"


class AppState:
    """保存 Web 服务运行状态，并延迟初始化 WikiEngine。"""

    def __init__(self, web_dir=DEFAULT_WEB_DIR, engine_factory=None):
        """设置静态资源目录和可替换的查询引擎工厂，便于测试注入假引擎。"""
        self.web_dir = Path(web_dir)
        self.engine_factory = engine_factory
        self._engine = None

    def get_engine(self):
        """按需创建并缓存查询引擎，首次创建时尝试加载本地索引。"""
        if self._engine is None:
            factory = self.engine_factory
            if factory is None:
                from src.wiki_engine import WikiEngine

                factory = WikiEngine
            self._engine = factory()
            self._engine.load_index()
        return self._engine

    def status_payload(self):
        """返回前端状态栏需要展示的索引加载状态和知识库规模。"""
        engine = self.get_engine()
        index_loaded = engine.index is not None and len(engine.chunks) > 0
        graph = getattr(engine, "graph", None)
        graph_edge_count = graph.number_of_edges() if graph is not None and hasattr(graph, "number_of_edges") else 0
        return {
            "index_loaded": index_loaded,
            "chunk_count": len(engine.chunks),
            "node_count": len(engine.all_nodes),
            "graph_edge_count": graph_edge_count,
            "compiled_at": getattr(engine, "compiled_at", None),
        }


def create_handler(state):
    """创建绑定 AppState 的请求处理类，避免全局变量耦合并方便单元测试。"""
    class WikiRequestHandler(BaseHTTPRequestHandler):
        server_version = "HeshengWiki/1.0"

        def log_message(self, format, *args):
            return

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/status":
                self.handle_status()
                return
            if parsed.path == "/api/config":
                self.handle_config()
                return
            self.serve_static()

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/answer":
                self.handle_answer()
                return
            if parsed.path == "/api/rebuild":
                self.handle_rebuild()
                return
            self.write_json({"error": "未找到接口。"}, status=404)

        def handle_status(self):
            self.write_json(state.status_payload())

        def handle_config(self):
            """返回前端生成模型选择器需要的白名单配置。"""
            self.write_json({
                "default_model": DEFAULT_LLM_MODEL,
                "models": list(ALLOWED_LLM_MODELS),
            })

        def handle_answer(self):
            """校验用户问题并委托 WikiEngine 生成带证据的问答结果。"""
            payload = self.read_json()
            if self.write_json_error_if_needed(payload):
                return
            query = str(payload.get("query", "")).strip()
            model = str(payload.get("model", DEFAULT_LLM_MODEL)).strip()

            if not query:
                self.write_json({"error": "请输入问题后再检索。"}, status=400)
                return
            if model not in ALLOWED_LLM_MODELS:
                self.write_json({"error": f"不支持的模型：{model}"}, status=400)
                return

            try:
                result = state.get_engine().answer_question(query, top_k=DEFAULT_TOP_K, model=model)
                self.write_json(result)
            except Exception as exc:
                self.write_json({"error": f"处理问答请求失败：{exc}"}, status=500)

        def handle_rebuild(self):
            """触发本地索引重建，并返回重建后的状态信息。"""
            if not self.is_same_origin_request():
                self.write_json({"error": "拒绝跨站触发重建索引。"}, status=403)
                return

            payload = self.read_json()
            if self.write_json_error_if_needed(payload):
                return

            try:
                engine = state.get_engine()
                engine.build_index()
                self.write_json({
                    "message": "索引构建成功。",
                    **state.status_payload(),
                })
            except Exception as exc:
                self.write_json({"error": f"索引构建失败：{exc}"}, status=500)

        def serve_static(self):
            """托管 web 静态文件，并防止路径逃逸到 web 目录之外。"""
            parsed_path = unquote(urlparse(self.path).path)
            relative = parsed_path.lstrip("/") or "index.html"
            target = (state.web_dir / relative).resolve()
            web_root = state.web_dir.resolve()

            try:
                target.relative_to(web_root)
            except ValueError:
                target = web_root / "index.html"

            if not target.exists() or not target.is_file():
                target = web_root / "index.html"

            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.write_body(body)

        def read_json(self):
            """读取请求体中的 JSON；空请求体按空对象处理。"""
            try:
                length = int(self.headers.get("Content-Length", 0)) if hasattr(self, "headers") else 0
            except ValueError:
                return {"_error": "请求体长度无效。", "_status": 400}
            if length <= 0:
                return {}
            if length > MAX_JSON_BODY_BYTES:
                return {"_error": "请求体过大。", "_status": 413}
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return {"_error": "请求体不是合法 JSON。", "_status": 400}

        def write_json_error_if_needed(self, payload):
            if isinstance(payload, dict) and "_error" in payload:
                self.write_json({"error": payload["_error"]}, status=payload.get("_status", 400))
                return True
            return False

        def is_same_origin_request(self):
            origin = self.headers.get("Origin") if hasattr(self, "headers") else None
            if not origin:
                return True
            host = self.headers.get("Host", "")
            parsed = urlparse(origin)
            return parsed.netloc == host

        def write_json(self, payload, status=200):
            """以 UTF-8 JSON 形式写出接口响应。"""
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.write_body(body)

        def write_body(self, body):
            if hasattr(self, "wfile_write"):
                self.wfile_write(body)
            else:
                self.wfile.write(body)

    return WikiRequestHandler


def main():
    """解析命令行参数并启动本地 HTTP 服务。"""
    parser = argparse.ArgumentParser(description="启动合晟资产内部 Wiki 问答服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    state = AppState()
    handler = create_handler(state)
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"合晟资产内部 Wiki 已启动：http://{args.host}:{args.port}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
