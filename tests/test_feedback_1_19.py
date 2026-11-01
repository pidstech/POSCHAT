# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""1.19 공개 전 사용자 피드백(백엔드): 플러그인 한국어 설명, 사용량 그래프 자료, 시작 창 크기 설정,
PLMS 창에서 계정 저장, 브라우저 막대의 '기본 브라우저로 열기'·닫기."""
import ast
import re
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import isolated_app_dir  # noqa: E402

import browser  # noqa: E402
import plugins  # noqa: E402
import plugins_ko  # noqa: E402
import storage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class PluginKoreanTests(unittest.TestCase):
    def test_every_translation_is_korean_and_keys_are_well_formed(self):
        self.assertGreater(len(plugins_ko.KO), 300)
        for key, text in plugins_ko.KO.items():
            self.assertRegex(key, r"^[a-z0-9][a-z0-9._-]*(/(cmd:)?[A-Za-z0-9._:/-]+)?$", key)
            self.assertRegex(text, "[가-힣]", key)
            self.assertLessEqual(len(text), 260, key)

    def test_localize_adds_korean_without_touching_the_original(self):
        data = {"plugins": [
            {"name": "productivity", "summary": "기존 소개", "description": "Original",
             "skills": [{"name": "start", "description": "Start the system"}, {"name": "unknown-skill", "description": "x"}],
             "commands": []},
            {"name": "airtable", "summary": "", "description": "Airtable plugin", "skills": [], "commands": []},
        ]}
        out = plugins.localize(data)
        prod, air = out["plugins"]
        self.assertEqual(prod["summary"], "기존 소개")  # 손으로 쓴 소개가 먼저
        self.assertEqual(prod["skills"][0]["description"], "Start the system")
        self.assertRegex(prod["skills"][0]["description_ko"], "[가-힣]")
        self.assertNotIn("description_ko", prod["skills"][1])  # 번역이 없으면 원문만
        self.assertRegex(air["summary"], "[가-힣]")
        self.assertEqual(air["description"], "Airtable plugin")

    def test_catalog_returns_localized_entries(self):
        with isolated_app_dir():
            plugins._catalog_dir().mkdir(parents=True, exist_ok=True)
            plugins._archive().write_bytes(b"zip")
            plugins._write_json(plugins._catalog_file(), {"plugins": [
                {"name": "data", "summary": "", "description": "", "skills": [{"name": "write-query", "description": "SQL"}],
                 "commands": []}]})
            entry = plugins.catalog()["plugins"][0]
            self.assertRegex(entry["skills"][0].get("description_ko", ""), "[가-힣]")
            # 받아 둔 목록 파일에는 번역을 쓰지 않는다(원문 그대로)
            self.assertNotIn("description_ko", plugins._read_json(plugins._catalog_file(), {})["plugins"][0]["skills"][0])


class UsageDailyTests(unittest.TestCase):
    def test_summary_has_thirty_days_oldest_first_with_zeros(self):
        with isolated_app_dir():
            today = time.strftime("%Y-%m-%d")
            old = time.strftime("%Y-%m-%d", time.localtime(time.time() - 5 * 86400))
            storage._write_json(storage.USAGE_PATH, {today: {"calls": 1, "input_tokens": 10, "output_tokens": 4},
                                                     old: {"calls": 2, "input_tokens": 100, "output_tokens": 50}})
            daily = storage.usage_summary()["daily"]
            self.assertEqual(len(daily), 30)
            self.assertEqual(daily[-1], {"day": today, "calls": 1, "input_tokens": 10, "output_tokens": 4})
            self.assertEqual(daily[-6]["input_tokens"], 100)
            self.assertEqual(sum(d["calls"] for d in daily), 3)
            self.assertEqual([d["day"] for d in daily], sorted(d["day"] for d in daily))


class BridgeSettingsTests(unittest.TestCase):
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
        self.bridge = main.Bridge()
        self.addCleanup(self.bridge._mcp.shutdown)
        self.addCleanup(self.bridge._events.stop)

    def test_window_mode_is_saved_and_unknown_values_are_ignored(self):
        self.assertEqual(self.bridge.get_state()["config"]["window_mode"], "maximized")  # 2.0 기본값
        self.bridge.save_settings({"window_mode": "fullscreen"})
        self.assertEqual(storage.load_config()["window_mode"], "fullscreen")
        self.bridge.save_settings({"window_mode": "kiosk"})
        self.assertEqual(self.bridge.get_state()["config"]["window_mode"], "fullscreen")
        self.bridge._config["window_mode"] = "weird"
        self.assertEqual(self.bridge._window_mode(), "maximized")

    def test_run_app_passes_the_window_mode_to_pywebview(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        run_app = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_app")
        call = next(n for n in ast.walk(run_app) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "create_window")
        self.assertEqual({k.arg for k in call.keywords} >= {"maximized", "fullscreen"}, True)

    def test_plms_save_account_requires_both_fields_and_enables_plms(self):
        import plms
        self.assertFalse(self.bridge.plms_save_account("student", "")["ok"])
        self.assertFalse(self.bridge.plms_save_account("", "pw")["ok"])
        res = self.bridge.plms_save_account(" student ", "pw-1")
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["plms_username"], "student")
        self.assertEqual(plms.saved_username(), "student")
        self.assertTrue(storage.load_config().get("plms_enabled"))
        self.assertNotIn("pw-1", (storage.CONFIG_PATH).read_text(encoding="utf-8"))
        plms.clear_credentials()


class BrowserToolbarTests(unittest.TestCase):
    def make(self, toolbar):
        events = []
        backend = type("B", (), {"mode": "native", "toolbar": toolbar, "show": lambda s, r: None,
                                 "open": lambda s, u: None, "hide": lambda s: None})()
        b = browser.Browser(lambda _: backend, on_event=events.append)
        return b, events

    def test_events_report_whether_the_native_toolbar_exists(self):
        b, events = self.make(True)
        b.show()
        self.assertTrue(events[-1]["toolbar"])
        b, events = self.make(False)
        b.show()
        self.assertFalse(events[-1]["toolbar"])

    def test_open_external_only_opens_web_addresses(self):
        b, _ = self.make(True)
        opened = []
        b.opener = opened.append
        b.open_external()  # 아직 주소 없음
        b.state["url"] = "file:///C:/Windows/System32/calc.exe"
        b.open_external()
        b.state["url"] = "https://example.com/a"
        b.open_external()
        self.assertEqual(opened, ["https://example.com/a"])

    def test_native_backends_build_the_toolbar_and_hide_through_the_controller(self):
        for name in ("browser_win.py", "browser_mac.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("self.toolbar = True", text, name)
            self.assertIn("open_external", text, name)
            # 버튼 처리기는 UI 스레드에서 돈다: hide는 작업 스레드로 넘겨야 한다(B1)
            self.assertTrue(re.search(r"threading\.Thread\(target=(self\.owner\.browser|handler)", text), name)


if __name__ == "__main__":
    unittest.main()
