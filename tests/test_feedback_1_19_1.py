# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""1.19.1 수정(백엔드): 플러그인 스킬의 한국어 설명, 기본 전체 화면, 웹페이지 위 막대의 주소 칸·이동 버튼."""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import isolated_app_dir  # noqa: E402

import browser  # noqa: E402
import plugins  # noqa: E402
import storage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class SkillKoreanTests(unittest.TestCase):
    def test_skill_ko_finds_skills_and_commands(self):
        self.assertRegex(plugins.skill_ko("productivity:start"), "[가-힣]")
        self.assertRegex(plugins.skill_ko("brand-voice:enforce-voice"), "[가-힣]")  # 명령(cmd:)
        self.assertEqual(plugins.skill_ko("productivity:no-such-skill"), "")
        self.assertEqual(plugins.skill_ko("summarize"), "")  # 플러그인 스킬이 아니다


class BridgeTests(unittest.TestCase):
    def setUp(self):
        import os
        import types

        self.iso = isolated_app_dir()
        self.iso.__enter__()
        self.addCleanup(self.iso.__exit__, None, None, None)
        os.environ.setdefault("POSTECH_CHAT_SECRETS", "file")
        sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))
        import main
        self.main = main

    def bridge(self):
        b = self.main.Bridge()
        self.addCleanup(b._mcp.shutdown)
        self.addCleanup(b._events.stop)
        return b

    def test_plugin_skills_carry_korean_descriptions_only_for_plugins(self):
        b = self.bridge()
        fake = {
            "productivity:start": type("S", (), {"name": "productivity:start", "description": "Start", "source": "플러그인 productivity",
                                                 "path": Path("x")})(),
            "summarize": type("S", (), {"name": "summarize", "description": "요약", "source": "내장", "path": Path("y")})(),
        }
        orig = self.main.discover_skills
        self.main.discover_skills = lambda ws: fake
        try:
            items = {s["name"]: s for s in b._skills()}
        finally:
            self.main.discover_skills = orig
        self.assertRegex(items["productivity:start"]["description_ko"], "[가-힣]")
        self.assertEqual(items["productivity:start"]["description"], "Start")  # 모델에 가는 원문은 그대로
        self.assertEqual(items["summarize"]["description_ko"], "")

    def test_old_implicit_normal_is_reset_once(self):
        cfg = storage.load_config()
        cfg["window_mode"] = "normal"  # 1.19.0이 설정 저장 때 함께 적어 둔 값
        storage.save_config(cfg)
        b = self.bridge()
        self.assertEqual(b._window_mode(), "maximized")  # 2.0 기본값
        # 1.19.1에서 '기본 창'을 직접 고르면 다음 실행에도 그대로
        b.save_settings({"window_mode": "normal"})
        self.assertEqual(self.bridge()._window_mode(), "normal")

    def test_maximized_choice_survives_the_reset(self):
        cfg = storage.load_config()
        cfg["window_mode"] = "maximized"
        storage.save_config(cfg)
        self.assertEqual(self.bridge()._window_mode(), "maximized")


class BrowserBarTests(unittest.TestCase):
    def make(self, toolbar=True):
        calls, events = [], []

        class Backend:
            mode = "native"

            def __init__(self):
                self.toolbar = toolbar

            def show(self, ratio):
                calls.append("show")

            def open(self, url):
                calls.append(("open", url))

            def hide(self):
                calls.append("hide")

            def back(self):
                calls.append("back")

            def reload(self):
                calls.append("reload")

            def focus_address(self):
                calls.append("focus")

        b = browser.Browser(lambda _: Backend(), on_event=events.append)
        return b, calls, events

    def test_bar_open_and_nav(self):
        b, calls, events = self.make()
        b.bar_open("example.com")
        self.assertIn(("open", "https://example.com"), calls)
        b.bar_nav("back")
        self.assertIn("back", calls)
        b.bar_nav("bogus")  # 알 수 없는 동작은 조용히 무시한다(작업 스레드에서 예외가 새지 않는다)
        b.bar_open("   ")  # 빈 입력은 아무것도 하지 않는다
        self.assertEqual(sum(1 for c in calls if isinstance(c, tuple)), 1)

    def test_bar_open_reports_errors_as_blocked(self):
        b, calls, events = self.make()
        b.bar_open("javascript:alert(1)")
        self.assertFalse(any(isinstance(c, tuple) for c in calls))
        blocked = [e for e in events if e.get("kind") == "blocked"]
        self.assertEqual(blocked[-1]["reason"], "http·https 주소만 열 수 있습니다.")

    def test_focus_address_only_with_toolbar(self):
        b, calls, _ = self.make(toolbar=True)
        b.show()
        self.assertTrue(b.focus_address())
        self.assertIn("focus", calls)
        b2, calls2, _ = self.make(toolbar=False)
        b2.show()
        self.assertFalse(b2.focus_address())
        self.assertNotIn("focus", calls2)

    def test_native_bars_have_address_and_nav_controls(self):
        for name in ("browser_win.py", "browser_mac.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            ast.parse(src)
            for needle in ("bar_open", "bar_nav", "_sync_bar", "focus_address", "주소 또는 검색어", "기본 브라우저로 열기"):
                self.assertIn(needle, src, f"{name}: {needle}")
        win = (ROOT / "browser_win.py").read_text(encoding="utf-8")
        self.assertNotIn("b.AutoSize = True", win)  # 1.19.0의 잘림: 버튼이 막대 높이를 채운다


if __name__ == "__main__":
    unittest.main()
