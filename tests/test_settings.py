# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
import tempfile
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("webview", types.ModuleType("webview"))
import main as app_main

Bridge = app_main.Bridge


class SettingsTests(unittest.TestCase):
    def bridge(self, config=None):
        bridge = Bridge.__new__(Bridge)
        bridge._config = config or {}
        bridge._lock = threading.RLock()
        return bridge

    def test_selected_api_modes_require_an_https_endpoint(self):
        bridge = self.bridge()
        responses = bridge.save_settings({"api_mode": "responses", "responses_url": ""})
        compatible = bridge.save_settings({"api_mode": "chat_completions", "chat_completions_url": "http://api.test/v1/chat/completions"})

        self.assertFalse(responses["ok"])
        self.assertIn("Responses API", responses["error"])
        self.assertFalse(compatible["ok"])
        self.assertIn("Chat Completions", compatible["error"])

    @patch.object(app_main.storage, "save_config")
    def test_valid_selected_endpoint_is_saved(self, save_config):
        bridge = self.bridge()
        bridge.get_state = lambda: {"ok": True}

        result = bridge.save_settings({
            "api_mode": "chat_completions",
            "chat_completions_url": "https://api.example.edu/v1/chat/completions",
        })

        self.assertTrue(result["ok"])
        self.assertEqual(bridge._config["chat_completions_url"], "https://api.example.edu/v1/chat/completions")
        save_config.assert_called_once()

    def test_each_thread_keeps_its_selected_model(self):
        with tempfile.TemporaryDirectory() as temp:
            thread_dir = Path(temp) / "threads"
            thread_dir.mkdir()
            with patch.object(app_main.storage, "THREADS_DIR", thread_dir):
                bridge = self.bridge({"api_mode": "chat_completions", "model": "gemini-3.8-flash"})
                thread = bridge.new_thread()
                bridge._config["model"] = "gpt-6-astra"

                loaded = bridge.load_thread(thread["id"])
                self.assertEqual(loaded["model"], "gemini-3.8-flash")
                self.assertEqual(loaded["updated"], thread["updated"])
                changed = bridge.set_thread_model(thread["id"], "claude-sonnet-5-5")
                self.assertEqual(changed["model"], "claude-sonnet-5-5")
                self.assertEqual(bridge.load_thread(thread["id"])["model"], "claude-sonnet-5-5")

                # 1.9 이전에 저장한 잘못된 Claude ID(점)는 게이트웨이의 ID(-)로 바뀐다
                old = app_main.storage.new_thread()
                old["model"] = "claude-opus-5.5"
                app_main.storage.save_thread(old)
                self.assertEqual(bridge.load_thread(old["id"])["model"], "claude-opus-5-5")

                legacy = app_main.storage.new_thread()
                legacy_updated = legacy["updated"]
                migrated = bridge.load_thread(legacy["id"])
                self.assertEqual(migrated["model"], "gpt-6-astra")
                self.assertEqual(migrated["updated"], legacy_updated)

    def test_responses_mode_rejects_models_outside_its_supported_set(self):
        bridge = self.bridge({"api_mode": "responses"})
        result = bridge.set_thread_model("missing", "claude-sonnet-5-5")
        self.assertFalse(result["ok"])
        self.assertIn("지원하지 않는", result["error"])

    @patch.object(app_main.storage, "save_config")
    def test_base_url_is_saved_as_full_endpoint(self, _save_config):
        bridge = self.bridge()
        bridge.get_state = lambda: {"ok": True}
        result = bridge.save_settings({"api_mode": "chat_completions", "chat_completions_url": "https://api.example.edu/v1/"})
        self.assertTrue(result["ok"])
        self.assertEqual(bridge._config["chat_completions_url"], "https://api.example.edu/v1/chat/completions")

    @patch.object(app_main.storage, "save_config")
    @patch.object(app_main.api, "list_models", return_value=["gpt-6.1-sol", "new-model-x"])
    def test_server_models_replace_the_builtin_list_when_saved(self, list_models, save_config):
        bridge = self.bridge({"api_mode": "chat_completions", "api_key": "saved-key"})
        result = bridge.refresh_models({"chat_completions_url": "https://api.example.edu/v1"})

        self.assertTrue(result["ok"])
        list_models.assert_called_once_with("saved-key", "https://api.example.edu/v1/chat/completions")
        self.assertEqual([m["id"] for m in result["models"]], ["gpt-6.1-sol", "new-model-x"])
        # 불러오기만 하고 저장하지 않으면(설정 창 취소) 아무것도 바뀌지 않는다
        save_config.assert_not_called()
        self.assertNotIn("server_models", bridge._config)
        self.assertNotIn("chat_completions_url", bridge._config)

        bridge.get_state = lambda: {"ok": True}
        bridge.save_settings({"chat_completions_url": result["chat_completions_url"],
                              "server_models": [m["id"] for m in result["models"]], "model": "new-model-x"})
        self.assertEqual(bridge._model_ids("chat_completions"), {"gpt-6.1-sol", "new-model-x"})
        self.assertEqual(bridge._config["model"], "new-model-x")
        self.assertEqual({m for m, _ in bridge._models("responses")}, {m for m, _ in app_main.RESPONSES_MODELS})

        bridge.save_settings({"chat_completions_url": "https://other.example.edu/v1"})
        self.assertNotIn("server_models", bridge._config)

    @patch.object(app_main.storage, "save_config")
    @patch.object(app_main.storage, "backup_user_data", return_value=None)  # 1.10 첫 실행 백업은 test_migration에서
    def test_old_a1_default_moves_to_the_openai_compatible_api_once(self, _backup, save_config):
        bridge = self.bridge({"api_mode": "a1", "model": "claude-sonnet-5.5"})
        bridge._migrate_config()
        self.assertEqual(bridge._config["api_mode"], "chat_completions")
        self.assertEqual(bridge._config["model"], "claude-sonnet-5-5")
        self.assertEqual(app_main.ApiSettings.from_config(bridge._config).chat_completions_url,
                         app_main.api.DEFAULT_CHAT_COMPLETIONS_URL)
        bridge._config["api_mode"] = "a1"  # 옮긴 뒤 사용자가 다시 a1을 고르면 그대로 둔다
        bridge._migrate_config()
        self.assertEqual(bridge._config["api_mode"], "a1")

    def test_po_budget_guard_keeps_the_reserved_share_of_weekly_credits(self):
        bridge = self.bridge({"po_reserve": 30})
        bridge._credit = None
        self.assertTrue(bridge._po_budget_ok())  # 크레딧을 아직 모르면 막지 않는다
        bridge._credit = {"usage": 10000, "limit": 15000, "interval": "WEEKLY"}
        self.assertTrue(bridge._po_budget_ok())   # 남은 5,000 ≥ 4,500
        bridge._credit = {"usage": 11000, "limit": 15000, "interval": "WEEKLY"}
        self.assertFalse(bridge._po_budget_ok())  # 남은 4,000 < 4,500
        bridge._config["po_reserve"] = 0
        self.assertTrue(bridge._po_budget_ok())

    @patch.object(app_main.storage, "save_config")
    @patch.object(app_main.updates, "check")
    @patch.object(app_main.updates, "cleanup")
    def test_startup_update_check_respects_setting_interval_and_skip(self, cleanup, check, _save_config):
        check.return_value = {"available": True, "version": "1.10.0", "asset": "PostechChat-Setup.exe",
                              "name": "", "notes": "", "url": ""}
        bridge = self.bridge({"update_check": False})
        self.assertTrue(bridge.check_for_updates(False)["skipped"])  # 꺼 두면 시작할 때 묻지 않는다
        self.assertTrue(bridge.check_for_updates(True)["available"])  # '업데이트 확인' 버튼은 언제나 묻는다
        bridge._config["update_check"] = True
        self.assertTrue(bridge.check_for_updates(False)["skipped"])  # 방금 확인했다: 6시간 안에는 다시 묻지 않는다
        bridge._config["update_checked_at"] = 0
        bridge._config["update_skip"] = "1.10.0"
        self.assertFalse(bridge.check_for_updates(False)["available"])  # 건너뛴 버전은 알리지 않는다
        check.side_effect = app_main.updates.UpdateError("업데이트 정보를 찾지 못했습니다")
        self.assertIn("찾지 못했습니다", bridge.check_for_updates(True)["error"])
        # 2.3.1: 시작할 때(manual=False)만 지난 업데이트 설치 파일을 정리한다. '업데이트 확인' 버튼은 정리하지 않는다
        self.assertEqual(cleanup.call_count, 3)
        cleanup.reset_mock()
        bridge._updating = True   # 받는 중에는 받던 파일을 건드리지 않는다
        bridge.check_for_updates(False)
        cleanup.assert_not_called()

    def test_refresh_models_needs_key_and_https_url(self):
        with patch.dict(app_main.os.environ, {}, clear=True):
            self.assertFalse(self.bridge().refresh_models({"chat_completions_url": "https://api.example.edu/v1"})["ok"])
        bad = self.bridge({"api_key": "k"}).refresh_models({"chat_completions_url": "http://api.example.edu/v1"})
        self.assertFalse(bad["ok"])

    @patch.object(app_main.api, "list_models", side_effect=app_main.ApiError("API 오류 401"))
    def test_refresh_models_reports_server_errors(self, _list_models):
        result = self.bridge({"api_key": "k"}).refresh_models({"chat_completions_url": "https://api.example.edu/v1"})
        self.assertFalse(result["ok"])
        self.assertIn("401", result["error"])

    @patch.object(app_main.storage, "save_config")
    def test_personal_claude_api_uses_its_own_key_and_model(self, _save_config):
        with patch.dict(app_main.os.environ, {}, clear=True):
            bridge = self.bridge({"api_key": "postech-key", "model": "gpt-6-astra"})
            bridge.get_state = lambda: {"ok": True}
            bridge.save_settings({"api_mode": "anthropic", "anthropic_api_key": " sk-ant-mine ",
                                  "model": "claude-haiku-5-5"})
            self.assertEqual(bridge._config["api_mode"], "anthropic")
            self.assertEqual(bridge._config["anthropic_api_key"], "sk-ant-mine")
            self.assertEqual(bridge._config["anthropic_model"], "claude-haiku-5-5")
            self.assertEqual(bridge._config["model"], "gpt-6-astra")  # POSTECH 쪽 기본 모델은 그대로
            # 대화는 Anthropic 키로, 크레딧·PO노트 서버 음성 인식은 POSTECH 키로
            self.assertEqual(bridge._api_key(), "sk-ant-mine")
            self.assertEqual(bridge._postech_key(), "postech-key")
            self.assertEqual(bridge._default_model(), "claude-haiku-5-5")
            self.assertEqual(app_main.ApiSettings.from_config(bridge._config).model, "claude-haiku-5-5")
            # POSTECH 모델 ID는 개인 Claude API에서 고를 수 없다
            bridge.save_settings({"model": "gpt-6-astra"})
            self.assertEqual(bridge._config["anthropic_model"], "claude-haiku-5-5")
            bridge.save_settings({"clear_anthropic_key": True})
            self.assertEqual(bridge._api_key(), "")
            self.assertIn("Claude API 키", bridge._missing_key_error())
            bridge.save_settings({"api_mode": "chat_completions"})
            self.assertEqual(bridge._api_key(), "postech-key")

    def test_anthropic_key_can_come_from_the_environment(self):
        with patch.dict(app_main.os.environ, {"ANTHROPIC_API_KEY": "sk-ant-env"}, clear=True):
            bridge = self.bridge({"api_mode": "anthropic"})
            self.assertEqual(bridge._api_key(), "sk-ant-env")
            self.assertEqual(bridge._postech_key(), "")

    @patch.object(app_main.api, "list_anthropic_models", return_value=["claude-opus-5-5", "claude-opus-4-8"])
    @patch.object(app_main.storage, "save_config")
    def test_claude_model_list_is_kept_only_after_saving(self, _save_config, list_models):
        with patch.dict(app_main.os.environ, {}, clear=True):
            bridge = self.bridge({"api_mode": "anthropic"})
            self.assertFalse(bridge.refresh_models({"api_mode": "anthropic"})["ok"])  # 키가 없다
            result = bridge.refresh_models({"api_mode": "anthropic", "anthropic_api_key": "sk-ant-new"})
            list_models.assert_called_once_with("sk-ant-new")
            self.assertEqual([m["id"] for m in result["models"]], ["claude-opus-5-5", "claude-opus-4-8"])
            self.assertNotIn("anthropic_server_models", bridge._config)
            bridge.get_state = lambda: {"ok": True}
            bridge.save_settings({"anthropic_server_models": ["claude-opus-4-8"], "model": "claude-opus-4-8"})
            self.assertEqual(bridge._config["anthropic_model"], "claude-opus-4-8")
            self.assertEqual([m for m, _ in bridge._models("anthropic")], ["claude-opus-4-8"])

    def test_verify_install_writes_the_version_without_starting_the_app(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "v.txt"
            with patch.object(app_main.sys, "argv", ["PostechChat.exe", f"--verify-install={out}"]), \
                    patch.object(app_main, "run_app", side_effect=AssertionError("창을 열면 안 된다")):
                app_main.main()
            self.assertEqual(out.read_text(encoding="utf-8"), app_main.APP_VERSION)


if __name__ == "__main__":
    unittest.main()
