# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.2 Linux(AppImage): 플랫폼 판별과 설치 파일 이름, AppImage 자동 업데이트(파일 바꾸기), 앱 메뉴 등록, Qt 창 설정, CI 빌드 설정."""
import os
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))

import updates  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class PlatformTests(unittest.TestCase):
    def test_linux_x86_64_gets_the_appimage(self):
        with patch.object(sys, "platform", "linux"), patch("platform.machine", return_value="x86_64"), \
                patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANDROID_ROOT", None)
            self.assertEqual(updates.current_platform(), "linux")
        release = {"assets": {"POSCHAT-linux-x86_64.AppImage": {}, "POSCHAT-linux-x86_64.AppImage.sig": {}}}
        self.assertEqual(updates.asset_name(release, "linux"), "POSCHAT-linux-x86_64.AppImage")
        self.assertIsNone(updates.asset_name({"assets": {"POSCHAT-linux-x86_64.AppImage": {}}}, "linux"))  # 서명 없음

    def test_other_linux_machines_are_not_offered_an_x86_64_file(self):
        with patch.object(sys, "platform", "linux"), patch("platform.machine", return_value="aarch64"):
            os.environ.pop("ANDROID_ROOT", None)
            self.assertEqual(updates.current_platform(), "unsupported")

    def test_appimage_path_only_when_frozen_and_the_file_exists(self):
        with tempfile.TemporaryDirectory() as d:
            app = Path(d, "POSCHAT.AppImage")
            app.write_bytes(b"old")
            with patch.dict(os.environ, {"APPIMAGE": str(app)}):
                self.assertIsNone(updates.appimage_path())   # 소스 실행
                with patch.object(sys, "frozen", True, create=True):
                    self.assertEqual(updates.appimage_path(), app)
            with patch.dict(os.environ, {"APPIMAGE": str(Path(d, "없음"))}), patch.object(sys, "frozen", True, create=True):
                self.assertIsNone(updates.appimage_path())


class ReplaceTests(unittest.TestCase):
    def test_replaces_the_running_file_and_keeps_it_executable(self):
        with tempfile.TemporaryDirectory() as d:
            target, new = Path(d, "apps", "POSCHAT.AppImage"), Path(d, "dl", "POSCHAT-linux-x86_64.AppImage")
            target.parent.mkdir()
            new.parent.mkdir()
            target.write_bytes(b"old")
            target.chmod(0o750)
            new.write_bytes(b"new")
            new.chmod(0o600)
            with open(target, "rb") as running:   # 실행 중인 옛 파일을 연 채로 바꿔도 연 쪽은 옛 내용 그대로
                self.assertEqual(updates.replace_appimage(new, target), target)
                self.assertEqual(running.read(), b"old")
            self.assertEqual(target.read_bytes(), b"new")
            mode = stat.S_IMODE(target.stat().st_mode)
            self.assertTrue(mode & stat.S_IXUSR)
            self.assertEqual(mode & 0o077, 0o050)   # 원래 권한을 따른다
            self.assertFalse(new.exists())
            self.assertEqual(sorted(p.name for p in target.parent.iterdir()), ["POSCHAT.AppImage"])

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root는 읽기 전용 폴더에도 쓴다")
    def test_read_only_folder_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d, "apps")
            folder.mkdir()
            target, new = folder / "POSCHAT.AppImage", Path(d, "new")
            target.write_bytes(b"old")
            new.write_bytes(b"new")
            folder.chmod(0o500)
            try:
                with self.assertRaises(updates.UpdateError):
                    updates.replace_appimage(new, target)
            finally:
                folder.chmod(0o700)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertTrue(new.exists())


class BridgeUpdateTests(unittest.TestCase):
    def setUp(self):
        import main
        from support import isolated_app_dir, preserved_hooks

        self.hooks = preserved_hooks()
        self.hooks.__enter__()
        self.addCleanup(self.hooks.__exit__, None, None, None)
        self.iso = isolated_app_dir()
        self.iso.__enter__()
        self.addCleanup(self.iso.__exit__, None, None, None)
        self.main = main
        self.bridge = main.Bridge()
        self.addCleanup(self.bridge._mcp.shutdown)
        self.addCleanup(self.bridge._events.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name, "POSCHAT.AppImage")
        self.app.write_bytes(b"old")
        self.app.chmod(0o755)

    def test_can_self_update_only_as_an_appimage(self):
        with patch.object(updates, "current_platform", return_value="linux"):
            with patch.dict(os.environ, {"APPIMAGE": str(self.app)}):
                self.assertFalse(self.bridge._can_self_update())   # 소스 실행
                with patch.object(sys, "frozen", True, create=True):
                    self.assertTrue(self.bridge._can_self_update())
            with patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {}, clear=False):
                os.environ.pop("APPIMAGE", None)
                self.assertFalse(self.bridge._can_self_update())   # 배포판 패키지·압축 폴더

    def test_update_work_swaps_the_appimage(self):
        new = Path(self.tmp.name, "dl", "POSCHAT-linux-x86_64.AppImage")
        new.parent.mkdir()
        new.write_bytes(b"new")
        events = []
        with patch.object(updates, "current_platform", return_value="linux"), \
                patch.object(updates, "download", return_value=(new, "9.9.9")), \
                patch.object(sys, "frozen", True, create=True), \
                patch.dict(os.environ, {"APPIMAGE": str(self.app)}), \
                patch.object(self.bridge, "_push", side_effect=events.append), \
                patch.object(self.main, "open_path", side_effect=AssertionError("AppImage는 열지 않고 바꾼다")):
            self.bridge._update_work()
        self.assertEqual(self.app.read_bytes(), b"new")
        self.assertEqual(events[-1]["kind"], "opened")
        self.assertIn("9.9.9", events[-1]["message"])


class DesktopEntryTests(unittest.TestCase):
    def test_registers_and_follows_a_moved_appimage(self):
        import main

        with tempfile.TemporaryDirectory() as d:
            env = {"XDG_DATA_HOME": d, "APPIMAGE": "/home/u/Apps/POSCHAT.AppImage"}
            with patch.dict(os.environ, env):
                os.environ.pop("POSCHAT_NO_DESKTOP_ENTRY", None)
                main._register_desktop_entry()
                entry = Path(d, "applications", "poschat.desktop").read_text(encoding="utf-8")
                self.assertIn('Exec="/home/u/Apps/POSCHAT.AppImage"\n', entry)
                self.assertIn("Icon=poschat\n", entry)
                self.assertTrue(Path(d, "icons", "hicolor", "256x256", "apps", "poschat.png").is_file())
                os.environ["APPIMAGE"] = "/home/u/다른 곳/POSCHAT.AppImage"
                main._register_desktop_entry()
                self.assertIn('Exec="/home/u/다른 곳/POSCHAT.AppImage"\n',
                              Path(d, "applications", "poschat.desktop").read_text(encoding="utf-8"))

    def test_skips_unsafe_names_and_opt_out(self):
        import main

        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {"XDG_DATA_HOME": d, "APPIMAGE": '/tmp/a"b$.AppImage'}):
                main._register_desktop_entry()
            with patch.dict(os.environ, {"XDG_DATA_HOME": d, "APPIMAGE": "/tmp/ok.AppImage", "POSCHAT_NO_DESKTOP_ENTRY": "1"}):
                main._register_desktop_entry()
            self.assertFalse(Path(d, "applications").exists())


class QtSetupTests(unittest.TestCase):
    def test_linux_picks_qt_and_bundled_portaudio(self):
        import ctypes.util
        import main

        original = ctypes.util.find_library
        self.addCleanup(setattr, ctypes.util, "find_library", original)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "libportaudio.so.2").write_bytes(b"")
            keys = ("PYWEBVIEW_GUI", "QT_API", "QTWEBENGINE_DISABLE_SANDBOX", "APPIMAGE")
            with patch.object(sys, "platform", "linux"), patch.object(sys, "frozen", True, create=True), \
                    patch.object(sys, "_MEIPASS", d, create=True), patch.dict(os.environ, {}):
                for k in keys:
                    os.environ.pop(k, None)
                main._prepare_linux()
                self.assertEqual(os.environ["PYWEBVIEW_GUI"], "qt")
                self.assertEqual(os.environ["QT_API"], "pyqt6")
                self.assertEqual(os.environ["QTWEBENGINE_DISABLE_SANDBOX"], "1")
                self.assertEqual(ctypes.util.find_library("portaudio"), str(Path(d, "libportaudio.so.2")))
        ctypes.util.find_library = original
        with patch.object(sys, "platform", "linux"), patch.dict(os.environ, {"QTWEBENGINE_DISABLE_SANDBOX": "0"}):
            os.environ.pop("PYWEBVIEW_GUI", None)
            main._prepare_linux()   # 소스 실행: Qt를 고르지만 샌드박스·PortAudio는 건드리지 않는다
            self.assertEqual(os.environ["QTWEBENGINE_DISABLE_SANDBOX"], "0")
        self.assertIs(ctypes.util.find_library, original)

    def test_other_platforms_are_untouched(self):
        import main

        with patch.object(sys, "platform", "win32"), patch.dict(os.environ, {}):
            os.environ.pop("PYWEBVIEW_GUI", None)
            main._prepare_linux()
            self.assertNotIn("PYWEBVIEW_GUI", os.environ)


class BuildConfigTests(unittest.TestCase):
    def test_ci_builds_signs_and_publishes_the_appimage(self):
        workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        self.assertIn("runs-on: ubuntu-22.04", workflow)
        self.assertIn("--window-check=", workflow)
        self.assertIn("needs: [release-tag, license, tests, ui, windows, macos, linux, browser-spike]", workflow)
        sign = next(line for line in workflow.splitlines() if "update_sign.py sign" in line)
        self.assertIn("dist/POSCHAT-linux-x86_64.AppImage", sign)
        self.assertIn("dist/POSCHAT-linux-x86_64.AppImage.sig", workflow)

    def test_names_match(self):
        import build_installer

        self.assertEqual(build_installer.APPIMAGE_FILE, updates.ASSETS["linux"])
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        for name in ("PyQt6>=", "PyQt6-WebEngine>=", "qtpy>="):
            line = next(x for x in requirements.splitlines() if x.startswith(name))
            self.assertIn('sys_platform == "linux"', line)


if __name__ == "__main__":
    unittest.main()
