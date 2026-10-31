# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""macOS: pywebview 창(NSWindow)의 내용을 NSSplitView로 바꿔 왼쪽에 앱 화면, 오른쪽에 WKWebView를 둔다(browser.py가 쓴다).

격리: 이 WKWebView에는 스크립트 메시지 핸들러(window.webkit.messageHandlers)를 하나도 달지 않는다.
http·https 밖의 주소, 새 창(같은 뷰에서 연다), 다운로드는 내비게이션 대리자에서 막는다.
"""
import threading

import AppKit
import Foundation
import WebKit
from objc import super  # noqa: A004
from PyObjCTools import AppHelper

import browser as browser_mod

READ_TIMEOUT = 15


class _Delegate(AppKit.NSObject):
    """WKNavigationDelegate + WKUIDelegate. 메인(UI) 스레드에서 불린다: 여기서 UI 스레드를 기다리는 호출을 하면 안 된다
    (browser.navigated() → Bridge._push()는 큐에 넣고 바로 돌아온다, ui_events·B1)."""

    def initWithOwner_(self, owner):
        self = super(_Delegate, self).init()
        if self is not None:
            self.owner = owner
        return self

    def webView_decidePolicyForNavigationAction_decisionHandler_(self, webview, action, handler):
        url = str(action.request().URL().absoluteString() or "")
        if browser_mod.allowed(url) or url == "about:blank":
            handler(getattr(WebKit, "WKNavigationActionPolicyAllow", 1))
        else:
            handler(getattr(WebKit, "WKNavigationActionPolicyCancel", 0))
            self.owner.browser.blocked(url, "http·https 주소만 열 수 있습니다.")

    def webView_decidePolicyForNavigationResponse_decisionHandler_(self, webview, response, handler):
        if response.canShowMIMEType():
            handler(WebKit.WKNavigationResponsePolicyAllow)
        else:  # 화면에 보일 수 없는 파일 = 다운로드
            handler(WebKit.WKNavigationResponsePolicyCancel)
            self.owner.browser.blocked(str(response.response().URL().absoluteString() or ""),
                                       "다운로드는 기본 브라우저에서 하세요(외부 브라우저로 열기).")

    def webView_didStartProvisionalNavigation_(self, webview, nav):
        self.owner._sync_bar(loading=True)
        self.owner.browser.navigated(loading=True)

    def webView_didFinishNavigation_(self, webview, nav):
        self.owner.report(webview, loading=False)
        # didFinish 시점에 webview.title()이 아직 비어 있을 때가 있어 문서 제목을 한 번 더 읽는다
        webview.evaluateJavaScript_completionHandler_("document.title", self.owner.title_handler(webview))

    def webView_didFailNavigation_withError_(self, webview, nav, error):
        self.owner.report(webview, loading=False)

    def webView_didFailProvisionalNavigation_withError_(self, webview, nav, error):
        self.owner.report(webview, loading=False)

    # 1.19 웹페이지 위 막대의 버튼(메인 스레드). hide는 메인 스레드를 기다리므로 작업 스레드로 넘긴다(B1)
    def closeBrowser_(self, sender):
        threading.Thread(target=self.owner.browser.hide, daemon=True).start()

    def openExternal_(self, sender):
        threading.Thread(target=self.owner.browser.open_external, daemon=True).start()

    # 1.19.1 막대의 이동 버튼·주소 칸
    def goBack_(self, sender):
        threading.Thread(target=self.owner.browser.bar_nav, args=("back",), daemon=True).start()

    def goForward_(self, sender):
        threading.Thread(target=self.owner.browser.bar_nav, args=("forward",), daemon=True).start()

    def reloadPage_(self, sender):
        action = "stop" if self.owner.browser.state.get("loading") else "reload"
        threading.Thread(target=self.owner.browser.bar_nav, args=(action,), daemon=True).start()

    def addressEntered_(self, sender):
        text = str(sender.stringValue() or "")
        threading.Thread(target=self.owner.browser.bar_open, args=(text,), daemon=True).start()

    def webView_createWebViewWithConfiguration_forNavigationAction_windowFeatures_(self, webview, config, action,
                                                                                  features):
        url = str(action.request().URL().absoluteString() or "")
        if browser_mod.allowed(url):
            webview.loadRequest_(action.request())  # 새 창 대신 같은 뷰에서 연다
        return None


class WKWebViewBackend:
    mode = "native"

    def __init__(self, window, browser):
        self.ns_window = getattr(window, "native", None)
        if self.ns_window is None:
            raise browser_mod.BrowserError("앱 창을 찾지 못했습니다.")
        self.browser = browser
        self.split = None
        self.view = None
        self.pane = None  # 1.19: 웹페이지 위 막대 + 웹페이지
        self.address = self.back_btn = self.forward_btn = self.reload_btn = None  # 1.19.1 막대의 주소 칸·이동 버튼
        self.toolbar = False
        self.main_view = None
        self.delegate = None
        self._run(self._create)

    def _run(self, fn, wait=True):
        """메인(UI) 스레드에서 fn을 실행한다. wait면 끝날 때까지 기다리고 결과를 돌려준다."""
        if threading.current_thread() is threading.main_thread():
            return fn()
        box, done = {}, threading.Event()

        def go():
            try:
                box["value"] = fn()
            except Exception as e:
                box["error"] = e
            finally:
                done.set()

        AppHelper.callAfter(go)
        if not wait:
            return None
        if not done.wait(20):
            raise browser_mod.BrowserError("앱 화면이 응답하지 않습니다.")
        if "error" in box:
            raise box["error"]
        return box.get("value")

    def _create(self):
        main = self.ns_window.contentView()
        frame = main.frame()
        config = WebKit.WKWebViewConfiguration.alloc().init()  # 메시지 핸들러 없음
        view = WebKit.WKWebView.alloc().initWithFrame_configuration_(frame, config)
        self.delegate = _Delegate.alloc().initWithOwner_(self)
        view.setNavigationDelegate_(self.delegate)
        view.setUIDelegate_(self.delegate)
        view.setAllowsBackForwardNavigationGestures_(True)
        split = AppKit.NSSplitView.alloc().initWithFrame_(frame)
        split.setVertical_(True)  # 왼쪽·오른쪽
        split.setDividerStyle_(AppKit.NSSplitViewDividerStyleThin)
        split.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        split.addSubview_(main)  # 앱 화면(pywebview WKWebView)을 왼쪽으로 옮긴다
        pane = view
        try:
            pane = self._make_pane(frame, view)
            self.toolbar = True
        except Exception:
            self.toolbar = False  # 막대를 못 만들면 앱 화면의 주소 표시줄에 버튼을 그대로 둔다
        split.addSubview_(pane)
        self.ns_window.setContentView_(split)
        pane.setHidden_(True)
        self.split, self.view, self.pane, self.main_view = split, view, pane, main

    def _make_pane(self, frame, view):
        """웹페이지와 그 위 막대(1.19.1: 뒤로·앞으로·새로 고침, 주소 칸, 기본 브라우저로 열기, 닫기). 좌표는 왼쪽 아래가 원점이다.

        막대는 버튼 높이보다 넉넉하게(40) 잡고 모든 컨트롤을 세로 가운데에 둔다(1.19.0은 윗부분이 살짝 잘렸다).
        """
        bar_h = 40
        w, h = frame.size.width, frame.size.height
        pane = AppKit.NSView.alloc().initWithFrame_(frame)
        pane.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        view.setFrame_(Foundation.NSMakeRect(0, 0, w, h - bar_h))
        view.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        pane.addSubview_(view)
        bar = AppKit.NSView.alloc().initWithFrame_(Foundation.NSMakeRect(0, h - bar_h, w, bar_h))
        bar.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewMinYMargin)

        def place(control, x, width, mask):
            ch = control.frame().size.height
            control.setFrame_(Foundation.NSMakeRect(x, round((bar_h - ch) / 2), width, ch))
            control.setAutoresizingMask_(mask)
            bar.addSubview_(control)

        def nav_button(image_name, fallback, tip, action):
            image = AppKit.NSImage.imageNamed_(image_name) if image_name else None
            if image is not None:
                b = AppKit.NSButton.buttonWithImage_target_action_(image, self.delegate, action)
            else:
                b = AppKit.NSButton.buttonWithTitle_target_action_(fallback, self.delegate, action)
            b.setToolTip_(tip)
            b.sizeToFit()
            return b

        # 오른쪽: 닫기(맨 오른쪽) → 기본 브라우저로 열기
        close = AppKit.NSButton.buttonWithTitle_target_action_("닫기", self.delegate, "closeBrowser:")
        close.setToolTip_("브라우저 닫기")
        external = AppKit.NSButton.buttonWithTitle_target_action_("기본 브라우저로 열기", self.delegate, "openExternal:")
        external.setToolTip_("지금 페이지를 기본 브라우저로 엽니다")
        right = w - 8
        for b in (close, external):
            b.sizeToFit()
            bw = b.frame().size.width
            right -= bw
            place(b, right, bw, AppKit.NSViewMinXMargin)
            right -= 4
        # 왼쪽: 뒤로 → 앞으로 → 새로 고침
        back = nav_button(getattr(AppKit, "NSImageNameGoLeftTemplate", "NSGoLeftTemplate"), "←", "뒤로", "goBack:")
        forward = nav_button(getattr(AppKit, "NSImageNameGoRightTemplate", "NSGoRightTemplate"), "→", "앞으로", "goForward:")
        reload = nav_button(getattr(AppKit, "NSImageNameRefreshTemplate", "NSRefreshTemplate"), "↻", "새로 고침", "reloadPage:")
        x = 8
        for b in (back, forward, reload):
            bw = max(30, b.frame().size.width)
            place(b, x, bw, AppKit.NSViewMaxXMargin)
            x += bw + 2
        back.setEnabled_(False)
        forward.setEnabled_(False)
        # 가운데: 주소 칸(Enter로 연다)
        address = AppKit.NSTextField.alloc().initWithFrame_(Foundation.NSMakeRect(0, 0, 100, 24))
        address.setPlaceholderString_("주소 또는 검색어")
        address.setBezelStyle_(AppKit.NSTextFieldRoundedBezel)
        address.setTarget_(self.delegate)
        address.setAction_("addressEntered:")
        address.cell().setSendsActionOnEndEditing_(False)  # Enter를 눌렀을 때만 연다
        address.cell().setScrollable_(True)
        address.setAccessibilityLabel_("주소 또는 검색어")
        place(address, x + 4, max(60, right - x - 8), AppKit.NSViewWidthSizable)
        line = AppKit.NSBox.alloc().initWithFrame_(Foundation.NSMakeRect(0, 0, w, 1))
        line.setBoxType_(AppKit.NSBoxSeparator)
        line.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        bar.addSubview_(line)
        pane.addSubview_(bar)
        self.address, self.back_btn, self.forward_btn, self.reload_btn = address, back, forward, reload
        return pane

    def _sync_bar(self, url=None, loading=None, can_back=None, can_forward=None):
        """막대의 주소·버튼 상태를 맞춘다(메인 스레드). 주소 칸에 입력하는 중이면 글자를 덮어쓰지 않는다."""
        try:
            if url is not None and self.address is not None and self.address.currentEditor() is None:
                self.address.setStringValue_(url)
            if can_back is not None and self.back_btn is not None:
                self.back_btn.setEnabled_(bool(can_back))
            if can_forward is not None and self.forward_btn is not None:
                self.forward_btn.setEnabled_(bool(can_forward))
            if loading is not None and self.reload_btn is not None:
                self.reload_btn.setToolTip_("멈추기" if loading else "새로 고침")
                name = getattr(AppKit, "NSImageNameStopProgressTemplate" if loading else "NSImageNameRefreshTemplate", None)
                image = AppKit.NSImage.imageNamed_(name) if name else None
                if image is not None:
                    self.reload_btn.setImage_(image)
        except Exception:
            pass

    def focus_address(self):
        """브라우저를 처음 열 때 주소 칸에 입력할 수 있게 한다."""
        def go():
            if self.address is not None:
                self.ns_window.makeFirstResponder_(self.address)
                self.address.selectText_(None)
        try:
            self._run(go)
        except Exception:
            pass

    def report(self, webview, loading=None):
        url = webview.URL()
        self._sync_bar(url=str(url.absoluteString()) if url is not None else None, loading=loading,
                       can_back=bool(webview.canGoBack()), can_forward=bool(webview.canGoForward()))
        self.browser.navigated(url=str(url.absoluteString()) if url is not None else "", title=str(webview.title() or ""),
                               loading=loading, can_back=bool(webview.canGoBack()),
                               can_forward=bool(webview.canGoForward()))

    def title_handler(self, webview):
        def done(result, error):
            if error is None and result:
                self.browser.navigated(title=str(result))
        return done

    def _layout(self, ratio):
        width = self.split.frame().size.width
        self.split.setPosition_ofDividerAtIndex_(width * (1 - ratio), 0)

    def show(self, ratio):
        def go():
            self.pane.setHidden_(False)
            self.split.adjustSubviews()
            self._layout(ratio)
        self._run(go)

    def hide(self):
        def go():
            self.pane.setHidden_(True)
            self.split.adjustSubviews()
        self._run(go)

    def set_ratio(self, ratio):
        self._run(lambda: self._layout(ratio))

    def open(self, url):
        def go():
            request = Foundation.NSURLRequest.requestWithURL_(Foundation.NSURL.URLWithString_(url))
            self.view.loadRequest_(request)
        self._run(go)

    def back(self):
        self._run(lambda: self.view.goBack())

    def forward(self):
        self._run(lambda: self.view.goForward())

    def reload(self):
        self._run(lambda: self.view.reload())

    def stop(self):
        self._run(lambda: self.view.stopLoading())

    def read(self, script):
        box, done = {}, threading.Event()

        def handler(result, error):
            box["result"], box["error"] = result, error
            done.set()

        self._run(lambda: self.view.evaluateJavaScript_completionHandler_(script, handler), wait=False)
        if not done.wait(READ_TIMEOUT):
            raise browser_mod.BrowserError("웹페이지가 응답하지 않습니다.")
        if box.get("error") is not None:
            raise browser_mod.BrowserError(f"웹페이지를 읽지 못했습니다: {box['error']}")
        return str(box.get("result") or "")

    def plms_cookies(self, origin, clear=False):
        box, done = {}, threading.Event()

        def receive(cookies):
            matching = [c for c in cookies if "plms.postech.ac.kr" == str(c.domain()).lstrip(".")
                        or "plms.postech.ac.kr".endswith("." + str(c.domain()).lstrip("."))]
            if clear:
                store = self.view.configuration().websiteDataStore().httpCookieStore()
                pending = [c for c in matching if str(c.domain()).lstrip(".") == "plms.postech.ac.kr"]
                remaining = [len(pending)]
                def deleted():
                    remaining[0] -= 1
                    if remaining[0] == 0:
                        done.set()
                for cookie in pending:
                    store.deleteCookie_completionHandler_(cookie, deleted)
                if not pending:
                    done.set()
            else:
                box["cookies"] = [{"name": str(c.name()), "value": str(c.value()), "path": str(c.path())} for c in matching]
                done.set()

        self._run(lambda: self.view.configuration().websiteDataStore().httpCookieStore().getAllCookies_(receive), wait=False)
        if not done.wait(READ_TIMEOUT):
            raise browser_mod.BrowserError("PLMS 세션을 읽지 못했습니다.")
        return box.get("cookies", [])

    def screenshot(self):
        """보이는 웹페이지를 PNG로(1.16 브라우저 에이전트). 작업 스레드에서 부른다."""
        box, done = {}, threading.Event()

        def handler(image, error):
            try:
                if image is not None:
                    rep = AppKit.NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
                    box["png"] = bytes(rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {}))
                box["error"] = error
            finally:
                done.set()

        self._run(lambda: self.view.takeSnapshotWithConfiguration_completionHandler_(None, handler), wait=False)
        if not done.wait(READ_TIMEOUT) or not box.get("png"):
            raise browser_mod.BrowserError("화면을 캡처하지 못했습니다.")
        return box["png"]

    def close(self):
        def go():
            if self.split is not None and self.main_view is not None:
                self.ns_window.setContentView_(self.main_view)  # 앱 화면을 원래대로
            if self.pane is not None:
                self.pane.removeFromSuperview()
        self._run(go)
        self.split = self.view = self.pane = None
