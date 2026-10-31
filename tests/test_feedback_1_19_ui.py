# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""1.19 공개 전 사용자 피드백 화면 시험: 시작 창 크기 설정, 사용법 가이드 카드·제목, 사용량 그래프,
어두운 화면의 링크 색과 다녀온 링크, PLMS 창에서 계정 저장, 브라우저 막대의 버튼 위치.

Playwright가 없으면 건너뛴다. POSTECH_UI_SHOTS 폴더가 주어지면 스크린숏을 남긴다.
"""
import importlib.util
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright가 없어 화면 점검을 건너뜁니다")
class FeedbackUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import storage
        import ui_harness
        from support import isolated_app_dir, preserved_hooks

        cls.saved_env = {k: os.environ.get(k) for k in ("APPDATA", "POSTECH_CHAT_SECRETS")}
        cls.hooks = preserved_hooks()
        cls.hooks.__enter__()
        cls.isolation = isolated_app_dir()
        data_dir = cls.isolation.__enter__()
        cls.bridge, cls.events = ui_harness.make_bridge(data_dir)
        cls.bridge.save_settings({"api_key": "test-key"})
        # 그래프에 그릴 사용량: 오늘과 사흘 전
        for days_ago, (i, o) in ((0, (1200, 300)), (3, (5000, 900))):
            day = time.strftime("%Y-%m-%d", time.localtime(time.time() - days_ago * 86400))
            data = storage._load_usage()
            data[day] = {"calls": 2, "token_calls": 2, "input_tokens": i, "output_tokens": o}
            storage._write_json(storage.USAGE_PATH, data)
        cls.server = ui_harness.serve(cls.bridge, cls.events)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.init_script = ui_harness.INIT_SCRIPT
        cls.shots = os.environ.get("POSTECH_UI_SHOTS")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.bridge._events.stop()
        cls.bridge._mcp.shutdown()
        for k, v in cls.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls.isolation.__exit__(None, None, None)
        cls.hooks.__exit__(None, None, None)

    def page(self, p, width=1366, height=900, dark=True):
        browser = p.chromium.launch(**({"executable_path": CHROMIUM} if CHROMIUM else {}))
        page = browser.new_page(viewport={"width": width, "height": height}, color_scheme="dark" if dark else "light")
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(self.init_script)
        page.goto(self.url)
        page.wait_for_selector("#composer")
        return browser, page, errors

    def shot(self, page, name):
        if self.shots:
            os.makedirs(self.shots, exist_ok=True)
            page.screenshot(path=os.path.join(self.shots, f"{name}.png"))

    def close_modals(self, page):
        while page.locator("#modal-root .modal").count():
            page.keyboard.press("Escape")

    def test_settings_window_mode_guide_card_and_usage_chart(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                self.close_modals(page)
                page.click("#btn-settings")
                card = page.locator(".guide-card")
                card.wait_for()
                self.assertIn("사용법 가이드", card.locator("b").inner_text())
                self.assertGreaterEqual(float(card.locator("b").evaluate("e => parseFloat(getComputedStyle(e).fontSize)")), 18)
                page.wait_for_selector(".usage-chart svg .uc-in")
                self.assertEqual(page.locator(".usage-chart .uc-day").count(), 30)
                self.assertIn("7,400", page.locator(".usage-chart figcaption").inner_text())
                self.shot(page, "settings-top")
                page.locator("#window-mode").scroll_into_view_if_needed()
                self.assertEqual(page.input_value("#window-mode"), "fullscreen")  # 1.19.1 기본값
                page.select_option("#window-mode", "maximized")
                self.shot(page, "settings-window-mode")
                page.click(".modal-foot button:has-text('저장')")
                page.wait_for_selector("#modal-root .modal", state="detached")
                self.assertEqual(self.bridge._config["window_mode"], "maximized")
                self.assertEqual(self.bridge.get_state()["config"]["window_mode"], "maximized")
                # 가이드: 큰 제목과 목차, 목차를 누르면 그 항목이 펼쳐진다
                page.click("#btn-settings")
                page.click(".guide-card")
                page.wait_for_selector(".guide-hero h2")
                self.assertEqual(page.locator(".guide-hero h2").inner_text(), "사용법 가이드")
                page.locator(".guide-toc-item").nth(3).click()
                self.assertTrue(page.locator(".guide-section").nth(3).evaluate("e => e.open"))
                self.shot(page, "guide")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_links_follow_the_dark_theme_and_remember_visits(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                self.close_modals(page)
                page.evaluate("""() => {
                  const box = document.createElement('div'); box.className = 'md'; box.id = 'link-test';
                  box.innerHTML = '<a href="https://example.com/a" target="_blank">a</a> <a href="https://example.com/b">b</a>';
                  document.body.append(box);  // #messages는 첫 대화를 여는 동안 다시 그려진다
                  box.querySelectorAll('a').forEach((a) => a.addEventListener('click', (e) => e.preventDefault()));
                }""")
                color = lambda sel: page.locator(sel).evaluate("e => getComputedStyle(e).color")  # noqa: E731
                self.assertEqual(color("#link-test a >> nth=0"), "rgb(168, 209, 255)")  # 1.19.1 더 밝게
                page.click("#link-test a >> nth=0")
                self.assertEqual(page.locator("#link-test a >> nth=0").get_attribute("data-visited"), "")
                self.assertEqual(color("#link-test a >> nth=0"), "rgb(217, 194, 255)")
                self.assertEqual(color("#link-test a >> nth=1"), "rgb(168, 209, 255)")
                # 다시 열어도(같은 주소가 다시 그려져도) 다녀온 링크로 보인다
                page.reload()
                page.wait_for_selector("#composer")
                page.evaluate("""() => { const a = document.createElement('a'); a.id = 'again'; a.href = 'https://example.com/a';
                  a.textContent = 'again'; document.body.append(a); }""")
                page.wait_for_function("document.querySelector('#again').hasAttribute('data-visited')")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_plms_dialog_saves_the_account_to_settings(self):
        import plms
        from playwright.sync_api import sync_playwright

        plms.clear_credentials()
        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                self.close_modals(page)
                page.evaluate("document.querySelector('#btn-plms').hidden = false")
                page.click("#btn-plms")
                page.wait_for_selector(".plms-save")
                self.assertFalse(page.is_visible(".plms-save-form"))
                page.click(".plms-save button:has-text('계정을 설정에 저장해 두기')")
                page.fill(".plms-save-form input[type=text]", "student")
                page.click(".plms-save-form button[type=submit]")
                page.wait_for_selector(".plms-save-form small[role=status]:has-text('모두 입력')")
                page.fill(".plms-save-form input[type=password]", "pw-1234")
                self.shot(page, "plms-save")
                page.click(".plms-save-form button[type=submit]")
                page.wait_for_selector("#modal-root .modal:has-text('저장된 계정(student)')")
                self.assertEqual(page.locator(".plms-save").count(), 0)
                self.assertEqual(plms.saved_username(), "student")
                self.assertTrue(self.bridge._config.get("plms_enabled"))
                self.assertEqual(self.bridge.get_state()["config"]["plms_username"], "student")
                self.assertEqual(errors, [])
            finally:
                browser.close()
                plms.clear_credentials()

    def test_tool_pages_keep_the_sidebar_and_native_browser_toolbar_hides_duplicates(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                self.close_modals(page)
                page.click("#btn-plugins")
                page.wait_for_selector("#tool-view", state="visible")
                self.assertTrue(page.is_visible("#sidebar"))
                self.assertFalse(page.evaluate("document.querySelector('#app').classList.contains('collapsed')"))
                page.click("#btn-new")
                # 1.19.1: 네이티브 막대가 있으면 채팅 위 주소 줄(주소 칸·이동·기본 브라우저로 열기·닫기)을 통째로 뺀다
                page.evaluate("browserEvent({ visible: true, url: 'https://example.com/', mode: 'native', toolbar: true })")
                page.wait_for_selector("#browser-bar", state="visible")
                for sel in ("#browser-address", "#browser-back", "#browser-external", "#browser-close"):
                    self.assertFalse(page.is_visible(sel), sel)
                self.assertTrue(page.is_visible("#browser-ask-page"))  # AI에게 묻기 버튼은 채팅 위에 남는다
                page.evaluate("browserEvent({ toolbar: false })")
                for sel in ("#browser-address", "#browser-back", "#browser-external", "#browser-close"):
                    self.assertTrue(page.is_visible(sel), sel)
                self.assertEqual(errors, [])
            finally:
                browser.close()


    def test_credit_bar_skill_korean_and_button_links(self):
        """1.19.1: 크레딧 막대, 플러그인 스킬의 한국어 설명, 버튼 모양 링크 색."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                self.close_modals(page)
                # 크레딧 막대: 사용량/한도 비율로 채우고 90%부터 경고 색
                page.evaluate("S.credit = { usage: 300, limit: 1000, interval: 'WEEKLY' }; S.creditAt = Date.now()")
                page.evaluate("showUsage()")
                bar = page.locator("#modal-root [data-credit-bar]")
                bar.wait_for()
                self.assertEqual(bar.get_attribute("aria-valuenow"), "30")
                self.assertIn("30%", page.locator("#modal-root .credit-fill").get_attribute("style"))
                page.evaluate("window.onBackendEvent({ type: 'credit', credit: { usage: 950, limit: 1000, interval: 'WEEKLY' } })")
                self.assertEqual(bar.get_attribute("aria-valuenow"), "95")
                self.assertIn("danger", bar.get_attribute("class"))
                self.assertIn("95%", page.locator("#modal-root [data-credit]").inner_text())
                self.shot(page, "credit-bar")
                self.close_modals(page)
                # 플러그인 스킬: 스킬 목록과 / 메뉴에 한국어 설명, 영문 원문은 접어 둔다
                page.evaluate("""S.skills = [{ name: 'productivity:start', description: 'Initialize the productivity system',
                  description_ko: '생산성 시스템을 설정합니다.', source: '플러그인 productivity', path: '' },
                  { name: 'summarize', description: '긴 글을 요약', description_ko: '', source: '내장', path: '' }]""")
                page.click("#btn-skills")
                item = page.locator(".skill-item:has-text('productivity:start')")
                item.wait_for()
                self.assertIn("생산성 시스템을 설정합니다.", item.inner_text())
                self.assertFalse(item.locator(".plugin-orig p").is_visible())
                self.assertEqual(page.locator(".skill-item:has-text('summarize') .plugin-orig").count(), 0)
                self.shot(page, "skills-korean")
                self.close_modals(page)
                self.assertEqual(page.evaluate("slashItems('productivity')[0].description"), "생산성 시스템을 설정합니다.")
                # 버튼 모양 링크는 브라우저 기본 파랑이 아니라 밝은 링크 색, 밑줄 없음
                page.evaluate("""() => { const a = document.createElement('a'); a.className = 'btn'; a.id = 'btn-link';
                  a.href = 'https://example.com/home'; a.textContent = '홈페이지'; document.body.append(a); }""")
                style = page.locator("#btn-link").evaluate("e => [getComputedStyle(e).color, getComputedStyle(e).textDecorationLine]")
                self.assertEqual(style, ["rgb(168, 209, 255)", "none"])
                self.assertEqual(errors, [])
            finally:
                browser.close()

if __name__ == "__main__":
    unittest.main()
