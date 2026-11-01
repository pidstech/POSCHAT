# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.0 화면 시험: 답이 끝나면 대화별 모델 선택이 다시 켜지고, 겹친 창은 Escape로 맨 위 창만 닫히고,
연결·도구 창에서 탭을 빨리 옮겨도 늦게 끝난 이전 탭 내용이 보이지 않고, 대화 이름을 고치는 중에
목록을 다시 그려도 입력 칸이 남고, 코드 작업 폴더를 바꾼 뒤 남긴 탭은 새 폴더에 저장하지 않는다.

Playwright가 없으면 건너뛴다.
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright가 없어 화면 점검을 건너뜁니다")
class Release20UiTests(unittest.TestCase):
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
        for i in range(3):
            t = storage.new_thread()
            t["title"] = f"대화 {i + 1}"
            storage.save_thread(t)
        cls.ws1 = Path(data_dir) / "proj-a"
        cls.ws2 = Path(data_dir) / "proj-b"
        for ws, text in ((cls.ws1, "A = 1\n"), (cls.ws2, "B = 2\n")):
            ws.mkdir()
            (ws / "same.py").write_text(text, encoding="utf-8")
        cls.bridge._config["workspace"] = str(cls.ws1)
        cls.server = ui_harness.serve(cls.bridge, cls.events)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.init_script = ui_harness.INIT_SCRIPT

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.bridge._code_shutdown()
        cls.bridge._events.stop()
        cls.bridge._mcp.shutdown()
        for k, v in cls.saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls.isolation.__exit__(None, None, None)
        cls.hooks.__exit__(None, None, None)

    def page(self, p):
        browser = p.chromium.launch(**({"executable_path": CHROMIUM} if CHROMIUM else {}))
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.add_init_script(self.init_script)
        page.goto(self.url)
        page.wait_for_selector("#composer")
        page.wait_for_function("typeof S !== 'undefined' && S.thread")
        while page.locator("#modal-root .modal").count():
            page.keyboard.press("Escape")
        return browser, page, errors

    def test_thread_model_reenabled_when_reply_is_done(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                page.wait_for_selector("#thread-model-picker:not([hidden])")
                page.evaluate("S.runningThreads.add(S.currentId); S.busy = true; S.busyThread = S.currentId; renderThreadModel()")
                self.assertTrue(page.locator("#thread-model").is_disabled())
                page.evaluate("window.onBackendEvent({ type: 'done', thread_id: S.currentId })")
                page.wait_for_function("!document.querySelector('#thread-model').disabled")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_escape_closes_only_the_topmost_modal(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                page.click("#btn-settings")
                page.wait_for_selector("#modal-root .modal input")
                page.evaluate("window._typed = document.querySelector('#modal-root .modal input:not([type=hidden])');"
                              "window._typed.value = '입력한 값'")
                page.evaluate("modal({ title: '승인', body: h('p', {}, '위 창') })")
                self.assertEqual(page.locator("#modal-root .modal").count(), 2)
                page.keyboard.press("Escape")
                self.assertEqual(page.locator("#modal-root .modal").count(), 1)
                self.assertNotIn("승인", page.inner_text("#modal-root .modal h2"))
                self.assertTrue(page.evaluate("window._typed.isConnected && window._typed.value === '입력한 값'"))
                page.keyboard.press("Escape")
                self.assertEqual(page.locator("#modal-root .modal").count(), 0)
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_hub_tab_switch_ignores_late_render(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                page.evaluate("""() => {
                  HUB_TABS[0].render = async (panel) => { await new Promise((r) => setTimeout(r, 600));
                    fill(panel, h('p', { id: 'hub-slow' }, '느린 탭')); };
                  HUB_TABS[1].render = (panel) => fill(panel, h('p', { id: 'hub-fast' }, '빠른 탭'));
                  showHub(HUB_TABS[0].id);
                }""")
                page.locator(".hub-tab").nth(1).click()
                page.wait_for_selector("#hub-fast")
                page.wait_for_timeout(900)
                self.assertEqual(page.locator("#hub-slow").count(), 0)
                self.assertEqual(page.locator(".hub-panel #hub-fast").count(), 1)
                self.assertEqual(page.locator("#modal-root .hub-panel").count(), 1)
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_rename_survives_sidebar_refresh(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                item = page.locator(".thread:has-text('대화 2')")
                item.hover()
                item.locator("button[title='이름 변경']").click()
                inp = page.locator("#thread-list input.thread-rename")
                inp.wait_for()
                inp.fill("새 이름")
                page.evaluate("refreshThreads()")  # 다른 대화의 답이 끝날 때처럼
                page.wait_for_timeout(300)
                self.assertEqual(inp.count(), 1)
                self.assertTrue(inp.evaluate("e => document.activeElement === e"))
                page.keyboard.press("Enter")
                page.wait_for_selector(".thread:has-text('새 이름')")
                self.assertEqual(page.locator("#thread-list input").count(), 0)
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_kept_tab_does_not_save_into_new_workspace(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.page(p)
            try:
                self.bridge._config["workspace"] = str(self.ws1)
                page.click("#btn-code")
                page.wait_for_selector(".code-row[data-path='same.py']")
                page.click(".code-row[data-path='same.py']")
                page.wait_for_selector(".code-tabpane:not([hidden]) .cm-content")
                page.click(".code-tabpane:not([hidden]) .cm-line >> nth=0")
                page.keyboard.press("End")
                page.keyboard.type("  # 고침")
                page.wait_for_selector(".code-tab.active.dirty")
                # 다른 곳에서 작업 폴더를 바꾼다
                self.bridge._config["workspace"] = str(self.ws2)
                page.evaluate("codeRefreshState()")
                page.wait_for_function("CODE.state.workspace.path.endsWith('proj-b')")
                self.assertIn("다른 작업 폴더", page.inner_text("#code-notice"))
                page.click(".code-tabpane:not([hidden]) .cm-line >> nth=0")
                page.keyboard.press("Control+s")
                page.wait_for_selector("#toast:not([hidden]):has-text('그 폴더로 돌아가세요')")
                self.assertEqual((self.ws2 / "same.py").read_text(encoding="utf-8"), "B = 2\n")
                self.assertEqual((self.ws1 / "same.py").read_text(encoding="utf-8"), "A = 1\n")
                self.assertTrue(page.locator(".code-tab.active.dirty").count())
                # 창으로 돌아와도 새 폴더의 같은 파일로 다시 열지 않는다
                page.evaluate("codeCheckDisk()")
                page.wait_for_timeout(300)
                self.assertIn("고침", page.evaluate("CODE.tabs.find((t) => t.id === CODE.active).editor.getText()"))
                # 원래 폴더로 돌아가면 저장된다
                self.bridge._config["workspace"] = str(self.ws1)
                page.evaluate("codeRefreshState()")
                page.wait_for_function("CODE.state.workspace.path.endsWith('proj-a')")
                page.click(".code-tabpane:not([hidden]) .cm-line >> nth=0")
                page.keyboard.press("Control+s")
                page.wait_for_selector(".code-tab.active:not(.dirty)")
                self.assertEqual((self.ws1 / "same.py").read_text(encoding="utf-8"), "A = 1  # 고침\n")
                self.assertEqual((self.ws2 / "same.py").read_text(encoding="utf-8"), "B = 2\n")
                self.assertEqual(errors, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
