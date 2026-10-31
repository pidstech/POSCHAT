# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""Windows: pywebview 창(WinForms Form)에 WebView2 컨트롤을 하나 더 붙여 웹페이지를 띄운다(browser.py가 쓴다).

pywebview(edgechromium)가 이미 불러 둔 WebView2 .NET 어셈블리를 그대로 쓴다. 폼의 오른쪽에 웹페이지 뷰를,
그 왼쪽에 크기 조절 막대(Splitter)를 붙이고, 앱 화면(pywebview의 WebView2)은 남은 자리를 채운다.

격리: 이 뷰에는 host object·WebMessage를 쓰지 않고(설정에서 끈다) 개발자 도구도 끈다. 프로필 폴더를 따로 둔다.
"""
import threading

import browser as browser_mod
from webview.platforms import edgechromium  # noqa: F401  WebView2 어셈블리 참조(clr.AddReference)를 불러 둔다

import System.Windows.Forms as WinForms  # noqa: E402
from System import Func, Type  # noqa: E402
from Microsoft.Web.WebView2.Core import CoreWebView2PermissionState  # noqa: E402
from Microsoft.Web.WebView2.WinForms import CoreWebView2CreationProperties, WebView2  # noqa: E402

READ_TIMEOUT_MS = 15000


def _color(hex_text):
    from System.Drawing import ColorTranslator
    return ColorTranslator.FromHtml(hex_text)


class WebView2Backend:
    mode = "native"

    def __init__(self, window, browser):
        self.form = getattr(window, "native", None)
        if self.form is None:
            raise browser_mod.BrowserError("앱 창을 찾지 못했습니다.")
        self.browser = browser
        self.view = None
        self.pane = None  # 1.19: 웹페이지 위 막대 + 웹페이지
        self.address = self.back_btn = self.forward_btn = self.reload_btn = None  # 1.19.1: 막대의 주소 칸·이동 버튼
        self._glyph = {}
        self.toolbar = False
        self.splitter = None
        self.ready = threading.Event()
        self.error = None
        self.pending = None
        self.ratio = browser.ratio
        self._invoke(self._create)

    def _invoke(self, fn):
        """폼의 UI 스레드에서 fn을 실행하고 결과를 돌려준다(예외는 그대로 다시 낸다)."""
        box = {}

        def run():
            try:
                box["value"] = fn()
            except Exception as e:  # .NET 예외도 여기로 온다
                box["error"] = e

        if self.form.InvokeRequired:
            self.form.Invoke(Func[Type](run))
        else:
            run()
        if "error" in box:
            raise box["error"]
        return box.get("value")

    # ---- 만들기 ----

    def _create(self):
        view = WebView2()
        props = CoreWebView2CreationProperties()
        props.UserDataFolder = str(browser_mod.profile_dir())
        view.CreationProperties = props
        view.Dock = WinForms.DockStyle.Fill
        # 1.19: 웹페이지와 그 위 막대를 한 패널에 담는다. 막대 버튼이 웹페이지 바로 위에 있어 무엇을 닫는지 분명하다
        pane = WinForms.Panel()
        pane.Dock = WinForms.DockStyle.Right
        pane.Visible = False
        pane.Controls.Add(view)  # Fill은 먼저 넣어야 막대(Top)를 뺀 나머지를 채운다
        try:
            pane.Controls.Add(self._make_toolbar())
            self.toolbar = True
        except Exception:
            self.toolbar = False  # 막대를 못 만들면 앱 화면의 주소 표시줄에 버튼을 그대로 둔다
        splitter = WinForms.Splitter()
        splitter.Dock = WinForms.DockStyle.Right
        splitter.Width = 6
        splitter.MinSize = 320
        splitter.MinExtra = 360
        splitter.Visible = False
        splitter.SplitterMoved += self._on_split
        # 도킹은 컨트롤 순서의 뒤쪽부터: 웹페이지(맨 바깥) → 막대 → 앱 화면(Fill, 맨 앞)
        self.form.Controls.Add(splitter)
        self.form.Controls.Add(pane)
        main = getattr(getattr(self.form, "browser", None), "webview", None)
        if main is not None:
            main.BringToFront()
        # 1.18.6 PLMS 숨은 로그인: 화면에 붙이기(show) 전에도 웹 뷰가 초기화되도록 창 핸들을 먼저 만든다
        pane.CreateControl()
        _ = pane.Handle
        view.CreateControl()
        _ = view.Handle
        view.CoreWebView2InitializationCompleted += self._on_ready
        view.EnsureCoreWebView2Async(None)
        self.view, self.pane, self.splitter = view, pane, splitter

    def _make_toolbar(self):
        """웹페이지 위 막대(1.19.1): 뒤로·앞으로·새로 고침, 주소 입력, '기본 브라우저로 열기', '닫기'.

        1.19.0은 버튼을 AutoSize·Padding으로 두어 화면 배율에 따라 글자 윗부분이 잘렸다. 이제 막대 높이를 넉넉히 잡고
        버튼은 막대 높이를 그대로 채운 채 글자를 가운데 놓는다. 주소 칸은 높이를 재서 세로 가운데에 둔다.
        """
        import winreg
        from System.Drawing import ContentAlignment, Font, FontStyle, Size

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                dark = winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except OSError:
            dark = False
        bg, fg, hover, field, line = (("#212121", "#ececec", "#2f2f2f", "#303030", "#383838") if dark
                                      else ("#f9f9f9", "#0d0d0d", "#ececec", "#ffffff", "#e5e5e5"))
        try:
            scale = self.form.DeviceDpi / 96
        except Exception:
            scale = 1.0
        px = lambda v: int(round(v * scale))  # noqa: E731
        bar_h = px(42)
        bar = WinForms.Panel()
        bar.Dock = WinForms.DockStyle.Top
        bar.Height = bar_h
        bar.Padding = WinForms.Padding(px(4), 0, px(4), 0)  # 세로 여백 없음: 버튼이 막대 높이를 채운다
        bar.BackColor = _color(bg)
        font = Font("Malgun Gothic", 9.0, FontStyle.Regular)
        icon_font = Font("Segoe MDL2 Assets", 10.0, FontStyle.Regular)
        icons = icon_font.Name == "Segoe MDL2 Assets"  # Windows 10 이상. 없으면 글자 화살표를 쓴다
        glyph = {"back": "\uE72B", "forward": "\uE72A", "reload": "\uE72C", "stop": "\uE711"} if icons else \
            {"back": "←", "forward": "→", "reload": "↻", "stop": "✕"}
        self._glyph = glyph

        def button(text, tip, handler, dock, use_icon=False):
            b = WinForms.Button()
            b.Text = text
            b.Dock = dock
            b.AutoSize = False
            b.UseCompatibleTextRendering = False
            b.TextAlign = ContentAlignment.MiddleCenter
            b.Font = icon_font if use_icon and icons else font
            b.Width = px(34) if use_icon else WinForms.TextRenderer.MeasureText(text, font).Width + px(18)
            b.FlatStyle = WinForms.FlatStyle.Flat
            b.FlatAppearance.BorderSize = 0
            b.FlatAppearance.MouseOverBackColor = _color(hover)
            b.ForeColor = _color(fg)
            b.BackColor = _color(bg)
            b.Cursor = WinForms.Cursors.Hand
            b.TabStop = True
            b.AccessibleName = tip
            WinForms.ToolTip().SetToolTip(b, tip)
            # 처리기는 UI 스레드에서 돈다: UI 스레드를 기다리는 일(hide·nav → _invoke)은 작업 스레드로 넘긴다(B1)
            b.Click += lambda s, e: threading.Thread(target=handler, daemon=True).start()
            return b

        # 주소 칸: 한 줄 TextBox는 높이를 글꼴이 정하므로 패널에 넣고 위 여백으로 세로 가운데에 둔다
        address = WinForms.TextBox()
        address.Font = Font("Malgun Gothic", 10.0, FontStyle.Regular)
        address.BorderStyle = WinForms.BorderStyle.FixedSingle
        address.BackColor = _color(field)
        address.ForeColor = _color(fg)
        address.Dock = WinForms.DockStyle.Top
        address.AccessibleName = "주소 또는 검색어"
        try:
            address.PlaceholderText = "주소 또는 검색어"  # .NET Core 3 이상
        except Exception:
            pass
        address.KeyDown += self._on_address_key
        holder = WinForms.Panel()
        holder.Dock = WinForms.DockStyle.Fill
        top = max(0, (bar_h - address.PreferredHeight) // 2)
        holder.Padding = WinForms.Padding(px(6), top, px(6), 0)
        holder.BackColor = _color(bg)
        holder.Controls.Add(address)

        back = button(glyph["back"], "뒤로", lambda: self.browser.bar_nav("back"), WinForms.DockStyle.Left, True)
        forward = button(glyph["forward"], "앞으로", lambda: self.browser.bar_nav("forward"), WinForms.DockStyle.Left, True)
        reload = button(glyph["reload"], "새로 고침",
                        lambda: self.browser.bar_nav("stop" if self.browser.state.get("loading") else "reload"),
                        WinForms.DockStyle.Left, True)
        external = button("↗ 기본 브라우저로 열기", "지금 페이지를 기본 브라우저로 엽니다", self.browser.open_external,
                          WinForms.DockStyle.Right)
        close = button("✕ 닫기", "브라우저 닫기", self.browser.hide, WinForms.DockStyle.Right)
        back.Enabled = forward.Enabled = False
        border = WinForms.Panel()  # 막대와 웹페이지 사이 가는 선
        border.Dock = WinForms.DockStyle.Bottom
        border.Height = max(1, px(1))
        border.BackColor = _color(line)

        # Dock은 나중에 넣은 것부터 자리를 잡는다: 선(아래) → 닫기(맨 오른쪽) → 기본 브라우저로 열기 → 뒤로(맨 왼쪽)
        # → 앞으로 → 새로 고침 → 주소 칸(나머지)
        for control in (holder, reload, forward, back, external, close, border):
            bar.Controls.Add(control)
        bar.MinimumSize = Size(0, bar_h)
        self.address, self.back_btn, self.forward_btn, self.reload_btn = address, back, forward, reload
        return bar

    def _on_address_key(self, sender, e):
        if e.KeyCode == WinForms.Keys.Enter:
            e.Handled = e.SuppressKeyPress = True  # 띵 소리 없이
            text = str(sender.Text or "")
            threading.Thread(target=self.browser.bar_open, args=(text,), daemon=True).start()
        elif e.KeyCode == WinForms.Keys.Escape:
            e.Handled = e.SuppressKeyPress = True
            sender.Text = str(self.browser.state.get("url") or "")

    def _sync_bar(self, url=None, loading=None, can_back=None, can_forward=None):
        """막대의 주소·버튼 상태를 맞춘다(UI 스레드). 주소 칸에 입력하는 중이면 글자를 덮어쓰지 않는다."""
        try:
            if url is not None and self.address is not None and not self.address.Focused:
                self.address.Text = url
            if can_back is not None and self.back_btn is not None:
                self.back_btn.Enabled = bool(can_back)
            if can_forward is not None and self.forward_btn is not None:
                self.forward_btn.Enabled = bool(can_forward)
            if loading is not None and self.reload_btn is not None:
                self.reload_btn.Text = self._glyph["stop" if loading else "reload"]
                self.reload_btn.AccessibleName = "멈추기" if loading else "새로 고침"
        except Exception:
            pass

    def focus_address(self):
        """브라우저를 처음 열 때 주소 칸에 입력할 수 있게 한다."""
        def go():
            if self.address is not None:
                self.address.Focus()
                self.address.SelectAll()
        try:
            self._invoke(go)
        except Exception:
            pass

    def _on_ready(self, sender, args):
        if not args.IsSuccess:
            self.error = str(args.InitializationException)
            self.ready.set()
            return
        core = self.view.CoreWebView2
        settings = core.Settings
        settings.AreHostObjectsAllowed = False  # 웹페이지가 앱 객체를 부를 길을 막는다
        settings.IsWebMessageEnabled = False
        settings.AreDevToolsEnabled = False
        settings.IsStatusBarEnabled = True
        core.NavigationStarting += self._on_starting
        core.NavigationCompleted += self._on_completed
        core.SourceChanged += lambda s, e: self._report()
        core.DocumentTitleChanged += lambda s, e: self._report()
        core.HistoryChanged += lambda s, e: self._report()
        core.NewWindowRequested += self._on_new_window
        core.PermissionRequested += self._on_permission
        try:
            core.DownloadStarting += self._on_download
        except Exception:
            pass  # 오래된 WebView2 런타임
        self.ready.set()
        if self.pending:
            url, self.pending = self.pending, None
            core.Navigate(url)

    # ---- 이벤트 ----

    # 이 처리기들은 UI 스레드에서 돈다. 여기서 막는 호출(evaluate_js처럼 UI 스레드를 기다리는 것)을 하면 안 된다:
    # browser.navigated() → Bridge._push()는 큐에 넣고 바로 돌아온다(ui_events, B1).
    def _report(self, loading=None):
        core = self.view.CoreWebView2 if self.view is not None else None
        if core is None:
            return
        self._sync_bar(url=str(core.Source or ""), loading=loading, can_back=bool(core.CanGoBack),
                       can_forward=bool(core.CanGoForward))
        self.browser.navigated(url=str(core.Source or ""), title=str(core.DocumentTitle or ""), loading=loading,
                               can_back=bool(core.CanGoBack), can_forward=bool(core.CanGoForward))

    def _on_starting(self, sender, e):
        url = str(e.Uri or "")
        if not browser_mod.allowed(url) and url != "about:blank":
            e.Cancel = True
            self.browser.blocked(url, "http·https 주소만 열 수 있습니다.")
            return
        self._sync_bar(loading=True)
        self.browser.navigated(loading=True)

    def _on_completed(self, sender, e):
        self._report(loading=False)

    def _on_new_window(self, sender, e):
        e.Handled = True  # 새 창 대신 같은 뷰에서 연다
        url = str(e.Uri or "")
        if browser_mod.allowed(url):
            self.view.CoreWebView2.Navigate(url)

    def _on_permission(self, sender, e):
        e.State = CoreWebView2PermissionState.Deny  # 카메라·마이크·위치·알림 등

    def _on_download(self, sender, e):
        e.Cancel = True
        self.browser.blocked(str(e.DownloadOperation.Uri or ""), "다운로드는 기본 브라우저에서 하세요(외부 브라우저로 열기).")

    def _on_split(self, sender, e):
        width = self.form.ClientSize.Width
        if width > 0 and self.pane is not None:
            self.ratio = self.pane.Width / width
            self.browser.ratio = round(self.ratio, 3)

    # ---- browser.Browser가 부른다 ----

    def _layout(self, ratio):
        self.pane.Width = max(320, int(self.form.ClientSize.Width * ratio))

    def show(self, ratio):
        def go():
            self._layout(ratio)
            self.splitter.Visible = True
            self.pane.Visible = True
        self._invoke(go)

    def hide(self):
        def go():
            self.pane.Visible = False
            self.splitter.Visible = False
        self._invoke(go)

    def set_ratio(self, ratio):
        self._invoke(lambda: self._layout(ratio))

    def open(self, url):
        def go():
            if self.view.CoreWebView2 is None:
                self.pending = url
            else:
                self.view.CoreWebView2.Navigate(url)
        self._invoke(go)

    def _core_call(self, name):
        def go():
            core = self.view.CoreWebView2
            if core is not None:
                getattr(core, name)()
        self._invoke(go)

    def back(self):
        self._core_call("GoBack")

    def forward(self):
        self._core_call("GoForward")

    def reload(self):
        self._core_call("Reload")

    def stop(self):
        self._core_call("Stop")

    def read(self, script):
        if not self.ready.wait(20):
            raise browser_mod.BrowserError("웹페이지 뷰를 준비하지 못했습니다.")
        if self.error:
            raise browser_mod.BrowserError(f"WebView2를 시작하지 못했습니다: {self.error}")
        task = self._invoke(lambda: self.view.CoreWebView2.ExecuteScriptAsync(script))
        # UI 스레드 밖(이 함수를 부른 작업 스레드)에서 기다린다. UI 스레드가 비어 있어야 결과가 온다.
        if not task.Wait(READ_TIMEOUT_MS):
            raise browser_mod.BrowserError("웹페이지가 응답하지 않습니다.")
        return str(task.Result)

    def plms_cookies(self, origin, clear=False):
        if not self.ready.wait(20) or self.error:
            raise browser_mod.BrowserError("PLMS 브라우저가 준비되지 않았습니다.")
        manager = self._invoke(lambda: self.view.CoreWebView2.CookieManager)
        task = self._invoke(lambda: manager.GetCookiesAsync(origin))
        if not task.Wait(READ_TIMEOUT_MS):
            raise browser_mod.BrowserError("PLMS 세션을 읽지 못했습니다.")
        def finish():
            # 쿠키 속성도 WebView2의 UI 스레드에서만 읽을 수 있다.
            cookies = list(task.Result)
            if clear:
                for cookie in cookies:
                    if str(cookie.Domain).lstrip(".") == "plms.postech.ac.kr":
                        manager.DeleteCookie(cookie)
                return []
            return [{"name": str(c.Name), "value": str(c.Value), "path": str(c.Path)} for c in cookies]
        return self._invoke(finish)

    def screenshot(self):
        """보이는 웹페이지를 PNG로(1.16 브라우저 에이전트). 작업 스레드에서 부른다(UI 스레드에서 결과를 기다리지 않는다)."""
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        from System.IO import MemoryStream

        if not self.ready.wait(20) or self.error:
            raise browser_mod.BrowserError("웹페이지 뷰를 준비하지 못했습니다.")
        stream = MemoryStream()
        task = self._invoke(lambda: self.view.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream))
        if not task.Wait(READ_TIMEOUT_MS):
            raise browser_mod.BrowserError("화면을 캡처하지 못했습니다.")
        return bytes(stream.ToArray())

    def close(self):
        if self.form.IsDisposed or self.form.Disposing:
            self.view = self.pane = self.splitter = None  # 앱 창이 이미 닫혔다(앱 종료): 컨트롤도 함께 정리됐다
            return

        def go():
            for control in (self.pane, self.splitter):  # 패널을 지우면 안의 웹페이지·막대도 함께 정리된다
                if control is not None:
                    self.form.Controls.Remove(control)
                    control.Dispose()
        self._invoke(go)
        self.view = self.pane = self.splitter = None
