# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""Microsoft Store 제출 준비(1.18, EXE 방식): Store판 표시(distribution.txt), Store판은 스스로 업데이트하지 않고 Store로 안내,
Store 설치 파일의 payload, 부적절한 AI 응답 신고(GitHub 이슈 양식) 화면."""
import importlib.util
import os
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.modules.setdefault("webview", types.SimpleNamespace(FOLDER_DIALOG=20))

import updates  # noqa: E402
import version  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HAVE_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
CHROMIUM = os.environ.get("PLAYWRIGHT_CHROMIUM") or ("/opt/pw-browsers/chromium" if os.path.exists("/opt/pw-browsers/chromium") else None)


class DistributionTests(unittest.TestCase):
    def test_store_marker_in_the_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(sys, "_MEIPASS", d, create=True):
                self.assertEqual(version.distribution(), "github")
                Path(d, version.DISTRIBUTION_FILE).write_text("store\n", encoding="utf-8")
                self.assertEqual(version.distribution(), "store")
                Path(d, version.DISTRIBUTION_FILE).write_text("something else", encoding="utf-8")
                self.assertEqual(version.distribution(), "github")
        self.assertEqual(version.distribution(), "github")   # 소스 실행

    def test_store_url(self):
        with patch.object(updates, "STORE_PRODUCT_ID", ""):
            self.assertEqual(updates.store_url(), "ms-windows-store://downloadsandupdates")
        with patch.object(updates, "STORE_PRODUCT_ID", "9NTEST123"):
            self.assertEqual(updates.store_url(), "ms-windows-store://pdp/?productid=9NTEST123")

    def test_store_payload_carries_the_marker_and_the_github_one_does_not(self):
        import build_installer

        with tempfile.TemporaryDirectory() as d:
            app = Path(d, "app")
            (app / "_internal").mkdir(parents=True)
            (app / "PostechChat.exe").write_bytes(b"MZ")
            (app / "_internal" / "python312.dll").write_bytes(b"MZ")
            build_installer.zip_app(app, Path(d, "github.zip"))
            build_installer.zip_app(app, Path(d, "store.zip"), extra={f"_internal/{version.DISTRIBUTION_FILE}": "store\n"})
            with zipfile.ZipFile(Path(d, "github.zip")) as z:
                self.assertEqual(sorted(z.namelist()), ["PostechChat.exe", "_internal/python312.dll"])
            with zipfile.ZipFile(Path(d, "store.zip")) as z:
                self.assertEqual(z.read("_internal/distribution.txt"), b"store\n")
        self.assertEqual(build_installer.STORE_SETUP_FILE, "POSCHAT-Store-Setup.exe")

    def test_sign_tree_does_nothing_without_a_certificate(self):
        import build_installer

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("WINDOWS_SIGN_PFX", None)
            with patch.object(build_installer.subprocess, "run", side_effect=AssertionError("signtool을 부르면 안 됨")):
                build_installer.sign_tree(ROOT)

    def test_issue_form_matches_the_app(self):
        """앱(web/app.js)이 채우는 필드 id가 이슈 양식에 있어야 한다."""
        import re

        form = (ROOT / ".github" / "ISSUE_TEMPLATE" / "ai-report.yml").read_text(encoding="utf-8")   # PyYAML 없이 읽는다
        ids = set(re.findall(r"(?m)^\s+id: (\w+)$", form))
        self.assertTrue({"reason", "what", "response", "model", "version"} <= ids)
        block = form.split("options:", 1)[1].split("validations:", 1)[0]
        reasons = re.findall(r"(?m)^\s+- (.+)$", block)
        self.assertEqual(len(reasons), 6)
        app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        for r in reasons:
            self.assertIn(f'"{r}"', app)


class MsixTests(unittest.TestCase):
    """2.0.1 Microsoft Store(MSIX 방식): Store가 다시 서명하므로 인증서 없이 낼 수 있고, Store판으로 표시된다."""

    def manifest(self, identity=None):
        import xml.dom.minidom

        import build_installer
        ident = identity or build_installer.msix_identity()
        return xml.dom.minidom.parseString(build_installer.msix_manifest("2.0.1", ident).encode("utf-8"))

    def test_manifest_is_a_full_trust_desktop_app(self):
        doc = self.manifest()
        app = doc.getElementsByTagName("Application")[0]
        self.assertEqual(app.getAttribute("Executable"), "PostechChat.exe")
        self.assertEqual(app.getAttribute("EntryPoint"), "Windows.FullTrustApplication")
        self.assertEqual(doc.getElementsByTagName("Identity")[0].getAttribute("Version"), "2.0.1.0")
        self.assertEqual(doc.getElementsByTagName("Identity")[0].getAttribute("ProcessorArchitecture"), "x64")
        caps = [e.getAttribute("Name") for e in doc.getElementsByTagName("Capabilities")[0].childNodes if e.nodeType == 1]
        self.assertIn("runFullTrust", caps)
        self.assertIn("microphone", caps)    # PO노트 녹음
        self.assertEqual(doc.getElementsByTagName("desktop:ExecutionAlias")[0].getAttribute("Alias"), "poschat.exe")

    def test_identity_comes_from_partner_center_values_and_is_escaped(self):
        import build_installer

        env = {"MSIX_IDENTITY_NAME": "12345PIDSTech.POSCHAT", "MSIX_PUBLISHER": 'CN=1A2B-3C, O="A & B"',
               "MSIX_PUBLISHER_DISPLAY_NAME": "PIDS <Tech>"}
        with patch.dict(os.environ, env):
            doc = self.manifest(build_installer.msix_identity())
        ident = doc.getElementsByTagName("Identity")[0]
        self.assertEqual(ident.getAttribute("Name"), "12345PIDSTech.POSCHAT")
        self.assertEqual(ident.getAttribute("Publisher"), 'CN=1A2B-3C, O="A & B"')
        self.assertEqual(doc.getElementsByTagName("PublisherDisplayName")[0].firstChild.data, "PIDS <Tech>")
        with patch.dict(os.environ, {"MSIX_IDENTITY_NAME": "", "MSIX_PUBLISHER": "  "}):
            self.assertEqual(build_installer.msix_identity()["publisher"], "CN=POSCHAT Test")   # 시험용

    def test_store_requires_the_last_version_part_to_be_zero(self):
        import build_installer

        self.assertEqual(build_installer.msix_version(version.APP_VERSION), version.APP_VERSION + ".0")
        for bad in ("2.0", "2.0.0.1", "2.0.x", "70000.0.0"):
            with self.assertRaises(ValueError):
                build_installer.msix_version(bad)

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow 없음")
    def test_layout_marks_the_store_build_and_has_every_logo_the_manifest_names(self):
        import build_installer

        with tempfile.TemporaryDirectory() as d:
            app = Path(d, "app")
            (app / "_internal").mkdir(parents=True)
            (app / "PostechChat.exe").write_bytes(b"MZ")
            layout = build_installer.msix_layout(app, Path(d, "msix"), "2.0.1", build_installer.msix_identity())
            self.assertEqual((layout / "_internal" / "distribution.txt").read_text(encoding="utf-8"), "store\n")
            self.assertFalse((app / "_internal" / "distribution.txt").exists())   # GitHub판 폴더는 그대로
            text = (layout / "AppxManifest.xml").read_text(encoding="utf-8")
            for ref in ("Assets\\StoreLogo.png", "Assets\\Square44x44Logo.png", "Assets\\Square150x150Logo.png"):
                self.assertIn(ref, text)
                self.assertTrue((layout / ref.replace("\\", "/")).is_file(), ref)
            from PIL import Image
            for name, size in build_installer.MSIX_LOGOS.items():
                with Image.open(layout / "Assets" / name) as im:
                    self.assertEqual(im.size, (size, size))

    def test_unsigned_msix_is_not_published_to_releases(self):
        workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
        create = workflow[workflow.index("gh release create"):]
        create = create[:create.index("--notes-file")]
        self.assertNotIn(".msix", create)        # 서명하지 않은 MSIX는 Windows가 설치하지 않는다
        self.assertIn("release/POSCHAT.msix", workflow)   # CI 산출물로 남겨 파트너 센터에 올린다


class StoreUpdateTests(unittest.TestCase):
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
        self.release = {"available": True, "version": "99.0.0", "notes": "", "asset": {"name": "POSCHAT-Setup.exe"}}

    def test_store_build_points_to_the_store_and_never_downloads(self):
        with patch.object(version, "distribution", return_value="store"), \
                patch.object(updates, "check", return_value=dict(self.release)), \
                patch.object(updates, "current_platform", return_value="windows"), \
                patch.object(sys, "frozen", True, create=True):
            r = self.bridge.check_for_updates(manual=True)
            self.assertTrue(r["store"])
            self.assertFalse(r["can_install"])
            with patch.object(updates, "download", side_effect=AssertionError("Store판은 받지 않는다")):
                d = self.bridge.download_update()
            self.assertFalse(d["ok"])
            self.assertEqual(self.bridge.get_state()["distribution"], "store")
        with patch.object(self.main, "open_path") as op:
            self.assertTrue(self.bridge.open_store_updates()["ok"])
            op.assert_called_once_with(updates.store_url())

    def test_github_build_still_updates_itself(self):
        with patch.object(updates, "check", return_value=dict(self.release)), \
                patch.object(updates, "current_platform", return_value="windows"), \
                patch.object(sys, "frozen", True, create=True):
            r = self.bridge.check_for_updates(manual=True)
        self.assertFalse(r["store"])
        self.assertTrue(r["can_install"])


@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright가 없어 화면 점검을 건너뜁니다")
class ReportUiTests(unittest.TestCase):
    def test_report_opens_a_prefilled_github_issue_and_store_update_notice(self):
        import ui_harness
        from playwright.sync_api import sync_playwright
        from support import isolated_app_dir, preserved_hooks

        with preserved_hooks(), isolated_app_dir() as data_dir:
            bridge, events = ui_harness.make_bridge(data_dir)
            bridge.save_settings({"api_key": "test-key"})
            server = ui_harness.serve(bridge, events)
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(**({"executable_path": CHROMIUM} if CHROMIUM else {}))
                    page = browser.new_page(viewport={"width": 1200, "height": 800})
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.add_init_script(ui_harness.INIT_SCRIPT)
                    page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
                    page.wait_for_selector("#btn-new")
                    # 채팅 답변의 신고 단추
                    page.evaluate("""() => { const m = { id: 'm1', role: 'assistant', content: '문제가 된 답변 **내용**' };
                      document.querySelector('#messages, #scroll').append(messageNode(m)); }""")
                    page.click(".msg.assistant .report-btn")
                    page.wait_for_selector(".modal:has-text('누구나 볼 수 있습니다')")
                    self.assertTrue(page.is_hidden("#report-response"))     # 답변은 고를 때만 넣는다
                    page.select_option("#report-reason", "개인정보 노출")
                    page.fill("#report-note", "전화번호를 지어냈습니다")
                    page.check("#report-include")
                    page.fill("#report-response", "고친 답변")
                    opened = []   # 실제로 GitHub에 가지 않고 연 주소만 잡는다

                    def fake_github(route):
                        opened.append(route.request.url)
                        route.fulfill(status=200, body="ok")
                    page.context.route("https://github.com/**", fake_github)
                    with page.expect_popup() as pop:
                        page.click(".modal-foot button:has-text('GitHub에서 신고 열기')")
                    pop.value.wait_for_load_state()
                    pop.value.close()
                    url = urlparse(opened[0])
                    q = {k: v[0] for k, v in parse_qs(url.query).items()}
                    self.assertEqual(url.netloc + url.path, "github.com/pidstech/POSCHAT/issues/new")
                    self.assertEqual(q["template"], "ai-report.yml")
                    self.assertEqual(q["reason"], "개인정보 노출")
                    self.assertEqual(q["what"], "전화번호를 지어냈습니다")
                    self.assertEqual(q["response"], "고친 답변")
                    self.assertIn(version.APP_VERSION, q["version"])
                    # 답변을 넣지 않으면 response가 비어 있다
                    url2 = page.evaluate("() => reportUrl({ reason: '그 밖의 문제', note: '', response: '', model: 'auto' })")
                    self.assertEqual(parse_qs(urlparse(url2).query).get("response"), None)
                    # Store판 업데이트 안내: 받기 대신 Microsoft Store 열기
                    page.evaluate("() => offerUpdate({ version: '99.0.0', current: '1.0.0', store: true, can_install: false })")
                    page.wait_for_selector(".modal:has-text('Microsoft Store로 설치한 앱')")
                    self.assertEqual(page.locator(".modal-foot button:has-text('Microsoft Store 열기')").count(), 1)
                    self.assertEqual(page.locator(".modal-foot button:text-is('업데이트')").count(), 0)
                    self.assertEqual(errors, [])
                    browser.close()
            finally:
                server.shutdown()
                server.server_close()
                bridge._code_shutdown()
                bridge._events.stop()
                bridge._mcp.shutdown()


if __name__ == "__main__":
    unittest.main()
