# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""Adaptive AI(1.17) 화면 시험: 실제 Bridge에 붙은 web/ 화면을 Chromium으로 열어 본다.

설정 → AI 실행 정책 창(로컬 AI 연결·모델 목록·기능·라이선스·받기 전 확인) → 켜고 저장 → 대화 모델 목록의 '자동'·'로컬' →
로컬로 답한 메시지의 라우팅 표시와 펼친 이유 → 승격(로컬 임시 답이 접혀 남음) → 사용량·진단의 Adaptive 통계 → 휴대폰 폭.
로컬 실행기는 tests/fake_ollama.py, Cloud는 agent.ask를 바꿔 끼운다. Playwright가 없으면 건너뛴다.
"""
import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)
KO = "회의에서는 예산을 확정했고, 다음 주까지 발표 자료를 준비하기로 했습니다. 담당자는 김 연구원입니다."


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright가 없어 화면 점검을 건너뜁니다")
class AdaptiveUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import agent
        import ui_harness
        from fake_ollama import FakeOllama
        from support import isolated_app_dir, preserved_hooks

        cls.saved_env = {k: os.environ.get(k) for k in ("APPDATA", "POSTECH_CHAT_SECRETS", "POSTECH_GENAI_API_KEY")}
        os.environ.pop("POSTECH_GENAI_API_KEY", None)
        cls.hooks = preserved_hooks()
        cls.hooks.__enter__()
        cls.isolation = isolated_app_dir()
        data_dir = cls.isolation.__enter__()
        cls.fake = FakeOllama()
        cls.bridge, cls.events = ui_harness.make_bridge(data_dir)
        cls.bridge.save_settings({"api_key": "test-key"})
        cls.cloud = patch.object(agent, "ask", side_effect=lambda key, prompt, settings=None, **kw: "Cloud가 다시 쓴 한국어 답변입니다.")
        cls.cloud.start()
        cls.server = ui_harness.serve(cls.bridge, cls.events)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        cls.init_script = ui_harness.INIT_SCRIPT
        cls.shots = os.environ.get("POSTECH_UI_SHOTS")

    @classmethod
    def tearDownClass(cls):
        import api

        cls.cloud.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.fake.close()
        cls.bridge._code_shutdown()
        cls.bridge._events.stop()
        cls.bridge._mcp.shutdown()
        api.cloud_guard = None
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
        page.wait_for_selector("#btn-settings")
        return browser, page, errors

    def send(self, page, text):
        page.fill("#input", text)
        page.keyboard.press("Enter")
        page.wait_for_function("() => !S.busy && document.querySelectorAll('.msg.assistant').length > 0", timeout=30000)

    def test_policy_window_routing_badge_and_stats(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                # 설정 창의 칸 → AI 실행 정책 창(꺼진 상태)
                page.click("#btn-settings")
                field = page.locator(".modal .field:has(label:has-text('AI 실행 정책'))")
                field.wait_for()
                self.assertIn("꺼짐", field.inner_text())
                field.locator("button:has-text('열기')").click()
                dlg = page.locator(".modal:has(h2:has-text('AI 실행 정책'))")
                dlg.wait_for()
                self.assertIn("연결 안 됨", dlg.locator(".adaptive-health").inner_text())  # 기본 주소에는 Ollama가 없다
                # 가짜 Ollama 주소로 연결 시험(저장 전)
                dlg.locator("input[type=url]").fill(self.fake.url)
                dlg.locator("button:has-text('연결 시험')").click()
                page.wait_for_selector(".adaptive-health.ok:has-text('연결됨')")
                # 원격·메타데이터 주소는 저장하지 못한다
                dlg.locator("input[type=url]").fill("http://169.254.169.254")
                dlg.locator(".modal-foot button:has-text('저장')").click()
                page.wait_for_selector("#toast:has-text('연결하지 않습니다')")
                dlg.locator("input[type=url]").fill(self.fake.url)
                dlg.locator(".modal-foot button:has-text('저장')").click()  # 일단 주소만 저장 → 다시 열면 모델 목록
                page.wait_for_selector("#toast:has-text('AI 실행 정책을 저장했습니다')")
                page.click("#btn-settings") if not page.locator(".modal:has(h2:has-text('설정'))").count() else None
                page.locator(".modal .field:has(label:has-text('AI 실행 정책')) button:has-text('열기')").last.click()
                dlg = page.locator(".modal:has(h2:has-text('AI 실행 정책'))")
                dlg.wait_for()
                page.wait_for_selector(".adaptive-models td:has-text('qwen2.5:7b')")
                # 기능·라이선스는 실행기가 알려 준 대로
                row = dlg.locator(".adaptive-models tr:has(td:has-text('llava:7b'))")
                row.locator("button:has-text('기능·라이선스')").click()
                page.wait_for_selector(".adaptive-out:has-text('이미지')")
                # 켜기 + Economy + 기본 로컬 모델
                dlg.locator("label:has-text('자동 모델 선택 켜기') input").check()
                dlg.locator("label.adaptive-policy:has-text('Economy') input").check()
                dlg.locator("select").first.select_option("qwen2.5:7b")
                self.shot(page, "adaptive-policy")
                dlg.locator(".modal-foot button:has-text('저장')").click()
                page.wait_for_selector("#toast:has-text('AI 실행 정책을 저장했습니다')")
                while page.locator("#modal-root .modal").count():  # 2.0: Escape는 맨 위 창 하나만 닫는다
                    page.keyboard.press("Escape")  # 설정 창(그리고 그 사이 뜬 창) 닫기
                # 새 대화는 '자동', 목록에 로컬 모델
                page.click("#btn-new") if page.locator("#btn-new").count() else page.keyboard.press("Control+Shift+O")
                page.wait_for_function("() => [...document.querySelectorAll('#thread-model option')].some(o => o.value === 'local:qwen2.5:7b')")
                # 켜기 전에 만든 빈 대화는 고른 모델 그대로다: 목록에서 '자동'을 고른다(새로 만든 대화는 '자동'으로 시작 — 통합 시험)
                page.select_option("#thread-model", "auto")
                page.wait_for_function("() => S.thread && S.thread.model === 'auto'")
                # 로컬 답 → 라우팅 표시
                self.fake.replies.append(KO)
                self.send(page, "이 회의록을 세 줄로 요약해 줘")
                badge = page.locator(".msg.assistant .route-badge").last
                badge.wait_for()
                self.assertEqual(badge.inner_text(), "Local · 요약")
                badge.click()
                detail = page.locator(".route-detail").last
                self.assertIn("로컬(이 PC)", detail.inner_text())
                self.assertIn("Cloud API 호출", detail.inner_text())
                self.assertIn("없음", detail.inner_text())
                self.shot(page, "adaptive-badge")
                # 승격: 로컬 답이 검증 실패 → Cloud 답, 임시 답은 접혀 남는다
                self.fake.replies.append("English only answer that should fail the Korean language check for sure.")
                self.send(page, "이 회의록을 다시 요약해 줘")
                page.wait_for_function("() => document.querySelectorAll('.msg.assistant .route-badge').length >= 2", timeout=30000)
                # 로컬 임시 답의 배지('Local · 요약')가 먼저 그려졌다가 승격되면 바뀐다: 마지막 글자를 기다린다
                page.wait_for_function("() => [...document.querySelectorAll('.msg.assistant .route-badge')].pop()"
                                       "?.innerText.includes('Cloud')", timeout=30000)
                badge = page.locator(".msg.assistant .route-badge").last
                self.assertEqual(badge.inner_text(), "Local → Cloud · 요약")
                badge.click()
                self.assertIn("검증에 실패한 로컬 임시 답 보기", page.locator(".route-detail").last.inner_text())
                self.assertIn("Cloud가 다시 쓴", page.locator(".msg.assistant").last.inner_text())
                # 사용량·진단의 Adaptive 통계
                page.evaluate("showHub('diagnostics')")
                page.wait_for_selector(".hub-group h3:has-text('Adaptive AI')")
                sec = page.locator(".hub-group:has(h3:has-text('자동 모델 선택'))")
                self.assertIn("로컬로 끝냄", sec.inner_text())
                self.assertIn("Cloud API 청구 비용만 0", sec.inner_text())
                self.shot(page, "adaptive-stats")
                self.assertEqual([e for e in errors if "favicon" not in e], [])
            finally:
                browser.close()

    def test_developer_mode_prices_and_breakeven(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p)
            try:
                # 설정 → 개발자 모드 켜기
                page.click("#btn-settings")
                page.locator(".modal label:has-text('원자료 보기') input").check()
                page.locator(".modal-foot button:has-text('저장')").last.click()
                page.wait_for_function("() => S.config.developer_mode === true")
                # AI 실행 정책: 3단계는 켜야 쓴다(끄면 경량 모델 칸이 잠김), 단가로 손익분기 계산
                page.evaluate("showAdaptive()")
                dlg = page.locator(".modal:has(h2:has-text('AI 실행 정책'))")
                dlg.wait_for()
                tier_box = dlg.locator("label:has-text('3단계 켜기') input")
                self.assertFalse(tier_box.is_checked())
                light = dlg.locator(".field:has(label:has-text('경량 Cloud 모델')) select")
                self.assertTrue(light.is_disabled())
                tier_box.check()
                self.assertFalse(light.is_disabled())
                rows = dlg.locator(".adaptive-prices tr")
                for row, (inp, out) in ((1, ("1", "5")), (2, ("5", "25"))):
                    cells = rows.nth(row).locator("input")
                    cells.nth(0).fill(inp)
                    cells.nth(1).fill(out)
                dlg.locator("button:has-text('손익분기 계산')").click()
                page.wait_for_selector(".adaptive-econ:has-text('단가 비율 r = 0.2')")
                self.assertIn("손익분기 r*", dlg.locator(".adaptive-econ").inner_text())
                self.shot(page, "adaptive-breakeven")
                page.keyboard.press("Escape")
                # 라우팅 표시를 펼치면 호출마다 실제 토큰·손익분기·원본 JSON(개발자 모드)
                text = page.evaluate("""() => {
                  const n = routeBadge({ provider: 'light', model: 'm', label: 'Light · 요약', status: 'verified', reason_code: 'light',
                    attempts: [{ provider: 'light', model: 'm', ok: true, ms: 12, usage: { input_tokens: 1200, output_tokens: 80,
                    cache_read_input_tokens: 1000 } }], economics: { known: true, ratio: 0.2, breakeven_consult: 0.28,
                    breakeven_light: 0.81, costs: { frontier: 0.02, light: 0.006, consult: 0.017 }, best: 'light', p_escalate: 0.15 } });
                  document.body.append(n); n.querySelector('button').click(); return n.innerText; }""")
                self.assertIn("캐시 읽기 1000", text)
                self.assertIn("단가 비율 r = 0.2", text)
                self.assertIn("원본 JSON", text)
                # 사용량·진단의 개발자 데이터
                page.evaluate("showHub('diagnostics')")
                sec = page.locator(".hub-group:has(h3:has-text('개발자 데이터'))")
                sec.wait_for()
                sec.locator("button:has-text('개발자 데이터 불러오기')").click()
                sec.locator("button:has-text('JSON 복사')").wait_for()
                self.assertIn("요청 길이(토큰)", sec.inner_text())
                self.assertEqual([e for e in errors if "favicon" not in e], [])
            finally:
                self.bridge.save_settings({"developer_mode": False})
                browser.close()

    def test_phone_width(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser, page, errors = self.open(p, 390, 800)
            try:
                page.evaluate("showAdaptive()")
                dlg = page.locator(".modal:has(h2:has-text('AI 실행 정책'))")
                dlg.wait_for()
                width = page.evaluate("document.documentElement.scrollWidth")
                self.assertLessEqual(width, 392)  # 가로로 넘치지 않는다
                self.shot(page, "adaptive-phone")
                self.assertEqual([e for e in errors if "favicon" not in e], [])
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
