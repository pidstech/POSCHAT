# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""토큰 효율: 단계마다 되풀이해서 보내는 프롬프트 부분이 부풀지 않는지."""
import json
import tempfile
import unittest

import agent
from agent import Agent


def make(**kw):
    workspace = tempfile.mkdtemp()
    return Agent("key", workspace, True, 5, kw.pop("history_messages", 20), on_status=lambda *a: None,
                 on_tool=lambda *a: None, confirm=lambda *a: True, cancelled=lambda: False, **kw)


def act(**kw):
    return json.dumps(kw, ensure_ascii=False)


class FormatLogTests(unittest.TestCase):
    def test_repeated_read_keeps_only_the_latest_result(self):
        read = act(action="read", path="a.py")
        log = [(read, "옛 내용" * 50), (act(action="edit", path="a.py"), "ok"), (read, "새 내용")]
        text = Agent._format_log(log)
        self.assertNotIn("옛 내용", text)
        self.assertIn("3번에서 다시 했습니다", text)
        self.assertIn("새 내용", text)

    def test_non_read_steps_are_not_collapsed(self):
        run = act(action="run", command="pytest")
        text = Agent._format_log([(run, "첫 실패"), (run, "두 번째 결과")])
        self.assertIn("첫 실패", text)

    def test_old_observations_are_shortened(self):
        log = [(act(action="search", query=str(i)), "x" * 3000) for i in range(agent.RECENT_FULL_STEPS + 2)]
        text = Agent._format_log(log)
        self.assertLess(len(text), 2 * 3000 + agent.RECENT_FULL_STEPS * 3000 + 5000)
        self.assertEqual(text.count("x" * 3000), agent.RECENT_FULL_STEPS)


    def test_stale_browser_snapshots_are_shortened(self):
        log = [(act(action="browser_click", id="1"), "첫 화면 " * 200), (act(action="browser_click", id="2"), "마지막 화면 " * 200)]
        text = Agent._format_log(log)
        self.assertEqual(text.count("마지막 화면 " * 200), 1)
        self.assertNotIn("첫 화면 " * 200, text)
        self.assertIn("첫 화면", text)


class DocCacheTests(unittest.TestCase):
    def test_cache_drops_oldest_documents_over_the_budget(self):
        from pathlib import Path
        from unittest import mock

        a = make()
        with tempfile.TemporaryDirectory() as d, mock.patch.object(agent, "DOC_CACHE_CHARS", 250), \
                mock.patch.object(agent.documents, "extract_text", side_effect=lambda p: "x" * 100):
            paths = []
            for i in range(4):
                f = Path(d) / f"{i}.docx"
                f.write_bytes(b"x")
                paths.append(f)
                a._read_document(f)
        self.assertEqual(list(a._doc_cache), paths[-2:])


class HistoryTests(unittest.TestCase):
    def test_only_the_last_two_messages_stay_whole(self):
        a = make()
        big = "가" * 3000
        history = [{"role": "assistant", "content": big} for _ in range(4)]
        text = a._format_history(history)
        self.assertEqual(text.count(big), 2)


class SkillListTests(unittest.TestCase):
    def test_skill_list_is_capped_and_keeps_every_name(self):
        skills = [agent.Skill(name=f"p:s{i}", description="설명 " * 100, body="", path=None, source="x") for i in range(100)]
        text = agent._skill_list(skills)
        self.assertLess(len(text), agent.SKILL_LIST_CHARS + 100 * 40)
        for i in range(100):
            self.assertIn(f"p:s{i}", text)


class RelevantNoteTests(unittest.TestCase):
    def test_short_note_is_untouched(self):
        self.assertEqual(agent._relevant_note("- 짧은 메모", "아무 요청"), "- 짧은 메모")

    def test_long_note_keeps_head_and_matching_lines(self):
        lines = ["# 내 정보", "- 물리학과 3학년"] + [f"- 무관한 항목 번호 {i} " + "가" * 60 for i in range(80)]
        lines.insert(50, "- 졸업논문 지도교수는 김철수 교수님")
        text = "\n".join(lines)
        out = agent._relevant_note(text, "졸업논문 지도교수 이메일 써 줘")
        self.assertIn("물리학과 3학년", out)
        self.assertIn("졸업논문 지도교수는 김철수", out)
        self.assertLess(len(out), agent.NOTE_FULL_CHARS + 200)
        self.assertIn("생략됨", out)


class SharedBigramsTests(unittest.TestCase):
    def test_same_count_as_set_intersection(self):
        import storage

        texts = ["포항공대 수업 공지를 확인해 줘", "Hello, World! 안녕-하세요 3.14", "", "a b c", "ABC abc 가나다라"]
        for q_text in texts:
            q = storage._bigrams(q_text)
            for text in texts:
                with self.subTest(q=q_text, text=text):
                    self.assertEqual(storage.shared_bigrams(q, text), len(q & storage._bigrams(text)))


if __name__ == "__main__":
    unittest.main()
