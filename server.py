from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(__file__).resolve().parent / "static"
HOST = "127.0.0.1"
PORT = 8765
MAX_PORT_TRIES = 20

PREFERRED_CONTAINER_KEYS = ["items", "records", "rows", "entries", "data", "rubrics"]
PREFERRED_FIELD_ORDER = [
    "title",
    "name",
    "prompt",
    "question",
    "type",
    "category",
    "weight",
    "score",
    "points",
    "source",
    "reference",
    "description",
    "summary",
    "notes",
]
TITLE_CANDIDATES = ["title", "name", "prompt", "question", "summary", "description"]
BADGE_CANDIDATES = ["type", "category", "tag", "kind"]


def stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [stringify(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def is_record_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


def extract_record_list(payload: object) -> list[dict]:
    if is_record_list(payload):
        return payload
    if isinstance(payload, dict):
        for key in PREFERRED_CONTAINER_KEYS:
            value = payload.get(key)
            if is_record_list(value):
                return value
        if all(not isinstance(value, (dict, list)) for value in payload.values()):
            return [payload]
    raise ValueError("JSON 顶层需要是对象数组，或对象里包含一组对象数组字段")


def order_keys(record: dict) -> list[str]:
    keys = list(record.keys())
    preferred = [key for key in PREFERRED_FIELD_ORDER if key in record]
    remaining = [key for key in keys if key not in preferred]
    return preferred + remaining


def prettify_key(key: str) -> str:
    if not key:
        return ""
    key = key.replace("_", " ").replace("-", " ").strip()
    if not key:
        return ""
    return key[:1].upper() + key[1:]


def record_title(record: dict, fallback_index: int) -> str:
    for key in TITLE_CANDIDATES:
        value = stringify(record.get(key))
        if value:
            return value
    if stringify(record.get("index")):
        return f"Record {stringify(record.get('index'))}"
    return f"Record {fallback_index}"


def record_badge(record: dict) -> str:
    for key in BADGE_CANDIDATES:
        value = stringify(record.get(key))
        if value:
            return value
    return ""


def normalize_record(record: dict, fallback_index: int) -> dict:
    fields = []
    for key in order_keys(record):
        value = stringify(record.get(key))
        fields.append(
            {
                "key": key,
                "label": prettify_key(key),
                "value": value,
            }
        )

    non_empty_fields = [field for field in fields if field["value"]]
    display_index = stringify(record.get("index")) or str(fallback_index)
    title = record_title(record, fallback_index)
    badge = record_badge(record)
    combined = "\n\n".join(
        f"{field['label'] or field['key']}：{field['value']}" for field in non_empty_fields
    )

    return {
        "index": display_index,
        "displayTitle": title,
        "badge": badge,
        "fields": fields,
        "combined": combined,
        "raw": {key: stringify(value) for key, value in record.items()},
    }


def iter_json_files() -> list[Path]:
    results: list[Path] = []
    for path in ROOT.rglob("*.json"):
        if path.is_dir():
            continue
        if "rubric_copy_tool" in path.parts:
            continue
        results.append(path)
    return sorted(results)


def load_records(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = extract_record_list(payload)
    return [normalize_record(record, idx) for idx, record in enumerate(records, start=1)]


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
            for path in iter_json_files():
                rel = path.relative_to(ROOT).as_posix()
                try:
                    count = len(load_records(path))
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
                items = load_records(path)
            except Exception as exc:
                return json_response(self, {"error": f"读取失败：{exc}"}, status=400)
            return json_response(
                self,
                {
                    "path": rel_path,
                    "count": len(items),
                    "combined": "\n\n\n".join(item["combined"] for item in items if item["combined"]),
                    "items": items,
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
    print(f"Scanning JSON files under: {ROOT}")
    server, actual_port = create_server()
    print(f"JSON Field Copy Tool running at http://{HOST}:{actual_port}")
    if actual_port != PORT:
        print(f"Port {PORT} already in use, switched to http://{HOST}:{actual_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
