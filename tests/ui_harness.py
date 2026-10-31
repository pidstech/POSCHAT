# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""화면 점검용 하네스: web/ 화면을 브라우저에서 열고 window.pywebview.api 호출을 실제 main.Bridge로 넘긴다.

    python tests/ui_harness.py            # http://127.0.0.1:8765 에서 직접 열어 보기
    (tests/test_ui_smoke.py가 Playwright로 같은 하네스를 띄워 점검한다)

데이터 폴더는 임시 폴더이고(APPDATA를 바꾼다), 비밀은 파일 저장소를 쓴다. Python → 화면 이벤트는
/events를 0.3초마다 가져와 window.onBackendEvent로 넘긴다.
"""
import json
import os
import sys
import tempfile
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INIT_SCRIPT = """
window.pywebview = { api: new Proxy({}, { get: (_, name) => (...args) =>
  fetch('/api/' + String(name), { method: 'POST', body: JSON.stringify(args) }).then(async (r) => {
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'API error');
    return data;
  }) }) };
setInterval(() => fetch('/events').then((r) => r.json()).then((evs) => evs.forEach((ev) => window.onBackendEvent && window.onBackendEvent(ev))), 300);
"""


class _Window:
    def __init__(self, events):
        self.events = events

    def evaluate_js(self, script):
        prefix = "window.onBackendEvent("
        if script.startswith(prefix):
            self.events.append(json.loads(script[len(prefix):-1]))

    def create_file_dialog(self, *args, **kwargs):
        return None


def make_bridge(data_dir):
    os.environ["APPDATA"] = str(data_dir)
    os.environ["POSTECH_CHAT_SECRETS"] = "file"
    sys.path.insert(0, str(ROOT))
    sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))
    import main

    events = []
    bridge = main.Bridge()
    bridge._window = _Window(events)
    return bridge, events


def serve(bridge, events, port=0):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, status, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if self.path == "/events":
                # 복사와 비우기 사이에 앱의 이벤트 스레드가 더한 이벤트를 잃지 않도록, 복사한 만큼만 지운다
                # (예전에는 그 사이에 온 이벤트가 사라져 SSH 'connected' 같은 이벤트를 화면이 못 받는 일이 있었다)
                with lock:
                    n = len(events)
                    out = events[:n]
                    del events[:n]
                return self._send(200, out)
            path = (ROOT / "web" / self.path.lstrip("/").split("?")[0]).resolve()
            if self.path in ("/", ""):
                path = ROOT / "web" / "index.html"
            if ROOT / "web" not in path.parents and path != ROOT / "web" / "index.html" or not path.is_file():
                return self._send(404, {"error": "not found"})
            ctype = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2"}.get(
                path.suffix, "application/octet-stream")
            self._send(200, path.read_bytes(), ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))

        def do_POST(self):  # noqa: N802
            name = self.path[len("/api/"):]
            args = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"[]")
            fn = getattr(bridge, name, None)
            if name.startswith("_") or not callable(fn):
                return self._send(404, {"error": f"unknown api {name}"})
            try:
                self._send(200, fn(*args))
            except Exception as e:  # 화면에 오류를 그대로 보인다
                self._send(500, {"error": f"{type(e).__name__}: {e}"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        bridge, events = make_bridge(tmp)
        server = serve(bridge, events, 8765)
        print("http://127.0.0.1:8765  (Ctrl+C로 끝내기). 브라우저 콘솔에 아래 스크립트를 먼저 넣으세요:\n" + INIT_SCRIPT)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            server.shutdown()
