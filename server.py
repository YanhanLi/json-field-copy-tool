from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = 8765
MAX_PORT_TRIES = 20


@dataclass
class RubricItem:
    index: str
    title: str
    type: str
    weight: str
    source: str
    reference: str
    description: str
    is_deduction: str

    @classmethod
    def from_dict(cls, payload: dict) -> "RubricItem":
        return cls(
            index=str(payload.get("index", "")).strip(),
            title=str(payload.get("title", "")).strip(),
            type=str(payload.get("type", "")).strip(),
            weight=str(payload.get("weight", "")).strip(),
            source=str(payload.get("source", "")).strip(),
            reference=str(payload.get("reference", "")).strip(),
            description=str(payload.get("description", "")).strip(),
            is_deduction=str(payload.get("isDeductionPoints", "")).strip(),
        )

    def to_form_block(self) -> str:
        lines = [
            f"NO. {self.index}",
            f"评分点：{self.title}",
            f"类型：{self.type}",
            f"得分：{self.weight}",
            f"来源：{self.source}",
            f"引用：{self.reference}",
            f"说明：{self.description}",
        ]
        return "\n".join(lines)


def iter_rubric_files() -> list[Path]:
    results: list[Path] = []
    for path in ROOT.rglob("*.json"):
        if path.is_dir():
            continue
        if "rubric" not in path.name.lower():
            continue
        if path.parts and "rubric_copy_tool" in path.parts:
            continue
        results.append(path)
    return sorted(results)


def load_rubrics(path: Path) -> list[RubricItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("rubrics"), list):
            payload = payload["rubrics"]
        else:
            raise ValueError("JSON 根节点不是 rubric 数组，也没有 rubrics 字段")
    if not isinstance(payload, list):
        raise ValueError("JSON 根节点必须是数组")
    return [RubricItem.from_dict(item) for item in payload if isinstance(item, dict)]


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/files":
            files = []
            for path in iter_rubric_files():
                rel = path.relative_to(ROOT).as_posix()
                try:
                    count = len(load_rubrics(path))
                except Exception:
                    count = None
                files.append({"path": rel, "name": path.name, "count": count})
            return json_response(self, {"files": files, "root": str(ROOT)})

        if parsed.path == "/api/rubric":
            params = parse_qs(parsed.query)
            rel_path = params.get("path", [""])[0]
            if not rel_path:
                return json_response(self, {"error": "缺少 path 参数"}, status=400)
            path = (ROOT / rel_path).resolve()
            if ROOT not in path.parents and path != ROOT:
                return json_response(self, {"error": "非法路径"}, status=400)
            if not path.exists():
                return json_response(self, {"error": "文件不存在"}, status=404)
            try:
                items = load_rubrics(path)
            except Exception as exc:
                return json_response(self, {"error": f"读取失败：{exc}"}, status=400)
            blocks = [item.to_form_block() for item in items]
            return json_response(
                self,
                {
                    "path": rel_path,
                    "count": len(items),
                    "combined": "\n\n".join(blocks),
                    "items": [
                        {
                            "index": item.index,
                            "title": item.title,
                            "type": item.type,
                            "weight": item.weight,
                            "source": item.source,
                            "reference": item.reference,
                            "description": item.description,
                            "isDeductionPoints": item.is_deduction,
                            "block": item.to_form_block(),
                        }
                        for item in items
                    ],
                },
            )

        self.serve_static(parsed.path)

    def serve_static(self, url_path: str) -> None:
        path = STATIC_DIR / ("index.html" if url_path in {"", "/"} else url_path.lstrip("/"))
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        mime, _ = mimetypes.guess_type(path.name)
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{mime or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server() -> tuple[ThreadingHTTPServer, int]:
    last_error: OSError | None = None
    for port in range(PORT, PORT + MAX_PORT_TRIES):
        try:
            server = ThreadingHTTPServer((HOST, port), Handler)
            return server, port
        except OSError as exc:
            last_error = exc
            continue
    raise RuntimeError(
        f"无法在 {HOST}:{PORT}-{PORT + MAX_PORT_TRIES - 1} 范围内启动服务"
    ) from last_error


if __name__ == "__main__":
    print(f"Scanning rubric JSON files under: {ROOT}")
    server, actual_port = create_server()
    print(f"Rubric Copy Tool running at http://{HOST}:{actual_port}")
    if actual_port != PORT:
        print(f"Port {PORT} already in use, switched to http://{HOST}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
