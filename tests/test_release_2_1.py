# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.1.0: PLMS 연결과 자동 로그인(SSO)을 없앴다. 코드·화면·설정에 남은 것이 없고, 예전에 저장한 계정은 첫 실행 때 지운다."""
import importlib.util
import os
import re
import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import isolated_app_dir  # noqa: E402

import storage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# 지난 기록(릴리스 노트·로드맵·README 버전 기록)과 이 시험 자신은 PLMS를 말할 수 있다
SOURCES = [p for p in ROOT.glob("*.py")] + [ROOT / "web" / n for n in ("app.js", "browser.js", "index.html", "style.css")]


class PlmsRemovedTests(unittest.TestCase):
    def test_module_is_gone(self):
        self.assertFalse((ROOT / "plms.py").exists())
        self.assertIsNone(importlib.util.find_spec("plms"))

    def test_no_plms_or_autologin_in_app_sources(self):
        pattern = re.compile(r"plms|stonepass|\bSSO\b|자동 ?로그인|autologin", re.I)
        for path in SOURCES:
            if path.name == "main.py":
                text = re.sub(r"(?s)if not self\._config\.get\(\"migrated_2_1\"\):.*?changed = True\n", "",
                              path.read_text(encoding="utf-8"))
            else:
                text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertIsNone(pattern.search(text), pattern.search(text) and text[pattern.search(text).start() - 60:][:160])

    def test_browser_has_no_hidden_login_or_cookie_api(self):
        import browser
        for name in ("plms_cookies", "run_script", "open_background", "ensure"):
            self.assertFalse(hasattr(browser.Browser, name), name)

    def test_agents_have_no_plms_tools(self):
        import agent
        import code_agent
        import quality_gate
        for cls in (agent.Agent, code_agent.CodeAgent):
            self.assertEqual([n for n in dir(cls) if "plms" in n], [])
        self.assertFalse(any("plms" in a for a in quality_gate.AGENT_ACTIONS))


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.iso = isolated_app_dir()
        self.iso.__enter__()
        self.addCleanup(self.iso.__exit__, None, None, None)
        os.environ.setdefault("POSTECH_CHAT_SECRETS", "file")
        sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))

    def test_saved_account_and_setting_are_cleared_once(self):
        import secret_store
        secret_store.set_json("plms_login", {"username": "student", "password": "pw-1"})
        cfg = storage.load_config()
        cfg["plms_enabled"] = True
        storage.save_config(cfg)

        import main
        b = main.Bridge()
        self.addCleanup(b._mcp.shutdown)
        self.assertIsNone(secret_store.get_json("plms_login"))
        saved = storage.load_config()
        self.assertNotIn("plms_enabled", saved)
        self.assertTrue(saved.get("migrated_2_1"))
        self.assertNotIn("plms", str(b.get_state()["config"]).lower())
        for name in ("plms_login", "plms_courses", "plms_save_account", "plms_disconnect"):
            self.assertFalse(hasattr(b, name), name)


if __name__ == "__main__":
    unittest.main()
