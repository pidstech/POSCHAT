# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""1.13 브라우저 기술 검증 + 1.15 B1(앱 멈춤) 회귀 시험. CI의 Windows·macOS 작업이 실제 pywebview 창에서 실행한다.

    python tests/browser_spike.py [결과.json]                  # 고친 방식(ui_events 큐)으로 모든 단계 확인
    python tests/browser_spike.py [결과.json] --legacy-push    # 1.13~1.14 방식(처리기에서 바로 evaluate_js)이
                                                               # 앱 창을 멈추게 하는지 재현(멈추면 종료 코드 0)

실제 앱처럼 브라우저 이벤트를 받으면 앱 창에 window.onBackendEvent(...)를 evaluate_js로 실행한다(main.Bridge._push와 같은 길).
단계마다 앱 창이 응답하는지(evaluate_js가 RESPONSIVE_SECONDS 안에 돌아오는지) 본다.

확인하는 것:
1. 네이티브 방식(Windows WebView2 컨트롤, macOS WKWebView 분할)으로 붙는지(mode == "native")
2. 로컬 페이지를 열고 주소·제목·불러오기 완료 이벤트가 오고, 앱 화면(window.onBackendEvent)에도 도착하는지
3. 페이지의 글과 선택한 글, 논문 식별자(meta citation_doi)를 읽는지
4. 격리: 웹페이지 쪽에 window.pywebview가 없고, chrome.webview.hostObjects로 앱 객체에 닿지 못하며, postMessage가 앱에 오지 않는지
5. 링크 이동·뒤로·앞으로·새로 고침·빠른 연속 이동·차단된 주소·이벤트 폭주(제목·주소 수백 번 바뀜)·불러오는 중 닫기
6. 숨기기·다시 보이기·닫기가 오류 없이 되고, 그 사이 앱 창이 계속 응답하는지
"""
import json
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>Spike Page</title>
<meta name="citation_doi" content="10.1234/poschat.5678"></head>
<body><main><h1>POSCHAT-SPIKE-OK</h1><p id="p">선택할 문장입니다.</p><a id="next" href="/two">다음</a>
<a id="bad" href="file:///C:/Windows/win.ini">파일</a></main>
<script>
const r = document.createRange(); r.selectNodeContents(document.getElementById('p'));
getSelection().removeAllRanges(); getSelection().addRange(r);
window.__isolation = JSON.stringify({pywebview: typeof window.pywebview,
  hostObjects: typeof (window.chrome && window.chrome.webview && window.chrome.webview.hostObjects),
  webkitHandlers: typeof (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.browserDelegate),
  postMessage: typeof (window.chrome && window.chrome.webview && window.chrome.webview.postMessage)});
// WebView2는 chrome.webview.hostObjects 프록시를 늘 넣어 둔다. 실제로 앱 객체에 닿는지 불러 본다.
window.__hostProbe = 'pending';
(async () => {
  const h = window.chrome && window.chrome.webview && window.chrome.webview.hostObjects;
  if (!h) { window.__hostProbe = 'none'; return; }
  for (const name of ['api', 'pywebview', 'bridge', 'external']) {
    try { await h[name]; window.__hostProbe = 'reachable:' + name; return; } catch (e) {}
  }
  window.__hostProbe = 'blocked';
})();
</script></body></html>"""
PAGE_TWO = "<!doctype html><title>Two</title><p>second page</p>"
# 이벤트 폭주: 제목을 300번, 주소(pushState)를 100번 바꾼다 → DocumentTitleChanged·SourceChanged·HistoryChanged가 쏟아진다
PAGE_FLOOD = """<!doctype html><title>flood-0</title><p>flood</p><script>
let i = 0;
const t = setInterval(() => {
  i++; document.title = 'flood-' + i;
  if (i % 3 === 0) history.pushState({}, '', '/flood?s=' + i);
  if (i >= 300) { clearInterval(t); document.title = 'flood-done'; }
}, 1);
</script>"""
PAGE_SLOW = "<!doctype html><title>Slow</title><p>slow page</p>"
# 1.16 브라우저 에이전트: 네이티브 뷰에서 스냅샷·입력·고르기·폼 제출·캡처
PAGE_FORM = """<!doctype html><title>Form</title><main><form action="/result" method="get">
<label for="q">검색어</label><input id="q" name="q"><select name="field"><option value="all">전체</option><option value="title">제목</option></select>
<button type="submit">검색</button></form></main>"""
APP_HTML = """<!doctype html><title>app</title><h1>app</h1>
<script>window.__events = []; window.onBackendEvent = (e) => { window.__events.push(e); };</script>"""
RESPONSIVE_SECONDS = 5


def message_probe(backend):
    """WebView2: 앱 쪽에 WebMessageReceived를 달아 두고 웹페이지가 postMessage를 보내게 한 뒤, 받은 수를 센다.
    IsWebMessageEnabled=False면 함수는 남아 있어도 메시지가 앱에 오지 않아야 한다. 다른 플랫폼은 None."""
    if getattr(backend, "view", None) is None or not hasattr(backend, "_invoke"):
        return None
    from Microsoft.Web.WebView2.Core import CoreWebView2WebMessageReceivedEventArgs
    from System import EventHandler

    got = []
    on_message = EventHandler[CoreWebView2WebMessageReceivedEventArgs](lambda sender, args: got.append(1))
    backend._invoke(lambda: backend.view.CoreWebView2.add_WebMessageReceived(on_message))
    try:
        backend.read("(function(){try{window.chrome.webview.postMessage('poschat-probe');"
                     "window.chrome.webview.postMessage({probe:1});return 'sent'}catch(e){return 'threw'}})()")
        time.sleep(1.5)
    finally:
        backend._invoke(lambda: backend.view.CoreWebView2.remove_WebMessageReceived(on_message))
    return len(got)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/slow"):
            time.sleep(4)  # 불러오는 중에 닫기
        if self.path.startswith("/result"):
            from urllib.parse import parse_qs, urlparse

            q = parse_qs(urlparse(self.path).query)
            pages_result = f"<!doctype html><title>Result</title><main>RESULT {q.get('q', [''])[0]} {q.get('field', [''])[0]}</main>"
            body = pages_result.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        pages = {"/two": PAGE_TWO, "/flood": PAGE_FLOOD, "/slow": PAGE_SLOW, "/form": PAGE_FORM}
        body = next((v for k, v in pages.items() if self.path.startswith(k)), PAGE).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def js_value(raw):
    """플랫폼마다 다르게 감싼 스크립트 결과(WebView2는 JSON 문자열로 한 번 더 감싼다)를 값으로."""
    for _ in range(2):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                break
    return raw


def wait_for(cond, timeout=30, step=0.2):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return False


def responsive(window, seconds=RESPONSIVE_SECONDS):
    """앱 창이 응답하는지: 다른 스레드에서 evaluate_js가 seconds 안에 돌아오면 True."""
    box = {}

    def probe():
        try:
            box["value"] = window.evaluate_js("1 + 1")
        except Exception as e:
            box["error"] = repr(e)
    t = threading.Thread(target=probe, daemon=True)
    t.start()
    t.join(seconds)
    return not t.is_alive() and "error" not in box


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔(cp1252)에서 한글 출력이 죽지 않게
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    import webview

    import browser
    import ui_events

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    legacy = "--legacy-push" in sys.argv
    out = Path(args[0] if args else "browser-spike.json")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    report = {"platform": sys.platform, "mode": "legacy-push" if legacy else "queued-push", "ok": False, "steps": []}
    events = []

    window = webview.create_window("POSCHAT spike", html=APP_HTML, width=1100, height=760)

    def send(event):
        # main.Bridge._send_event와 같다: 앱 화면에 이벤트를 실행한다
        window.evaluate_js(f"window.onBackendEvent({json.dumps(event, ensure_ascii=False)})")

    pump = ui_events.EventPump(send)

    def on_event(event):
        events.append(event)
        if legacy:
            send(event)  # 1.13~1.14의 Bridge._push: 네이티브 처리기(UI 스레드)에서 그대로 evaluate_js
        else:
            pump.push(event)  # 1.15: 큐에 넣고 바로 돌아온다

    def step(name, ok, detail=""):
        report["steps"].append({"step": name, "ok": bool(ok), "detail": str(detail)[:500]})
        print(("PASS " if ok else "FAIL ") + name, detail if not ok else "", flush=True)
        return ok

    def alive(name):
        return step(f"app responsive: {name}", responsive(window))

    def finish(code):
        report["events"] = events[-10:]
        report["pump"] = dict(pump.stats)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        import os
        os._exit(code)

    shown = threading.Event()
    window.events.loaded += shown.set

    def run_legacy():
        """예전 방식이 앱 창을 멈추게 하는지 재현한다. 멈추면(재현) 종료 코드 0, 멈추지 않으면 1."""
        step("app window loaded", shown.wait(60))
        step("app responsive before opening", responsive(window))
        b = browser.Browser(browser.desktop_factory(window), on_event=on_event)
        threading.Thread(target=lambda: b.open(url), daemon=True).start()  # open도 멈출 수 있어 따로 돌린다
        hung = False
        for _ in range(6):  # 최대 약 30초: 페이지가 열리며 이벤트가 오는 동안 앱 창이 응답하는지
            time.sleep(1)
            if not responsive(window):
                hung = True
                break
        report["deadlock_reproduced"] = hung
        step("legacy push freezes the app window (B1 reproduced)", hung, json.dumps(b.state))
        report["ok"] = hung
        finish(0 if hung else 1)

    def run():
        try:
            # 앱 화면이 다 열린 뒤에 붙인다(실제 앱에서도 사용자가 브라우저를 여는 것은 화면이 뜬 뒤다)
            step("app window loaded", shown.wait(60), f"native={type(getattr(window, 'native', None)).__name__}")
            b = browser.Browser(browser.desktop_factory(window), on_event=on_event)
            print("... attaching the page view and opening", url, flush=True)
            b.open(url)
            step("backend", b.mode == "native", f"mode={b.mode} note={getattr(b._backend, 'note', '')}")
            loaded = wait_for(lambda: b.state["url"].startswith(url) and not b.state["loading"] and b.state["title"])
            step("navigation events", loaded, json.dumps(b.state))
            alive("after open")
            pump.flush(10)
            got = js_value(window.evaluate_js("JSON.stringify(window.__events.slice(-1))"))
            last = got[-1] if isinstance(got, list) and got else {}
            step("app screen received browser events", isinstance(last, dict) and str(last.get("url", "")).startswith(url),
                 json.dumps(last)[:300])
            print("... reading the page", flush=True)
            page = b.read()
            step("read text", "POSCHAT-SPIKE-OK" in page["text"], page["text"][:200])
            step("read selection", "선택할 문장" in page["selection"], page["selection"])
            step("paper id", page["paper"] == "10.1234/poschat.5678", page["paper"])
            iso = js_value(b._backend.read("window.__isolation || '{}'"))
            iso = iso if isinstance(iso, dict) else {}
            probe = "pending"
            for _ in range(20):
                probe = js_value(b._backend.read("window.__hostProbe || 'none'"))
                if probe != "pending":
                    break
                time.sleep(0.25)
            iso["hostProbe"] = probe
            iso["messagesReceived"] = message_probe(b._backend)
            step("isolation", iso.get("pywebview") == "undefined" and probe in ("none", "blocked")
                 and iso.get("webkitHandlers") in ("undefined", None)
                 and iso["messagesReceived"] in (0, None), iso)
            try:
                browser.normalize("file:///C:/Windows/win.ini")
                step("file url blocked", False, "normalize accepted file:")
            except browser.BrowserError:
                step("file url blocked", True)
            # 웹페이지가 스스로 file: 주소로 가려 해도 열리지 않아야 한다(대리자가 막거나 웹 엔진이 거부한다)
            b._backend.read("document.getElementById('bad').click(); 'ok'")
            time.sleep(1.5)
            blocked = [e for e in events if e.get("kind") == "blocked"]
            step("in-page file: navigation blocked", not b.state["url"].startswith("file:"),
                 f"url={b.state['url']} blocked_events={len(blocked)}")
            alive("after blocked navigation")
            b._backend.read("document.getElementById('next').click(); 'ok'")
            moved = wait_for(lambda: b.state["url"].endswith("/two") and not b.state["loading"])
            step("link navigation", moved, json.dumps(b.state))
            b.nav("back")
            back = wait_for(lambda: not b.state["url"].endswith("/two") and not b.state["loading"])
            step("back", back, json.dumps(b.state))
            alive("after back")
            b.nav("forward")
            fwd = wait_for(lambda: b.state["url"].endswith("/two") and not b.state["loading"])
            step("forward", fwd, json.dumps(b.state))
            seen = len(events)
            b.nav("reload")
            reloaded = wait_for(lambda: len(events) > seen and b.state["url"].endswith("/two") and not b.state["loading"])
            step("reload", reloaded, json.dumps(b.state))
            alive("after reload")
            print("... rapid navigation", flush=True)
            for i in range(10):
                b.open(f"{url}two?i={i}")
            rapid = wait_for(lambda: b.state["url"].endswith("two?i=9") and not b.state["loading"])
            step("rapid navigation", rapid, json.dumps(b.state))
            alive("after rapid navigation")
            print("... event flood", flush=True)
            before = len(events)
            b.open(f"{url}flood")
            # Windows는 제목·주소가 바뀔 때마다 이벤트가 온다. macOS 백엔드는 다 열릴 때만 알리므로 페이지를 직접 읽어 끝났는지 본다.
            flooded = wait_for(lambda: b.state["title"] == "flood-done"
                               or js_value(b._backend.read("document.title")) == "flood-done", timeout=40)
            step("event flood", flooded, f"events={len(events) - before} state={json.dumps(b.state)}")
            alive("during/after event flood")
            step("event queue drained", pump.flush(15), json.dumps(pump.stats))
            print("... browser agent (1.16)", flush=True)
            import browser_agent

            asked = []
            ag = browser_agent.BrowserAgent(b, lambda kind, title, detail: asked.append(kind) or True)
            b.watch = ag.on_navigated
            try:
                ag.open(f"{url}form")
                obs = ag.take_snapshot()
                els = ag.snapshot["elements"].values()
                q = next(e["id"] for e in els if e.get("text") == "검색어")
                sel = next(e["id"] for e in els if e["tag"] == "select")
                btn = next(e["id"] for e in els if e.get("text") == "검색")
                step("agent snapshot", "검색어" in obs and len(ag.snapshot["elements"]) >= 3, obs[:300])
                ag.type(q, "native")
                ag.select(sel, "제목")
                ag.click(btn)
                done = wait_for(lambda: "RESULT native title" in str(js_value(b._backend.read("document.body.innerText"))), timeout=15)
                step("agent type/select/submit", done and "send" in asked, f"asked={asked} state={json.dumps(b.state)}")
                png = ag.screenshot()
                step("agent screenshot", png[:4] == b"\x89PNG", f"{len(png)} bytes")
            except Exception as e:
                step("agent actions", False, f"{type(e).__name__}: {e}")
            b.watch = None
            alive("after browser agent")
            print("... closing while a page is loading", flush=True)
            b.open(f"{url}slow")
            time.sleep(0.5)
            b.close()
            step("close while loading", True)
            alive("after close while loading")
            b = browser.Browser(browser.desktop_factory(window), on_event=on_event)
            b.open(url)
            again = wait_for(lambda: b.state["url"].startswith(url) and not b.state["loading"] and b.state["title"])
            step("reopen after close", again, json.dumps(b.state))
            b.hide()
            b.show()
            b.set_ratio(0.4)
            step("hide/show/ratio", True)
            alive("after hide/show")
            b.close()
            step("close", True)
            alive("after close")
            report["ok"] = all(s["ok"] for s in report["steps"])
        except Exception:
            report["error"] = traceback.format_exc()
            print(report["error"], flush=True)
        finally:
            report["events"] = events[-10:]
            report["pump"] = dict(pump.stats)
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            pump.stop()
            window.destroy()

    def watchdog():
        time.sleep(90 if legacy else 240)
        print("TIMEOUT: steps so far", json.dumps(report["steps"], ensure_ascii=False), flush=True)
        report.setdefault("error", "timeout — 앱 창이 멈췄거나 단계가 끝나지 않았다")
        finish(3)

    threading.Thread(target=watchdog, daemon=True).start()
    print("... starting pywebview", "(legacy push)" if legacy else "", flush=True)
    webview.start(run_legacy if legacy else run)
    server.shutdown()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
