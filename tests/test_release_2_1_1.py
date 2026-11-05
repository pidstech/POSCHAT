# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.1.1: PO노트 녹음 중 크레딧 '확인'으로 예산 아래 값이 들어오면 서버 보정이 녹음 끝까지 멈추던 문제.

멈춘 동안에는 서버를 부르지 않아 크레딧 값이 새로 오지 않았다. 이제 멈춘 동안 2분마다 크레딧을 다시 확인해
예산이 돌아오면 다시 보정하고, 멈춘 동안 고치지 못한 구간도 함께 고친다. 멈춤·다시 시작은 화면에 알린다."""
import os
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import isolated_app_dir  # noqa: E402

import stt  # noqa: E402
from test_po_note import FakeLocal, FakeRefiner  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class BudgetRecoveryTests(unittest.TestCase):
    def setUp(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy 없음")
        self.np = np

    def session(self, budget, refresh=None, refiner=None):
        self.segs, self.refined, self.notes, self.events = [], [], [], []
        s = stt.LiveSession(FakeLocal([0.5] * 40), self.segs.append, on_error=self.notes.append,
                            refiner=refiner or FakeRefiner(lambda drafts: [d + "(고침)" for d in drafts]),
                            on_refine=lambda ids, fixed: self.refined.append((ids, fixed)),
                            budget_ok=budget, budget_refresh=refresh, on_budget=self.events.append)
        s._segmenter = type("S", (), {"_np": self.np})()
        return s

    def test_refresh_while_paused_resumes_refinement(self):
        credit = {"low": True}
        refreshed = []

        def refresh():
            refreshed.append(1)
            credit["low"] = False  # 다시 확인하니 예산이 남아 있다

        s = self.session(lambda: not credit["low"], refresh)
        with patch.object(stt, "BUDGET_RECHECK", 0):
            self.assertTrue(s._budget())
        self.assertEqual(refreshed, [1])
        self.assertFalse(s.budget_paused)

    def test_pause_and_resume_are_announced_every_time(self):
        credit = {"low": True}
        s = self.session(lambda: not credit["low"])
        self.assertFalse(s._budget())
        self.assertFalse(s._budget())   # 같은 멈춤은 다시 알리지 않는다
        credit["low"] = False
        self.assertTrue(s._budget())
        credit["low"] = True
        self.assertFalse(s._budget())   # 두 번째 멈춤도 알린다(예전에는 녹음마다 한 번뿐이었다)
        self.assertEqual(self.events, [True, False, True])
        self.assertEqual(sum("예산" in n for n in self.notes), 2)

    def test_refresh_is_rate_limited(self):
        # 부팅한 지 얼마 안 된 PC(monotonic이 120초보다 작다)에서도 처음 멈출 때 바로 다시 확인해야 한다
        clock = [30.0]
        calls = []
        s = self.session(lambda: False, lambda: calls.append(1))
        with patch.object(stt.time, "monotonic", lambda: clock[0]):
            for _ in range(5):
                s._budget()
            self.assertEqual(len(calls), 1)  # 처음 멈출 때 한 번 다시 확인하고, 그 뒤로는 BUDGET_RECHECK마다
            clock[0] += stt.BUDGET_RECHECK - 1
            s._budget()
            self.assertEqual(len(calls), 1)
            clock[0] += 1
            s._budget()
            self.assertEqual(len(calls), 2)

    def test_segments_skipped_while_paused_are_refined_after_resume(self):
        np = self.np
        credit = {"low": True}
        s = self.session(lambda: not credit["low"])
        t = threading.Thread(target=s._refine_loop)
        t.start()
        # 첫 묶음(10초 구간 12개 = 120초)은 예산 아래라 보정하지 못한다
        for i in range(12):
            s._refine_jobs.put(({"id": i, "text": f"a{i}", "conf": 0.5}, np.zeros(16000 * 10, dtype=np.float32)))
        deadline = 50
        while not s.budget_paused and deadline:
            threading.Event().wait(0.05)
            deadline -= 1
        self.assertTrue(s.budget_paused)
        credit["low"] = False
        s._refine_jobs.put(({"id": 12, "text": "a12", "conf": 0.5}, np.zeros(16000 * 10, dtype=np.float32)))
        s._refine_jobs.put(None)
        t.join(5)
        ids = [i for batch, _ in self.refined for i in batch]
        self.assertEqual(ids, list(range(13)))  # 멈춘 동안의 구간까지 함께 고쳤다
        self.assertEqual(self.events, [True, False])


class BridgeWiringTests(unittest.TestCase):
    def setUp(self):
        self.iso = isolated_app_dir()
        self.iso.__enter__()
        self.addCleanup(self.iso.__exit__, None, None, None)
        os.environ.setdefault("POSTECH_CHAT_SECRETS", "file")
        sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))

    def test_credit_check_and_recording_use_the_same_server(self):
        import api
        import main
        b = main.Bridge()
        self.addCleanup(b._mcp.shutdown)
        b._config["chat_completions_url"] = "https://example.com/v1/chat/completions"
        self.assertEqual(b._credit_url(), api.DEFAULT_CHAT_COMPLETIONS_URL)
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("budget_refresh=budget_refresh, on_budget=on_budget", source)
        self.assertIn('"budget_paused"', source)

    def test_screen_shows_paused_refinement(self):
        js = (ROOT / "web" / "po.js").read_text(encoding="utf-8")
        self.assertIn('case "budget"', js)
        self.assertIn("서버 보정 멈춤", js)


if __name__ == "__main__":
    unittest.main()
