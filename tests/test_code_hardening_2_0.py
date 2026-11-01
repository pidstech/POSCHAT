# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.0 Code 보강: code_project.git의 Git 안전 설정, 하위 폴더 격리 작업의 적용·정리, 패치 바이트 보존, 한글 경로 되돌리기,
품질 검사의 도구 목록, Lab의 로컬 작업 폴더, 명령 정의 파일을 고친 뒤 기억한 규칙, 휴지통 이름 겹침."""
import inspect
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))

import agent  # noqa: E402
import code_agent  # noqa: E402
import code_project  # noqa: E402
import code_workspace as cw  # noqa: E402
import quality_gate  # noqa: E402
from test_code_agent_plus import GIT_ENV, PY, Base, git  # noqa: E402

HAVE_GIT = shutil.which("git") is not None
POSIX = os.name != "nt"


def make_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    return path


def commit_all(path, msg="c"):
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", msg)


@unittest.skipUnless(HAVE_GIT and POSIX, "git·sh가 있어야 합니다")
class GitHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = patch.dict(os.environ, GIT_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.repo = make_repo(self.tmp / "repo")
        (self.repo / "a.txt").write_text("a\n")
        commit_all(self.repo)
        self.marker = self.tmp / "MARK"

    def test_fsmonitor_in_repo_config_does_not_run(self):
        git(self.repo, "config", "core.fsmonitor", f"touch '{self.marker}'; false")
        (self.repo / "a.txt").write_text("b\n")
        g = code_project.git_summary(self.repo)
        self.assertEqual(g["changed_count"], 1)
        code_project.review_diff(self.repo)
        self.assertFalse(self.marker.exists())

    def test_textconv_and_filters_do_not_run(self):
        git(self.repo, "config", "diff.evil.textconv", f"touch '{self.marker}'; cat")
        git(self.repo, "config", "filter.evil.clean", f"touch '{self.marker}'; cat")
        (self.repo / ".gitattributes").write_text("*.txt diff=evil filter=evil\n")
        commit_all(self.repo)
        self.marker.unlink(missing_ok=True)   # 위의 커밋(맨 git)이 남긴 표시는 지운다
        (self.repo / "a.txt").write_text("changed\n")
        self.assertIn("+changed", code_project.review_diff(self.repo))
        wt = self.tmp / "wt"
        base = code_project.worktree_create(self.repo, wt, "poschat/t")
        (wt / "a.txt").write_text("wt\n")
        self.assertIn(b"+wt", code_project.worktree_patch(wt, base))
        self.assertFalse(self.marker.exists())

    def test_worktree_hooks_do_not_run(self):
        hook = self.repo / ".git" / "hooks" / "post-checkout"
        hook.write_text(f"#!/bin/sh\ntouch '{self.marker}'\n")
        hook.chmod(0o755)
        code_project.worktree_create(self.repo, self.tmp / "wt", "poschat/h")
        self.assertFalse(self.marker.exists())


@unittest.skipUnless(HAVE_GIT, "git이 없어 건너뜁니다")
class WorktreeApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = patch.dict(os.environ, GIT_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.repo = make_repo(self.tmp / "repo")
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "a.txt").write_text("a\n")
        (self.repo / "top.txt").write_text("top\n")
        (self.repo / "한글.txt").write_text("하나\n둘\n셋\n", encoding="utf-8")
        (self.repo / "cp.txt").write_bytes("가나다\n".encode("cp949"))
        commit_all(self.repo)
        self.wt = self.tmp / "wt"
        self.base = code_project.worktree_create(self.repo, self.wt, "poschat/w")

    def status(self):
        return subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True).stdout.strip()

    def test_non_utf8_content_survives_as_bytes(self):
        data = "라마바 新\n".encode("cp949")
        (self.wt / "cp.txt").write_bytes(data)
        patch_ = code_project.worktree_patch(self.wt, self.base)
        self.assertIsInstance(patch_, bytes)
        r = code_project.worktree_apply(self.repo, patch_, self.wt)
        self.assertTrue(r["applied"] and r["verified"], r)
        self.assertEqual((self.repo / "cp.txt").read_bytes(), data)

    def test_subfolder_applies_from_toplevel_and_refuses_outside_paths(self):
        sub = self.repo / "sub"
        self.assertEqual(code_project.repo_prefix(sub), "sub/")
        (self.wt / "sub" / "a.txt").write_text("a2\n")
        (self.wt / "sub" / "new.txt").write_text("n\n")
        r = code_project.worktree_apply(sub, code_project.worktree_patch(self.wt, self.base), self.wt)
        self.assertTrue(r["applied"] and r["verified"], r)
        self.assertEqual((sub / "a.txt").read_text(), "a2\n")
        self.assertEqual((sub / "new.txt").read_text(), "n\n")
        # 작업 폴더(sub) 밖을 바꾼 패치는 적용하지 않는다(전에는 말없이 건너뛰고 '적용됨'이라 했다)
        wt2 = self.tmp / "wt2"
        base2 = code_project.worktree_create(self.repo, wt2, "poschat/w2")
        (wt2 / "top.txt").write_text("top2\n")
        (wt2 / "sub" / "a.txt").write_text("a3\n")
        with self.assertRaises(code_project.ProjectError) as e:
            code_project.worktree_apply(sub, code_project.worktree_patch(wt2, base2), wt2)
        self.assertIn("top.txt", str(e.exception))
        self.assertEqual((self.repo / "top.txt").read_text(), "top\n")
        self.assertEqual((sub / "a.txt").read_text(), "a2\n")

    def test_verify_reports_paths_that_did_not_land(self):
        (self.wt / "top.txt").write_text("top2\n")
        r = code_project.worktree_apply(self.repo, code_project.worktree_patch(self.wt, self.base), self.wt)
        self.assertTrue(r["verified"])
        (self.wt / "top.txt").write_text("다른 내용\n")
        self.assertEqual(code_project._verify_applied(self.repo, self.wt, ["top.txt"], False), ["top.txt"])

    def test_quoted_korean_path_listed_and_three_way_rollback(self):
        quoted = b'diff --git "a/\\355\\225\\234\\352\\270\\200.txt" "b/\\355\\225\\234\\352\\270\\200.txt"\n'
        self.assertEqual(code_project.patch_files(quoted), ["한글.txt"])
        (self.wt / "한글.txt").write_text("하나\n둘(격리)\n셋\n", encoding="utf-8")
        patch_ = code_project.worktree_patch(self.wt, self.base)
        # 원래 폴더에서 같은 줄을 바꿔 커밋: 3-way가 겹쳐 실패해야 하고, 한글 파일도 원래대로 남아야 한다
        (self.repo / "한글.txt").write_text("하나\n둘(원래)\n셋\n", encoding="utf-8")
        commit_all(self.repo, "user")
        with self.assertRaises(code_project.ProjectError):
            code_project.worktree_apply(self.repo, patch_, self.wt)
        self.assertEqual((self.repo / "한글.txt").read_text(encoding="utf-8"), "하나\n둘(원래)\n셋\n")
        self.assertEqual(self.status(), b"")


@unittest.skipUnless(HAVE_GIT, "git이 없어 건너뜁니다")
class SubfolderIsolationTests(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.ws
        self.sub = self.repo / "pkg"
        self.sub.mkdir()
        (self.sub / "calc.py").write_text("def add(a, b):\n    return a - b\n")
        git(self.repo, "init", "-q")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "처음")
        env = patch.dict(os.environ, GIT_ENV)
        env.start()
        self.addCleanup(env.stop)
        self.bridge._config["workspace"] = str(self.sub)

    def branches(self):
        return subprocess.run(["git", "branch", "--list", "poschat/*"], cwd=self.repo, capture_output=True, text=True).stdout.strip()

    def test_agent_works_in_the_same_subfolder_and_apply_lands(self):
        task, _ = self.run_task([
            {"action": "edit", "path": "calc.py", "old": "return a - b", "new": "return a + b"},
            {"action": "done", "answer": "끝"}], options={"isolate": True})
        wt = Path(task["worktree"])
        self.assertEqual(task["worktree_sub"], "pkg/")
        self.assertIn("return a + b", (wt / "pkg" / "calc.py").read_text())
        self.assertIn("return a - b", (wt / "calc.py").read_text())   # 저장소 맨 위의 같은 이름 파일은 그대로
        r = self.bridge.code_agent_apply(task["id"])
        self.assertTrue(r["ok"] and r["verified"], r)
        self.assertIn("return a + b", (self.sub / "calc.py").read_text())
        self.assertTrue(r["task"]["worktree_removed"])

    def test_changes_outside_the_subfolder_keep_worktree_and_branch(self):
        task, _ = self.run_task([
            {"action": "edit", "path": "calc.py", "old": "return a - b", "new": "return a + b"},
            {"action": "done", "answer": "끝"}], options={"isolate": True})
        wt = Path(task["worktree"])
        (wt / "outside.txt").write_text("명령이 만든 파일\n")   # 예: 실행한 명령이 작업 폴더 밖에 남긴 변경
        r = self.bridge.code_agent_apply(task["id"])
        self.assertFalse(r["ok"])
        self.assertIn("outside.txt", r["error"])
        self.assertTrue(wt.exists())
        self.assertTrue(self.branches())
        self.assertIn("return a - b", (self.sub / "calc.py").read_text())

    def test_unverified_apply_keeps_worktree_and_branch(self):
        task, _ = self.run_task([
            {"action": "edit", "path": "calc.py", "old": "return a - b", "new": "return a + b"},
            {"action": "done", "answer": "끝"}], options={"isolate": True})
        real = code_project.worktree_apply

        def fake(root, patch_, worktree=None):
            r = real(root, patch_, worktree)
            r.update(verified=False, message="적용했지만 일부 파일이 격리 작업 공간과 달라 남겼습니다: pkg/calc.py")
            return r
        with patch.object(code_project, "worktree_apply", fake):
            r = self.bridge.code_agent_apply(task["id"])
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["task"].get("worktree_removed"))
        self.assertTrue(Path(task["worktree"]).exists())
        self.assertTrue(self.branches())


class CommandDefinitionFileTests(Base):
    def test_remembered_rule_asks_again_after_editing_package_json(self):
        cmd = f"{PY} test_calc.py"
        prefix = code_project.command_prefix(cmd)
        self.assertTrue(prefix)
        self.bridge._ca_add_rule(str(self.ws), prefix)
        (self.ws / "package.json").write_text('{"scripts": {"test": "echo ok"}}\n')
        task, _ = self.run_task([{"action": "run", "command": cmd}, {"action": "done", "answer": "끝"}])
        self.assertEqual(self.confirms(), [])                       # 규칙이 있으면 묻지 않는다
        task, _ = self.run_task([
            {"action": "edit", "path": "package.json", "old": "echo ok", "new": "echo changed"},
            {"action": "run", "command": cmd},
            {"action": "done", "answer": "끝"}], options={"mode": "auto_edit"})
        runs = [c for c in self.confirms() if c["kind"] == "run"]
        self.assertEqual(len(runs), 1)
        self.assertIn("package.json", runs[0]["detail"])
        # 같은 작업의 다음 지시에서도(작업 기록의 변경으로) 다시 묻는다
        self.run_task([{"action": "run", "command": cmd}, {"action": "done", "answer": "끝"}], task_id=task["id"])
        self.assertEqual(len([c for c in self.confirms() if c["kind"] == "run"]), 2)

    def test_pattern(self):
        for rel in ("package.json", "sub/Makefile", "pyproject.toml", "setup.cfg", "tox.ini", "noxfile.py", "tests/conftest.py",
                    "justfile", "Taskfile.yml"):
            self.assertTrue(code_agent.COMMAND_DEF_FILES.search(rel), rel)
        for rel in ("src/app.py", "README.md", "package.json.bak"):
            self.assertFalse(code_agent.COMMAND_DEF_FILES.search(rel), rel)


class QualityGateActionTests(unittest.TestCase):
    def test_every_real_tool_is_an_allowed_action(self):
        names = {n[len("_tool_"):] for cls in (agent.Agent, code_agent.CodeAgent)
                 for n, _ in inspect.getmembers(cls, inspect.isfunction) if n.startswith("_tool_")}
        names.add("done")
        self.assertFalse(names - quality_gate.AGENT_ACTIONS, names - quality_gate.AGENT_ACTIONS)
        for action in ("glob", "multi_edit", "job_output", "job_stop", "web_search", "web_fetch", "paper_search"):
            r = quality_gate.check("agent_step", '{"action": "%s"}' % action, {})
            self.assertTrue(r.ok, (action, r.failures))


class LabLocalWorkspaceTests(Base):
    def test_lab_refuses_when_only_a_remote_workspace_is_open(self):
        import lab_store
        self.addCleanup(lab_store.close)
        (self.ws / "train.py").write_text("print(1)\n")
        exp = self.bridge.lab_experiment_save({"name": "e", "settings": {"kind": "python", "script": "train.py", "params": {}}})
        self.assertTrue(exp["ok"], exp)
        eid = exp["experiment"]["id"]
        self.bridge._config.setdefault("code", {})["remote"] = {"target": "srv", "path": "/home/u/proj"}
        r = self.bridge.lab_run_check(eid, {})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["cwd"], str(self.ws))                    # 원격이 열려 있어도 Lab은 로컬 폴더
        self.bridge._config["workspace"] = ""
        r = self.bridge.lab_run_check(eid, {})
        self.assertFalse(r["ok"])
        self.assertIn("원격(SSH)", r["error"])
        r = self.bridge.lab_run_start(eid, {}, "x")
        self.assertFalse(r["ok"])
        self.assertIn("원격(SSH)", r["error"])


class TrashTests(unittest.TestCase):
    def test_same_path_deleted_twice_in_a_second_keeps_both(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        ws, trash = tmp / "ws", tmp / "trash"
        ws.mkdir()
        dests = []
        with patch.object(cw.time, "strftime", return_value="20261101-120000"):
            for text in ("첫째", "둘째"):
                (ws / "f.txt").write_text(text, encoding="utf-8")
                dests.append(cw.delete_to_trash(ws, "f.txt", trash)["trash"])
        self.assertNotEqual(dests[0], dests[1])
        self.assertEqual([Path(d).read_text(encoding="utf-8") for d in dests], ["첫째", "둘째"])


if __name__ == "__main__":
    unittest.main()
