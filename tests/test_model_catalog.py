# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.3 모델 목록 자동 동기화: 카탈로그 형식 검사, 기본 목록 대체, 옛 ID 옮기기, Bridge.sync_models."""
import io
import json
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("webview", types.ModuleType("webview"))
import api  # noqa: E402
import main as app_main  # noqa: E402
import model_catalog  # noqa: E402
import net  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

CATALOG = {
    "schema": 1, "updated": "2026-12-01",
    "chat_completions": [{"id": "gpt-7-gs", "label": "GPT-7 — 권장"}, {"id": "gpt-5.1-gs-2025-11-13", "label": "GPT-5.1"}],
    "anthropic": [{"id": "claude-opus-6-0", "label": "Claude Opus 6"}],
    "aliases": {"claude-opus-5-5": "claude-opus-6-0"},
    "future_key": {"ignored": True},
}


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self.raw = io.BytesIO(body)
        self.raw.read = (lambda read: (lambda n, decode_content=True: read(n)))(self.raw.read)

    def close(self):
        pass


def bridge(config=None):
    b = app_main.Bridge.__new__(app_main.Bridge)
    b._config = config or {}
    b._lock = threading.RLock()
    return b


class CatalogFormatTests(unittest.TestCase):
    def test_repository_models_json_matches_api(self):
        data = json.loads((ROOT / "models.json").read_text(encoding="utf-8"))
        built = model_catalog.build(api)
        data.pop("updated"), built.pop("updated")
        self.assertEqual(data, built, "api.py를 고쳤으면 `python tools/model_catalog.py write`를 실행하세요")

    def test_validate_keeps_only_known_fields(self):
        c = model_catalog.validate(CATALOG)
        self.assertEqual(c["modes"]["chat_completions"][0], ["gpt-7-gs", "GPT-7 — 권장"])
        self.assertNotIn("openai", c["modes"])
        self.assertNotIn("future_key", c)
        self.assertEqual(model_catalog.load(c), c)

    def test_validate_rejects_bad_catalogs(self):
        bad = [
            {**CATALOG, "schema": 2},
            {**CATALOG, "anthropic": []},
            {**CATALOG, "anthropic": [{"id": "x y"}]},
            {**CATALOG, "anthropic": [{"id": "<script>"}]},
            {**CATALOG, "aliases": {"a": "b c"}},
            {**CATALOG, "chat_completions": [{"id": f"m{i}"} for i in range(101)]},
            {"schema": 1},
            [],
        ]
        for data in bad:
            with self.assertRaises(model_catalog.CatalogError):
                model_catalog.validate(data)
        self.assertIsNone(model_catalog.load({"modes": {"anthropic": [["bad id", "x"]]}, "schema": 1}))

    def test_label_is_trimmed(self):
        c = model_catalog.validate({"schema": 1, "openai": [{"id": "gpt-x", "label": "  a \n b " + "x" * 200}]})
        label = c["modes"]["openai"][0][1]
        self.assertTrue(label.startswith("a b "))
        self.assertLessEqual(len(label), model_catalog.MAX_LABEL)


class FetchTests(unittest.TestCase):
    def test_falls_back_to_second_source(self):
        calls = []

        def fake(method, url, **kw):
            calls.append(url)
            if len(calls) == 1:
                raise net.ToolFailure("blocked")
            return FakeResponse(200, json.dumps(CATALOG).encode())

        with patch.object(net, "http", fake):
            c = model_catalog.fetch()
        self.assertEqual(calls, list(model_catalog.SOURCES))
        self.assertEqual(c["updated"], "2026-12-01")

    def test_too_large_or_bad_json_is_an_error(self):
        for body in (b"{" + b" " * model_catalog.MAX_BYTES + b"}", b"not json", b'{"schema": 9}'):
            with patch.object(net, "http", lambda *a, **k: FakeResponse(200, body)):
                with self.assertRaises(model_catalog.CatalogError):
                    model_catalog.fetch()
        with patch.object(net, "http", lambda *a, **k: FakeResponse(404, b"")):
            with self.assertRaises(model_catalog.CatalogError):
                model_catalog.fetch()


class ApplyTests(unittest.TestCase):
    def tearDown(self):
        api.set_catalog(None)

    def test_catalog_replaces_builtin_lists_and_aliases(self):
        api.set_catalog(model_catalog.validate(CATALOG))
        b = bridge({"api_mode": "chat_completions"})
        self.assertEqual(b._models("chat_completions")[0], ("gpt-7-gs", "GPT-7 — 권장"))
        self.assertEqual(b._models(api.ANTHROPIC_MODE), [("claude-opus-6-0", "Claude Opus 6")])
        self.assertEqual(b._models(api.OPENAI_MODE), api.OPENAI_MODELS)   # 카탈로그에 없는 방식은 기본 목록
        self.assertEqual(b._models("responses"), api.RESPONSES_MODELS)
        self.assertEqual(api.normalize_model("claude-opus-5-5"), "claude-opus-6-0")
        self.assertEqual(api.normalize_model("claude-opus-5.5"), "claude-opus-6-0")   # 옛 별칭 → 카탈로그 별칭
        self.assertEqual(api.model_label("gpt-7-gs"), "GPT-7 — 권장")
        # 설정의 기본 모델이 옛 ID면 새 ID로, 목록에서 사라졌으면 목록의 첫 모델로
        self.assertEqual(bridge({"api_mode": "anthropic", "anthropic_model": "claude-opus-5-5"})._default_model(),
                         "claude-opus-6-0")
        self.assertEqual(bridge({"api_mode": "chat_completions", "model": "gpt-6-astra"})._default_model(), "gpt-7-gs")

    def test_server_list_wins_over_catalog(self):
        api.set_catalog(model_catalog.validate(CATALOG))
        b = bridge({"anthropic_server_models": ["claude-mine"]})
        self.assertEqual(b._models(api.ANTHROPIC_MODE), [("claude-mine", "claude-mine")])

    def test_no_catalog_means_builtin(self):
        api.set_catalog(None)
        self.assertEqual(bridge()._models("chat_completions"), api.MODELS)
        self.assertEqual(api.normalize_model("claude-opus-5-5"), "claude-opus-5-5")


class SyncTests(unittest.TestCase):
    def tearDown(self):
        api.set_catalog(None)

    def run_sync(self, config, manual=False, catalog=CATALOG, refresh=None):
        b = bridge(config)
        fetch = (lambda: model_catalog.validate(catalog)) if catalog else \
            (lambda: (_ for _ in ()).throw(model_catalog.CatalogError("offline")))
        with patch.object(model_catalog, "fetch", fetch), \
                patch.object(app_main.storage, "save_config") as save, \
                patch.object(b, "refresh_models", refresh or (lambda s: {"ok": False, "error": "no key"})):
            result = b.sync_models(manual)
        return b, result, save

    def test_stores_catalog_and_reports_change(self):
        b, result, save = self.run_sync({})
        self.assertTrue(result["changed"])
        self.assertEqual(b._config["model_catalog"]["updated"], "2026-12-01")
        self.assertEqual(b._models("chat_completions")[0][0], "gpt-7-gs")
        self.assertTrue(save.called)
        # 같은 카탈로그를 다시 받으면 바뀐 것이 없다
        b2, again, _ = self.run_sync({"model_catalog": b._config["model_catalog"]}, manual=True)
        self.assertFalse(again["changed"])

    def test_respects_setting_and_interval(self):
        _, off, _ = self.run_sync({"model_sync": False})
        self.assertTrue(off.get("skipped"))
        _, recent, _ = self.run_sync({"model_synced_at": app_main.time.time()})
        self.assertTrue(recent.get("skipped"))
        _, manual, _ = self.run_sync({"model_sync": False}, manual=True)
        self.assertTrue(manual["changed"])

    def test_offline_keeps_current_lists(self):
        b, result, _ = self.run_sync({}, catalog=None)
        self.assertFalse(result["changed"])
        self.assertFalse(result["ok"])
        self.assertNotIn("model_catalog", b._config)
        self.assertNotIn("model_synced_at", b._config)   # 다음 시작 때 다시 시도
        self.assertEqual(b._models("chat_completions"), api.MODELS)

    def test_refreshes_saved_server_lists_only(self):
        asked = []

        def refresh(settings):
            asked.append(settings["api_mode"])
            return {"ok": True, "models": [{"id": "claude-new"}, {"id": "claude-mine"}]}

        b, result, _ = self.run_sync({"anthropic_server_models": ["claude-mine"]}, refresh=refresh)
        self.assertEqual(asked, [api.ANTHROPIC_MODE])
        self.assertEqual(b._config["anthropic_server_models"], ["claude-new", "claude-mine"])
        self.assertTrue(result["changed"])


if __name__ == "__main__":
    unittest.main()
