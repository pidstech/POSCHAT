# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""연구·작업용 브라우저(1.13): 채팅 옆에 웹페이지를 띄우고, 보고 있는 페이지를 AI가 읽게 한다.

화면 구성: 앱 창을 둘로 나눠 왼쪽은 POSCHAT 화면, 오른쪽은 웹페이지. 주소 표시줄·뒤로·앞으로 같은 조작은
POSCHAT 화면(web/browser.js)에 두고, 웹페이지는 플랫폼의 네이티브 웹 뷰가 그린다.

  Windows  pywebview 창(WinForms Form)에 WebView2 컨트롤을 하나 더 붙인다(browser_win.py)
  macOS    pywebview 창(NSWindow)의 내용을 NSSplitView로 바꾸고 WKWebView를 하나 더 둔다(browser_mac.py)
  Android  MainActivity가 화면을 나눠 WebView를 하나 더 둔다(android_main.AndroidBrowser)
  그 밖에  네이티브 붙이기가 실패하면 pywebview 창을 하나 더 열어 앱 창 옆에 붙인다(DockedBackend)

격리(반드시 지킨다):
- 웹페이지 쪽 웹 뷰에는 POSCHAT의 Python API(js_api·JavascriptInterface·host object·메시지 통로)를 하나도 주지 않는다.
  웹페이지가 POSCHAT을 부를 길이 없다. 앱이 웹페이지를 읽기만 한다(evaluate script → 글·주소·선택한 글).
- 읽은 내용은 AI에게 '외부 데이터'로 표시해 넘긴다(그 안의 지시를 따르지 않는다).
- http·https만 연다(file:, javascript:, data:, 앱 내부 주소는 막는다). 새 창은 같은 뷰에서 열고, 다운로드와
  카메라·마이크·위치 같은 권한 요청은 거절한다. 쿠키·저장소는 앱 화면과 다른 프로필 폴더에 둔다.
"""
import ipaddress
import json
import re
import threading
from urllib.parse import quote_plus, urlparse

import storage

HOME_URL = "https://www.google.com/"
SEARCH_URL = "https://www.google.com/search?q={}"
MAX_TEXT = 200_000
ALLOWED_SCHEMES = ("http", "https")
DEFAULT_RATIO = 0.55  # 웹페이지 쪽이 차지하는 너비 비율

# 웹페이지에서 글·선택한 글·논문 식별자를 읽는 스크립트. 결과는 JSON 문자열(모든 플랫폼에서 같은 모양).
READ_SCRIPT = r"""
(() => {
  const meta = (n) => { const m = document.querySelector(`meta[name="${n}"], meta[property="${n}"]`); return m ? m.content : ""; };
  const sel = (window.getSelection && String(window.getSelection())) || "";
  const main = document.querySelector("article, main, [role=main]") || document.body;
  const text = (main && main.innerText) || (document.body && document.body.innerText) || "";
  return JSON.stringify({
    url: location.href, title: document.title || "", selection: sel.slice(0, 20000),
    text: text.slice(0, %d), lang: document.documentElement.lang || "",
    description: meta("description") || meta("og:description"),
    doi: meta("citation_doi") || meta("dc.identifier") || meta("DC.identifier"),
    arxiv: meta("citation_arxiv_id"), pdf: meta("citation_pdf_url"),
    citation_title: meta("citation_title"),
  });
})()
""" % MAX_TEXT

ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)


class BrowserError(Exception):
    pass


def profile_dir():
    """웹페이지 쪽의 쿠키·저장소(앱 화면과 따로)."""
    path = storage.APP_DIR / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _private_host(host):
    """앱 내부·로컬 파일 서버처럼 열면 안 되는 주소. localhost는 연구용 로컬 서버(Jupyter 등)를 위해 연다."""
    host = (host or "").strip("[]").lower()
    if host in ("", "0.0.0.0", "appassets.androidplatform.net"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified


def allowed(url):
    """웹페이지 쪽 뷰가 열어도 되는 주소인지."""
    try:
        p = urlparse(str(url))
    except ValueError:
        return False
    return p.scheme in ALLOWED_SCHEMES and bool(p.netloc) and not _private_host(p.hostname)


def normalize(text):
    """주소창 입력을 열 주소로. 주소처럼 보이지 않으면 검색한다."""
    text = str(text or "").strip()
    if not text:
        return HOME_URL
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", text) and not re.match(r"^[^/:]+:\d+(/|$)", text):
        if allowed(text):
            return text
        raise BrowserError("http·https 주소만 열 수 있습니다.")
    looks_like_host = " " not in text and ("." in text.split("/")[0] or text.startswith("localhost"))
    if looks_like_host:
        url = ("http://" if text.startswith(("localhost", "127.")) else "https://") + text
        if allowed(url):
            return url
    return SEARCH_URL.format(quote_plus(text))


def parse_page(raw):
    """READ_SCRIPT 결과(JSON 문자열 또는 dict)를 정리한다."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = None
        if isinstance(raw, str):  # 한 번 더 감싼 JSON(WebView2·Android evaluateJavascript)
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = None
    if not isinstance(raw, dict):
        raise BrowserError("웹페이지 내용을 읽지 못했습니다. 페이지가 다 열린 뒤 다시 시도하세요.")
    page = {k: str(raw.get(k) or "") for k in ("url", "title", "selection", "text", "lang", "description", "doi",
                                                "arxiv", "pdf", "citation_title")}
    page["text"] = page["text"][:MAX_TEXT]
    page["paper"] = paper_id(page)
    return page


def paper_id(page):
    """연구 라이브러리에 더할 식별자(arXiv 번호·DOI) 또는 ""."""
    if page.get("arxiv"):
        return page["arxiv"]
    m = ARXIV_RE.search(page.get("url", ""))
    if m:
        return m.group(1)
    doi = (page.get("doi") or "").removeprefix("doi:").strip()
    if DOI_RE.fullmatch(doi):
        return doi
    m = DOI_RE.search(page.get("url", ""))
    return m.group(1).rstrip(".") if m else ""


def page_markdown(page, selection_only=False):
    """AI에게 넘길 페이지 글(첨부 파일 내용)."""
    head = [f"# {page['title'] or page['url']}", f"주소: {page['url']}"]
    if page.get("paper"):
        head.append(f"논문 식별자: {page['paper']}")
    if selection_only:
        return "\n".join(head + ["", "## 선택한 부분", "", page["selection"].strip()]) + "\n"
    if page.get("description"):
        head.append(f"요약(메타데이터): {page['description']}")
    return "\n".join(head + ["", page["text"].strip()]) + "\n"


# ---- 컨트롤러 ----

class Browser:
    """웹페이지 뷰 하나를 다룬다. backend는 open·back·forward·reload·hide·read·set_ratio를 가진다.

    on_event(dict)로 주소·제목·불러오는 중·뒤로 갈 수 있는지를 화면에 알린다(Bridge가 {"type": "browser"}로 보낸다).
    """

    def __init__(self, backend_factory, on_event=None, ratio=DEFAULT_RATIO):
        self._factory = backend_factory
        self._backend = None
        self._lock = threading.RLock()
        self.on_event = on_event
        self.ratio = ratio
        self.visible = False
        self.state = {"url": "", "title": "", "loading": False, "can_back": False, "can_forward": False}
        self.mode = ""  # native | docked | android
        self.watch = None  # (url) -> None: 에이전트가 조작 중일 때 주소 변경을 알린다
        self.opener = None  # (url) -> None: 1.19 웹페이지 위 막대의 '기본 브라우저로 열기'(Bridge._open_url)

    def _emit(self, **changes):
        self.state.update(changes)
        if self.on_event:
            try:
                # toolbar: 웹페이지 위에 네이티브 막대(1.19.1: 주소 칸·이동·기본 브라우저로 열기·닫기)를 붙였는지.
                # 화면은 붙였으면 채팅 위 주소 줄을 빼고 그린다
                self.on_event(dict(self.state, visible=self.visible, mode=self.mode,
                                   toolbar=bool(getattr(self._backend, "toolbar", False))))
            except Exception:
                pass

    def _ensure(self):
        if self._backend is None:
            self._backend = self._factory(self)
            self.mode = getattr(self._backend, "mode", "native")
        return self._backend

    # backend가 부른다 — 네이티브 이벤트 처리기(UI 스레드)에서 오므로 _lock을 잡지 않고, on_event도 막지 않아야 한다(B1)
    def navigated(self, url=None, title=None, loading=None, can_back=None, can_forward=None):
        changes = {k: v for k, v in (("url", url), ("title", title), ("loading", loading), ("can_back", can_back),
                                     ("can_forward", can_forward)) if v is not None}
        self._emit(**changes)
        watch = self.watch  # 1.16 브라우저 에이전트: 주소가 바뀌면 요소 ID를 무효로(표시만, 막지 않는다)
        if watch is not None and url:
            try:
                watch(url)
            except Exception:
                pass

    def blocked(self, url, reason):
        if self.on_event:
            self.on_event({"kind": "blocked", "url": str(url)[:300], "reason": reason})

    # Bridge가 부른다
    def open(self, text):
        url = normalize(text)
        with self._lock:
            backend = self._ensure()
            if not self.visible:
                backend.show(self.ratio)
                self.visible = True
            self._emit(url=url, loading=True)  # 먼저 알린다: 빨리 열리면 backend가 바로 '다 열림'을 알린다
            backend.open(url)
        return url

    def ensure(self):
        """웹 뷰를 만들되 화면에는 붙이지 않는다(PLMS 숨은 로그인·조회용)."""
        with self._lock:
            self._ensure()

    def open_background(self, text):
        """화면에 보이지 않게 주소를 연다. 이미 보이는 브라우저면 그대로 보인 채 이동한다."""
        url = normalize(text)
        with self._lock:
            backend = self._ensure()
            self._emit(url=url, loading=True)
            backend.open(url)
        return url

    def show(self):
        with self._lock:
            if self.visible:
                return
            backend = self._ensure()
            backend.show(self.ratio)
            self.visible = True
            if not self.state["url"]:
                backend.open(HOME_URL)
        self._emit()

    def hide(self):
        with self._lock:
            if self._backend is not None and self.visible:
                self._backend.hide()
            self.visible = False
        self._emit()

    def open_external(self):
        """1.19 웹페이지 위 막대의 '기본 브라우저로 열기'. 네이티브 버튼 처리기가 작업 스레드에서 부른다."""
        url = self.state.get("url", "")
        if url and allowed(url) and self.opener:
            self.opener(url)

    # 1.19.1 웹페이지 위 막대의 주소 칸·이동 버튼. 네이티브 처리기가 작업 스레드에서 부르므로 오류는 화면 알림으로 돌린다
    def bar_open(self, text):
        if not str(text or "").strip():
            return
        try:
            self.open(text)
        except Exception as e:
            self.blocked(str(text)[:300], str(e) if isinstance(e, BrowserError) else f"주소를 열지 못했습니다: {e}")

    def bar_nav(self, action):
        try:
            self.nav(action)
        except Exception:
            pass  # 브라우저가 닫히는 중이면 버튼을 눌러도 할 일이 없다

    def focus_address(self):
        """브라우저를 열 때 웹페이지 위 막대의 주소 칸에 입력할 수 있게 한다(막대가 없으면 아무것도 하지 않는다)."""
        backend = self._backend
        fn = getattr(backend, "focus_address", None) if backend is not None else None
        if fn is not None and getattr(backend, "toolbar", False):
            fn()
            return True
        return False

    def nav(self, action):
        if action not in ("back", "forward", "reload", "stop"):
            raise BrowserError("알 수 없는 동작입니다.")
        with self._lock:
            if self._backend is None or not self.visible:
                raise BrowserError("브라우저가 열려 있지 않습니다.")
            getattr(self._backend, action)()

    def set_ratio(self, ratio):
        self.ratio = min(0.8, max(0.25, float(ratio)))
        with self._lock:
            if self._backend is not None and self.visible:
                self._backend.set_ratio(self.ratio)
        return self.ratio

    def read(self):
        with self._lock:
            if self._backend is None or not self.visible or not self.state["url"]:
                raise BrowserError("열린 웹페이지가 없습니다. 브라우저에서 페이지를 먼저 여세요.")
            backend = self._backend
        page = parse_page(backend.read(READ_SCRIPT))
        if page["url"] and not allowed(page["url"]):
            raise BrowserError("이 페이지는 읽을 수 없습니다.")
        return page

    def run_script(self, script, url_ok):
        """PLMS 자동 로그인 전용(숨은 웹 뷰 포함): 지금 열린 주소가 url_ok일 때만 스크립트를 돌리고 결과 글자를 돌려준다."""
        with self._lock:
            if self._backend is None:
                raise BrowserError("열린 웹페이지가 없습니다.")
            if not url_ok(self.state.get("url", "")):
                return "blocked"
            backend = self._backend
        return str(backend.read(script) or "").strip('"')

    def plms_cookies(self, clear=False):
        """PLMS 모듈 전용. 쿠키는 화면 API·모델에 반환하지 않는다."""
        from plms import ORIGIN

        with self._lock:
            if self._backend is None:
                raise BrowserError("PLMS 브라우저에서 먼저 로그인하세요.")
            fn = getattr(self._backend, "plms_cookies", None)
            if fn is None:
                raise BrowserError("PLMS 연결에는 Windows·macOS 네이티브 브라우저가 필요합니다.")
        return fn(ORIGIN, clear)

    def close(self):
        with self._lock:
            if self._backend is not None:
                try:
                    self._backend.close()
                except Exception:
                    pass
            self._backend = None
            self.visible = False


# ---- 데스크톱 백엔드 고르기 ----

def desktop_factory(window):
    """pywebview 창 window에 붙는 백엔드를 만든다. 네이티브가 안 되면 옆에 붙는 창으로."""

    def make(browser):
        import sys

        errors = []
        try:
            if sys.platform == "win32":
                import browser_win
                return browser_win.WebView2Backend(window, browser)
            if sys.platform == "darwin":
                import browser_mac
                return browser_mac.WKWebViewBackend(window, browser)
        except Exception as e:  # 네이티브 붙이기 실패: 옆 창으로
            errors.append(f"{type(e).__name__}: {e}")
        backend = DockedBackend(window, browser)
        backend.note = "; ".join(errors)
        return backend

    return make


class DockedBackend:
    """pywebview 창을 하나 더 열어 앱 창 오른쪽에 붙인다(js_api 없음). 앱 창을 옮기거나 크기를 바꾸면 따라간다."""

    mode = "docked"

    def __init__(self, main_window, browser):
        import webview

        self._webview = webview
        self._main = main_window
        self._browser = browser
        self._win = None
        self.note = ""
        self._ratio = DEFAULT_RATIO

    def _place(self):
        if self._win is None:
            return
        try:
            m = self._main
            width = int(m.width * self._ratio / (1 - self._ratio))
            self._win.move(m.x + m.width, m.y)
            self._win.resize(max(420, width), m.height)
        except Exception:
            pass

    def show(self, ratio):
        self._ratio = ratio
        if self._win is None:
            self._win = self._webview.create_window("POSCHAT 브라우저", url=HOME_URL, width=720, height=800,
                                                    text_select=True)  # js_api를 주지 않는다
            self._win.events.loaded += self._loaded
            self._win.events.closed += lambda: self._browser.hide()
            self._main.events.moved += lambda *a: self._place()
            self._main.events.resized += lambda *a: self._place()
        else:
            self._win.show()
        self._place()

    def _harden(self):
        """pywebview가 모든 창에 여는 메시지 통로를 이 창에서는 닫는다(웹페이지 → 앱 호출 차단)."""
        native = getattr(self._win, "native", None)
        try:
            import sys

            if sys.platform == "darwin":
                webview_view = native.contentView()
                webview_view.configuration().userContentController().removeScriptMessageHandlerForName_("browserDelegate")
            elif sys.platform == "win32":
                settings = native.browser.webview.CoreWebView2.Settings
                settings.IsWebMessageEnabled = False
                settings.AreHostObjectsAllowed = False
                settings.AreDevToolsEnabled = False
            self.hardened = True
        except Exception as e:
            self.note = (self.note + "; " if self.note else "") + f"harden: {type(e).__name__}: {e}"

    def _loaded(self):
        if not getattr(self, "hardened", False):
            self._harden()
        url = self._win.get_current_url() or ""
        if url and not allowed(url):
            self._browser.blocked(url, "http·https 주소만 열 수 있습니다.")
            self._win.load_url(HOME_URL)
            return
        try:
            title = self._win.evaluate_js("document.title") or ""
        except Exception:
            title = ""
        self._browser.navigated(url=url, title=str(title), loading=False, can_back=True)

    def open(self, url):
        self._win.load_url(url)

    def back(self):
        self._win.evaluate_js("history.back()")

    def forward(self):
        self._win.evaluate_js("history.forward()")

    def reload(self):
        self._win.evaluate_js("location.reload()")

    def stop(self):
        self._win.evaluate_js("window.stop()")

    def hide(self):
        if self._win is not None:
            self._win.hide()

    def set_ratio(self, ratio):
        self._ratio = ratio
        self._place()

    def read(self, script):
        return self._win.evaluate_js(script)

    def close(self):
        if self._win is not None:
            self._win.destroy()
            self._win = None
