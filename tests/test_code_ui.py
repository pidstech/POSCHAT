# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""POSCHAT Code(1.15) 화면 시험: 실제 Bridge에 붙은 web/ 화면을 Chromium(Playwright)으로 열어 코드 화면을 조작한다.

열기 → 파일 트리 → 파일 선택 → 편집 → 저장 → 선택한 코드 묻기 → 에이전트 변경 검토(덩어리 받아들이기·거부) →
Git 변경 표시·스테이지 → 명령 실행(승인) → 브라우저·논문·코드 전환(저장하지 않은 내용 유지) → 휴대폰 폭.
Playwright가 없으면 건너뛴다. 스크린숏은 POSTECH_UI_SHOTS 폴더가 주어지면 거기에 남긴다.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
BASE = "".join(f"value_{i} = {i}\n" for i in range(1, 31))


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright가 없어 화면 점검을 건너뜁니다")
class CodeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ui_harness
        from support import isolated_app_dir, preserved_hooks

        cls.saved_env = {k: os.environ.get(k) for k in ("APPDATA", "POSTECH_CHAT_SECRETS")}
        cls.hooks = preserved_hooks()
        cls.hooks.__enter__()
        cls.isolation = isolated_app_dir()
        data_dir = cls.isolation.__enter__()
        cls.bridge, cls.events = ui_harness.make_bridge(data_dir)
        cls.bridge.save_settings({"api_key": "test-key"})
        cls.ws = Path(data_dir) / "proj 한글"
        (cls.ws / "rtl").mkdir(parents=True)
        (cls.ws / "sim").mkdir()
        (cls.ws / "rtl" / "counter.sv").write_text(
            "module counter #(parameter W = 8) (\n  input logic clk, rst_n,\n  output logic [W-1:0] q\n);\n"
            "  always_ff @(posedge clk or negedge rst_n) begin\n    if (!rst_n) q <= '0;\n    else q <= q + 1'b1;\n  end\n"
            "endmodule\n", encoding="utf-8")
        (cls.ws / "sim" / "model.py").write_bytes(BASE.replace("\n", "\r\n").encode())
        (cls.ws / "main.c").write_text("int main(void) { return 0; }\n")
        cls.git = shutil.which("git") is not None
        if cls.git:
            for c in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"],
                      ["add", "."], ["commit", "-qm", "init"]):
                subprocess.run(["git", *c], cwd=cls.ws, check=True, capture_output=True)
        cls.bridge._config["workspace"] = str(cls.ws)
        cls.server = ui_harness.serve(cls.bridge, cls.events)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.init_script = ui_harness.INIT_SCRIPT
        cls.shots = os.environ.get("POSTECH_UI_SHOTS")

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

    def shot(self, page, name):
        if self.shots:
            os.makedirs(self.shots, exist_ok=True)
            page.screenshot(path=os.path.join(self.shots, f"{name}.png"), full_page=False)

    def open(self, p, width=1400, height=900):
        browser = p.chromium.launch(**({"executable_path": CHROMIUM} if CHROMIUM else {}))
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.add_init_script(self.init_script)
        page.goto(self.url)
        page.wait_for_selector("#btn-code")
        return browser, page, errors

    def open_code(self, page):
        page.click("#btn-code")
        page.wait_for_selector("#code-pane:not([hidden])")
        page.wait_for_selector(".code-row[data-path='rtl']")

    def open_file(self, page, folder, path):
        if not page.is_visible(f".code-row[data-path='{path}']"):
            page.click(f".code-row[data-path='{folder}']")
        page.click(f".code-row[data-path='{path}']")
        page.wait_for_selector(f".code-tab.active:has-text('{path.split('/')[-1]}')")
        page.wait_for_selector(".code-tabpane:not([hidden]) .cm-content")

    def test_open_edit_save_and_ask(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                self.open_code(page)
                self.assertEqual(page.get_attribute("#btn-code", "aria-pressed"), "true")
                self.assertTrue(page.is_hidden("#main"))  # 1.17.2: 채팅 옆이 아니라 하나의 화면으로 열린다
                # SystemVerilog: 강조(키워드 토큰)와 언어 표시
                self.open_file(page, "rtl", "rtl/counter.sv")
                self.assertIn("SystemVerilog", page.inner_text("#code-statusbar"))
                self.assertGreater(page.locator(".code-tabpane:not([hidden]) .cm-content span").count(), 3)
                self.shot(page, "code-sv")
                # Python(CRLF) 편집 → 저장 → 줄 끝 유지
                self.open_file(page, "sim", "sim/model.py")
                self.assertIn("CRLF", page.inner_text("#code-statusbar"))
                page.click(".code-tabpane:not([hidden]) .cm-line >> nth=0")
                page.keyboard.press("End")
                page.keyboard.type("  # 고침")
                page.wait_for_selector(".code-tab.active.dirty")
                page.keyboard.press("Control+s")
                page.wait_for_selector(".code-tab.active:not(.dirty)")
                raw = (self.ws / "sim" / "model.py").read_bytes()
                self.assertTrue(raw.startswith(b"value_1 = 1  # \xea\xb3\xa0\xec\xb9\xa8\r\n"))
                self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
                # 되돌리기·다시 하기
                page.click(".code-tabpane:not([hidden]) .cm-line >> nth=1")
                page.keyboard.type("X")
                page.click("button[aria-label^='되돌리기']")
                page.wait_for_selector(".code-tab.active:not(.dirty)")
                page.click("button[aria-label^='다시 하기']")
                page.wait_for_selector(".code-tab.active.dirty")
                page.click("button[aria-label^='되돌리기']")
                # 줄 선택 → AI에게 묻기(선택한 부분 · 오류 분석) → 채팅 첨부
                page.evaluate("CODE.tabs.find((t) => t.id === CODE.active).editor.selectLines(3, 5)")
                page.click("#code-ask")
                page.wait_for_selector(".code-menu")
                self.assertIn("3-5줄", page.inner_text(".code-scope"))
                page.click(".code-menu-item[data-preset='bug']")
                page.wait_for_selector("#attach-tray:not([hidden])")
                self.assertIn("model.py 3-5", page.inner_text("#attach-tray"))
                self.assertIn("오류가 날 수 있는 곳", page.input_value("#input"))
                att = self.bridge  # 첨부 내용: 파일·언어·줄·선택한 코드
                import attachments
                item = attachments.info(page.evaluate("S.attach[0].id"))
                text = attachments.text_of(item)
                for want in ("파일: sim/model.py", "언어: Python", "줄: 3-5", "value_3 = 3", "주변 코드"):
                    self.assertIn(want, text)
                del att
                self.shot(page, "code-ask")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_agent_change_review_hunks(self):
        from playwright.sync_api import sync_playwright

        from agent import Agent

        (self.ws / "sim" / "review.py").write_text(BASE)
        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                self.open_code(page)
                page.wait_for_function("typeof CODE !== 'undefined' && CODE.state && CODE.state.workspace.path")
                stop = threading.Event()
                alive = lambda: not stop.is_set()  # noqa: E731
                agent = Agent(api_key="k", workspace=str(self.ws), agent_mode=True, max_steps=1, history_messages=1,
                              on_status=lambda t: None, on_tool=lambda s, d: None, confirm=lambda *a: True,
                              cancelled=lambda: not alive(),
                              review=lambda *a: self.bridge._code_review_edit("t", alive, str(self.ws), *a))
                new = BASE.replace("value_2 = 2", "value_2 = 200").replace("value_25 = 25", "value_25 = 2500")
                box = {}
                t = threading.Thread(target=lambda: box.setdefault("obs", agent._tool_write("sim/review.py", new, "값 조정")))
                t.start()
                page.wait_for_selector(".code-review .code-hunk", timeout=10000)
                self.assertEqual(page.locator(".code-hunk").count(), 2)
                self.assertIn("이유: 값 조정", page.inner_text(".code-review-head"))
                self.assertIn("변경 검토 (1)", page.inner_text("#code-side-review"))   # 1.18: 왼쪽 패널의 탭
                self.assertEqual((self.ws / "sim" / "review.py").read_text(), BASE)  # 승인 전에는 그대로
                self.shot(page, "code-review")
                page.uncheck(".code-hunk[data-hunk='0'] input[type=checkbox]")
                self.assertIn("1/2개", page.inner_text(".code-review-count"))
                page.click("#code-apply")
                t.join(10)
                self.assertIn("일부만 적용", box["obs"])
                text = (self.ws / "sim" / "review.py").read_text()
                self.assertIn("value_25 = 2500", text)
                self.assertIn("value_2 = 2\n", text)
                page.wait_for_selector(".code-review-head .st-partial")
                # 두 번째 제안은 모두 거부
                box.clear()
                t = threading.Thread(target=lambda: box.setdefault("obs", agent._tool_write(
                    "sim/review.py", text.replace("value_1 = 1", "value_1 = -1"))))
                t.start()
                page.wait_for_selector(".code-review-head .st-pending", timeout=10000)
                page.click("#code-reject")
                t.join(10)
                self.assertIn("거부", box["obs"])
                self.assertIn("value_1 = 1\n", (self.ws / "sim" / "review.py").read_text())
                page.click("#code-side-review")
                self.assertEqual(page.locator("#code-side-body .code-item").count(), 2)
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_git_panel_and_terminal(self):
        """1.18: Git은 왼쪽 패널의 탭, 아래 패널은 진짜 터미널(셸). 입력·출력·AI에게 묻기·새 터미널·닫기·끝남."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                if self.git:
                    (self.ws / "main.c").write_text("int main(void) { return 1; }\n")
                self.open_code(page)
                if self.git:
                    page.wait_for_selector(".code-row[data-path='main.c'] .code-git-mark")
                    page.click("#code-side-git")
                    page.wait_for_selector("#code-side-body .code-git-row:has-text('main.c')")
                    page.click(".code-git-file:has-text('main.c')")
                    page.wait_for_selector(".code-tabpane:not([hidden]) pre.diff .add")
                    self.assertIn("return 1", page.inner_text(".code-tabpane:not([hidden]) pre.diff"))
                    page.check(".code-git-row:has-text('main.c') input[type=checkbox]")
                    page.click("button:has-text('고른 파일 스테이지')")
                    page.wait_for_selector("h4:has-text('스테이지됨')")
                    self.shot(page, "code-git")
                    page.click("#code-side-files")
                    page.wait_for_selector("#code-tree")
                # 아래 패널: 코드 화면을 열면 터미널이 작업 폴더에서 바로 열린다(승인 창 없음 — 사용자가 직접 치는 셸)
                page.wait_for_selector(".code-term:not([hidden]) .xterm", timeout=15000)
                self.assertEqual(page.locator(".code-ttab").count(), 1)
                page.click(".code-term:not([hidden]) .xterm")
                page.keyboard.type('echo "답=$((6*7))"; pwd')
                page.keyboard.press("Enter")
                screen = "() => TERM.sessions.find((s) => s.id === TERM.active).term.buffer.active"
                text = f"() => {{ const b = ({screen})(); let t = ''; for (let i = 0; i < b.length; i++) t += b.getLine(i).translateToString(true) + '\\n'; return t; }}"
                page.wait_for_function(f"({text})().includes('답=42')", timeout=15000)
                self.assertIn(str(self.ws), page.evaluate(text))      # 작업 폴더에서 시작
                self.assertEqual(page.locator(".modal").count(), 0)
                self.shot(page, "code-terminal")
                # 새 터미널 → 탭 2개, 닫기 → 1개
                page.click("#code-term-new")
                page.wait_for_function("TERM.sessions.length === 2")
                page.click(".code-ttab.active .code-ttab-close")
                page.wait_for_function("TERM.sessions.length === 1")
                # AI에게 묻기: 끝부분을 채팅에 첨부하고 채팅으로 돌아간다
                page.click("#code-term-ask")
                page.wait_for_selector("#code-pane", state="hidden")
                page.wait_for_selector("#attach-tray:has-text('터미널 출력')")
                self.assertIn("터미널 출력", page.input_value("#input"))
                # 다시 열면 같은 터미널이 그대로 있다. exit로 끝내면 알린다
                page.click("#btn-expand")
                page.click("#btn-code")
                page.wait_for_selector(".code-term:not([hidden]) .xterm")
                self.assertEqual(page.evaluate("TERM.sessions.length"), 1)
                page.click(".code-term:not([hidden]) .xterm")
                page.keyboard.type("exit 3")
                page.keyboard.press("Enter")
                page.wait_for_function(f"({text})().includes('종료 코드 3')", timeout=15000)
                page.wait_for_selector(".code-ttab.dead")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_code_opened_while_the_app_starts_stays_open(self):
        """1.18 회귀: 앱이 시작하는 동안(느린 get_state → 첫 대화 열기) 코드를 열면, 첫 대화가 열린 뒤에도 코드 화면이 닫히지 않아야 한다.
        CI에서 시작이 느리면 test_code_agent_ui가 연 코드 화면이 저절로 닫혔다."""
        import time

        from playwright.sync_api import sync_playwright

        self.bridge.new_thread()   # 시작할 때 열 대화가 있게
        real = self.bridge.get_state

        def slow():
            time.sleep(1.5)
            return real()
        with patch.object(self.bridge, "get_state", slow), sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                page.click("#btn-code")
                page.wait_for_selector("#code-pane:not([hidden])")
                page.wait_for_function("() => typeof S !== 'undefined' && !!S.thread", timeout=10000)   # 첫 대화가 열렸다
                page.wait_for_timeout(300)
                self.assertTrue(page.is_visible("#code-pane"))
                self.assertTrue(page.is_hidden("#main"))
                self.assertEqual(page.locator(".thread.active").count(), 0)
                page.click("#code-sidebar-open")
                page.click("#btn-new")                                            # 사용자가 고르면 채팅으로 간다
                page.wait_for_selector("#code-pane", state="hidden")
                self.assertEqual(errors, [])
            finally:
                browser.close()

    def test_switching_right_panes_keeps_unsaved_code(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                self.open_code(page)
                self.open_file(page, "rtl", "rtl/counter.sv")
                page.click(".code-tabpane:not([hidden]) .cm-line >> nth=0")
                page.keyboard.type("// 저장 안 함 ")
                page.wait_for_selector(".code-tab.active.dirty")
                page.click("#code-sidebar-open")
                page.click("#btn-paper")
                page.wait_for_selector("#paper-pane:not([hidden])")
                self.assertTrue(page.is_hidden("#code-pane"))
                self.assertEqual(page.get_attribute("#btn-code", "aria-pressed"), "false")
                page.click("#btn-expand")
                page.click("#btn-code")
                page.wait_for_selector("#code-pane:not([hidden])")
                self.assertTrue(page.is_hidden("#paper-pane"))
                self.assertIn("// 저장 안 함", page.inner_text(".code-tabpane:not([hidden]) .cm-content"))
                self.assertIn("dirty", page.get_attribute(".code-tab.active", "class"))
                # 1.17.2: 코드는 하나의 화면(전체) — 채팅과 나누어 띄우지 않고, 나누는 막대·크게 보기 단추도 없다
                self.assertTrue(page.is_hidden("#main"))
                self.assertEqual(page.locator("#code-full, #code-resizer").count(), 0)
                # 새 채팅으로 가면 코드 화면이 닫히고, 다시 열면 탭·저장하지 않은 내용이 그대로다
                page.click("#code-sidebar-open")
                page.click("#btn-new")
                page.wait_for_selector("#code-pane", state="hidden")
                self.assertTrue(page.is_visible("#main"))
                self.assertEqual(page.get_attribute("#btn-code", "aria-pressed"), "false")
                page.click("#btn-code")
                page.wait_for_selector("#code-pane:not([hidden])")
                self.assertTrue(page.is_hidden("#main"))
                self.assertIn("dirty", page.get_attribute(".code-tab.active", "class"))
                # 저장하지 않은 탭을 닫으면 묻는다
                page.click(".code-tab.active .code-tab-close")
                page.wait_for_selector(".modal:has-text('저장하지 않은 변경')")
                page.click(".modal button:has-text('버리고 닫기')")
                self.assertNotIn("// 저장 안 함", (self.ws / "rtl" / "counter.sv").read_text(encoding="utf-8"))
                self.assertEqual(errors, [])
            finally:
                browser.close()

    @unittest.skipUnless(os.name != "nt" and importlib.util.find_spec("paramiko") is not None, "paramiko·POSIX 필요")
    def test_ssh_remote_folder(self):
        """1.18: 코드 화면 위 'SSH'로 서버(시험용 SSH 서버)에 연결 → 호스트 키 확인 → 암호·OTP → 폴더 고르기 → 원격 파일·터미널 →
        연결이 끊기면 '다시 연결' → 로컬로 되돌리기."""
        import tempfile

        import fake_ssh
        from playwright.sync_api import sync_playwright

        home = Path(tempfile.mkdtemp()) / "server-home"
        (home / "chip").mkdir(parents=True)
        (home / "chip" / "alu.sv").write_text("module alu; endmodule\n", encoding="utf-8")
        # HOME은 바꾸지 않는다(Playwright가 HOME 아래에서 Chromium을 찾는다). '서버'의 홈만 시험 폴더로
        env = patch.dict(os.environ, {"SSH_AUTH_SOCK": ""})
        env.start()
        self.addCleanup(env.stop)
        srv = fake_ssh.FakeSSH(home=str(home), allowed=("keyboard-interactive",)).__enter__()
        self.addCleanup(srv.stop)
        srv.env["HOME"] = str(home)
        target = f"student@127.0.0.1:{srv.port}"
        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                self.open_code(page)
                page.click("#code-ssh")
                page.wait_for_selector("#ssh-target")
                page.fill("#ssh-target", target)
                page.click("#ssh-connect")
                page.wait_for_selector(".modal:has-text('처음 연결하는 서버') code")
                self.assertIn("SHA256:", page.inner_text(".modal:has-text('처음 연결하는 서버') code"))
                self.shot(page, "code-ssh-hostkey")
                page.click(".modal:has-text('처음 연결하는 서버') button:has-text('받아들이고 연결')")
                page.wait_for_selector(".modal:has-text('POSTECH 로그인') #ssh-field-1")
                self.assertEqual(page.get_attribute("#ssh-field-0", "type"), "password")
                page.fill("#ssh-field-0", "pw-1234")
                page.fill("#ssh-field-1", "246810")
                page.keyboard.press("Enter")
                try:
                    page.wait_for_selector("#ssh-browser .ssh-dir:has-text('chip')", timeout=20000)
                except Exception as e:  # CI에서 가끔 폴더 목록이 뜨지 않는다: 그때의 화면 상태를 함께 남긴다
                    state = page.evaluate("""() => ({ target: SSH.target, states: SSH.states, modal: !!SSH.modal,
                      status: document.querySelector('#ssh-status')?.textContent,
                      browser: document.querySelector('#ssh-browser')?.outerHTML.slice(0, 500),
                      toast: document.querySelector('#toast')?.textContent,
                      modals: [...document.querySelectorAll('#modal-root .modal h2')].map((x) => x.textContent) })""")
                    raise AssertionError(f"SSH 폴더 목록이 뜨지 않음: {state}; 화면 오류: {errors}") from e
                self.assertIn("연결됨", page.inner_text("#ssh-status"))
                self.shot(page, "code-ssh-browse")
                page.click("#ssh-browser .ssh-dir:has-text('chip')")
                page.wait_for_function("SSH.folder && SSH.folder.path.endsWith('/chip')")
                page.click("#ssh-open")
                page.wait_for_selector(".code-row[data-path='alu.sv']")
                self.assertIn(f"SSH {target}:", page.inner_text("#code-ws"))
                self.assertEqual(page.locator(".modal").count(), 0)
                self.open_file(page, "", "alu.sv")
                self.assertIn("module alu", page.inner_text(".code-tabpane:not([hidden]) .cm-content"))
                # 터미널: 서버의 그 폴더에서 열린다
                page.wait_for_function("TERM.sessions.some((s) => s.title.includes('ssh '))", timeout=20000)
                tid = page.evaluate("TERM.sessions.find((s) => s.title.includes('ssh ')).id")
                page.evaluate(f"termShow('{tid}', true)")
                page.click(".code-term:not([hidden]) .xterm")
                page.keyboard.type("pwd")
                page.keyboard.press("Enter")
                text = (f"() => {{ const b = TERM.sessions.find((s) => s.id === '{tid}').term.buffer.active; let t = ''; "
                        "for (let i = 0; i < b.length; i++) t += b.getLine(i).translateToString(true) + '\\n'; return t; }")
                page.wait_for_function(f"({text})().includes('/chip')", timeout=15000)
                self.shot(page, "code-ssh-open")
                # 연결이 끊기면 다시 연결 안내
                page.evaluate("api().code_ssh_disconnect()")
                page.wait_for_selector("#code-ssh-reconnect", timeout=15000)
                self.assertIn("offline", page.get_attribute("#code-ws", "class"))
                page.click("#code-ssh-reconnect")
                page.wait_for_selector(".modal:has-text('POSTECH 로그인') #ssh-field-1")   # 호스트 키는 다시 묻지 않는다
                page.fill("#ssh-field-0", "pw-1234")
                page.fill("#ssh-field-1", "246810")
                page.click(".modal:has-text('POSTECH 로그인') button:has-text('확인')")
                page.wait_for_selector(".code-row[data-path='alu.sv']", timeout=20000)
                # 로컬로 되돌리기
                page.click("#code-ssh")
                page.click(".modal button:has-text('로컬 작업 폴더로')")
                page.wait_for_selector(".code-row[data-path='rtl']")
                self.assertNotIn("SSH", page.inner_text("#code-ws"))
                self.assertEqual([e for e in errors if "favicon" not in e], [])
            finally:
                browser.close()
                self.bridge.code_ssh_local()
                self.bridge._ssh_shutdown()

    def test_code_pane_fits_a_phone_screen(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p, width=390, height=800)
            try:
                page.click("#btn-expand")
                self.open_code(page)
                self.assertTrue(page.is_hidden("#main"))  # 휴대폰: 채팅을 덮는다
                self.open_file(page, "rtl", "rtl/counter.sv")
                self.assertTrue(page.is_hidden("#code-files"))  # 파일을 열면 목록은 접힌다
                width = page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(width, 390)
                self.shot(page, "code-phone")
                self.assertEqual(errors, [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
