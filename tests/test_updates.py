# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import updates

DATA = b"new installer bytes"
KEY = Ed25519PrivateKey.generate()
PUBLIC = base64.b64encode(KEY.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
OTHER_KEY = Ed25519PrivateKey.generate()


def sign(tag="v1.11.0", name="POSCHAT-Setup.exe", data=DATA, key=KEY):
    message = updates.signed_message(tag, name, len(data), hashlib.sha256(data).hexdigest())
    return base64.b64encode(key.sign(message)).decode() + "\n"


def release(version="1.11.0", digest=None, size=None, url=None, names=("POSCHAT-Setup.exe",), signatures=True):
    def asset(name, size, digest=None):
        return {"name": name, "size": size, "browser_download_url": f"{updates.DOWNLOAD_PREFIX}v{version}/{name}",
                **({"digest": digest} if digest else {})}

    assets = []
    for name in names:
        item = asset(name, len(DATA) if size is None else size,
                     digest if digest is not None else "sha256:" + hashlib.sha256(DATA).hexdigest())
        if url:
            item["browser_download_url"] = url
        if digest == "":
            item.pop("digest", None)
        assets.append(item)
        if signatures:
            assets.append(asset(name + ".sig", 90))
    return {"tag_name": f"v{version}", "name": f"POSCHAT v{version}", "body": "notes",
            "html_url": updates.RELEASES_PAGE, "draft": False, "prerelease": False, "assets": assets}


def response(status=200, json_data=None, chunks=None, text=""):
    r = Mock(status_code=status, text=text)
    r.json.return_value = json_data
    r.iter_content.return_value = chunks or [DATA[:5], DATA[5:]]
    r.__enter__ = lambda self: self
    r.__exit__ = Mock(return_value=False)
    return r


def ranged(start, data=None, status=206, total=None):
    """Range 요청(bytes=start-)에 대한 응답."""
    data = DATA[start:] if data is None else data
    r = response(status=status)
    r.iter_content.return_value = [data] if data else []
    r.headers = {"Content-Range": f"bytes {start}-{start + max(len(data), 1) - 1}/{total or len(DATA)}"}
    return r


def broken(data, error=None, start=0):
    """data를 보낸 뒤 연결이 끊기는 응답(start가 있으면 그 위치부터의 206 응답)."""
    def chunks(**_):
        yield data
        raise error or requests.exceptions.ChunkedEncodingError("connection reset")
    r = response(status=206 if start else 200)
    r.headers = {"Content-Range": f"bytes {start}-{len(DATA) - 1}/{len(DATA)}"}
    r.iter_content.side_effect = chunks
    return r


def server_release():
    feed = release()
    for a in feed["assets"]:
        a["browser_download_url"] = a["browser_download_url"].replace(updates.DOWNLOAD_PREFIX, updates.SERVER_DOWNLOAD_PREFIX)
    return feed


def serve(feed, signature=None, body=None):
    """latest_release → 서명 → 파일 순서로 받는 요청에 답한다."""
    return [response(json_data=feed), response(text=sign() if signature is None else signature),
            body or response(), response(503)]   # GitHub에서 실패하면 업데이트 서버 피드로 넘어간다(여기서는 서버도 실패)


@patch.object(updates, "UPDATE_PUBLIC_KEYS", (PUBLIC,))
class UpdateTests(unittest.TestCase):
    @patch("updates.requests.get")
    def test_check_reports_newer_release_and_this_platforms_asset(self, get):
        get.return_value = response(json_data=release())
        result = updates.check("1.10.0", "windows")
        self.assertEqual((result["available"], result["version"], result["asset"]), (True, "1.11.0", "POSCHAT-Setup.exe"))
        self.assertEqual(result["url"], updates.RELEASES_PAGE)
        self.assertFalse(updates.check("1.11.0", "windows")["available"])
        self.assertIsNone(updates.check("1.9.1", "macos")["asset"])  # 이 릴리스에 맥 파일이 없다

    @patch("updates.requests.get")
    def test_asset_without_signature_file_is_not_offered(self, get):
        get.return_value = response(json_data=release(signatures=False))
        self.assertIsNone(updates.check("1.10.0", "windows")["asset"])

    @patch("updates.requests.get")
    def test_requests_never_use_automatic_redirects(self, get):
        get.return_value = Mock(status_code=302, headers={})
        with self.assertRaisesRegex(updates.UpdateError, "HTTP 302"):
            updates.check("1.9.1", "windows")
        self.assertIs(get.call_args.kwargs["allow_redirects"], False)

    @patch("updates.requests.get")
    def test_feed_redirect_to_other_host_is_refused(self, get):
        get.return_value = Mock(status_code=302, headers={"Location": "https://evil.example.com/feed"})
        with self.assertRaisesRegex(updates.UpdateError, "허용한 곳이 아닙니다"):
            updates.check("1.9.1", "windows")

    @patch("updates.requests.get")
    def test_missing_release_is_reported_without_crashing(self, get):
        get.return_value = response(status=404)
        with self.assertRaisesRegex(updates.UpdateError, "아직 없습니다"):
            updates.check("1.9.1", "windows")

    @patch("updates.requests.get")
    def test_unreachable_server_is_reported(self, get):
        get.side_effect = requests.ConnectionError("down")
        with self.assertRaisesRegex(updates.UpdateError, "연결하지 못했습니다"):
            updates.check("1.9.1", "windows")

    @patch("updates.requests.get")
    def test_download_checks_size_sha256_and_signature(self, get):
        with tempfile.TemporaryDirectory() as temp:
            get.side_effect = serve(release())
            path, version = updates.download("1.9.1", temp, "windows")
            self.assertEqual((path.read_bytes(), version), (DATA, "1.11.0"))
            self.assertEqual(path.name, "POSCHAT-Setup.exe")
            self.assertFalse((path.parent / "POSCHAT-Setup.exe.part").exists())

    def assert_refused(self, get, pattern, directory="x"):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / directory
            with self.assertRaisesRegex(updates.UpdateError, pattern):
                updates.download("1.9.1", target, "windows")
            self.assertFalse((target / "POSCHAT-Setup.exe").exists())
            self.assertFalse((target / "POSCHAT-Setup.exe.part").exists())

    @patch("updates.requests.get")
    def test_download_refuses_hash_mismatch(self, get):
        get.side_effect = serve(release(digest="sha256:" + "0" * 64))
        self.assert_refused(get, "SHA-256")

    @patch("updates.requests.get")
    def test_short_file_keeps_the_part_and_reports_resume(self, get):
        """2.3.1: 끝까지 오지 않으면 받은 부분을 남기고(다시 누르면 이어 받는다) 설치 파일은 만들지 않는다."""
        get.side_effect = [response(json_data=release(size=len(DATA) + 10)), response(text=sign()), response()] + \
            [ranged(len(DATA), b"") for _ in range(updates.RESUME_ATTEMPTS)] + [response(503)]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(updates.UpdateError, "이어서"):
                updates.download("1.9.1", temp, "windows")
            self.assertFalse((Path(temp) / "POSCHAT-Setup.exe").exists())
            self.assertEqual((Path(temp) / "POSCHAT-Setup.exe.part").read_bytes(), DATA)

    @patch("updates.requests.get")
    def test_download_refuses_missing_digest(self, get):
        get.side_effect = serve(release(digest=""))
        self.assert_refused(get, "SHA-256 정보가 없습니다")

    @patch("updates.requests.get")
    def test_download_refuses_signature_from_another_key(self, get):
        get.side_effect = serve(release(), signature=sign(key=OTHER_KEY))
        self.assert_refused(get, "서명이 맞지 않습니다")

    @patch("updates.requests.get")
    def test_download_refuses_signature_of_another_version_or_file(self, get):
        get.side_effect = serve(release(), signature=sign(tag="v1.10.9"))
        self.assert_refused(get, "서명이 맞지 않습니다")
        get.side_effect = serve(release(), signature=sign(name="POSCHAT.apk"))
        self.assert_refused(get, "서명이 맞지 않습니다", "y")

    @patch("updates.requests.get")
    def test_download_refuses_tampered_file_even_if_feed_digest_was_changed_too(self, get):
        tampered = b"evil installer bytes"
        get.side_effect = serve(release(digest="sha256:" + hashlib.sha256(tampered).hexdigest(), size=len(tampered)),
                                body=response(chunks=[tampered]))
        self.assert_refused(get, "서명이 맞지 않습니다")

    @patch("updates.requests.get")
    def test_download_refuses_garbage_or_missing_signature(self, get):
        get.side_effect = serve(release(), signature="not base64!!")
        self.assert_refused(get, "형식")
        get.side_effect = [response(json_data=release()), response(status=404), response(503)]
        self.assert_refused(get, "서명을 내려받지 못했습니다", "y")
        get.side_effect = serve(release(signatures=False))
        self.assert_refused(get, "서명이 없습니다", "z")

    @patch("updates.requests.get")
    def test_download_refuses_without_any_public_key(self, get):
        get.side_effect = serve(release())
        with patch.object(updates, "UPDATE_PUBLIC_KEYS", ("",)):
            self.assert_refused(get, "서명이 맞지 않습니다")

    @patch("updates.requests.get")
    def test_second_public_key_allows_key_rotation(self, get):
        get.side_effect = serve(release(), signature=sign(key=OTHER_KEY))
        other = base64.b64encode(OTHER_KEY.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
        with tempfile.TemporaryDirectory() as temp, patch.object(updates, "UPDATE_PUBLIC_KEYS", (PUBLIC, other)):
            self.assertEqual(updates.download("1.9.1", temp, "windows")[0].read_bytes(), DATA)

    @patch("updates.requests.get")
    def test_download_refuses_files_outside_this_server(self, get):
        get.return_value = response(json_data=release(url="https://example.com/POSCHAT-Setup.exe"))
        self.assert_refused(get, "이 릴리스의 파일이 아닙니다")

    @patch("updates.requests.get")
    def test_download_refuses_another_versions_folder(self, get):
        get.return_value = response(json_data=release(url=f"{updates.DOWNLOAD_PREFIX}v9.9.9/POSCHAT-Setup.exe"))
        self.assert_refused(get, "이 릴리스의 파일이 아닙니다")

    @patch("updates.requests.get")
    def test_no_download_when_already_latest(self, get):
        get.return_value = response(json_data=release("1.9.1"))
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(updates.UpdateError, "최신"):
            updates.download("1.9.1", temp, "windows")


class ShippedKeyTests(unittest.TestCase):
    def test_app_ships_a_valid_public_key(self):
        self.assertTrue(updates.UPDATE_PUBLIC_KEYS)
        for key in updates.UPDATE_PUBLIC_KEYS:
            self.assertEqual(len(base64.b64decode(key, validate=True)), 32)

    def test_update_server_uses_https(self):
        self.assertTrue(updates.UPDATE_BASE_URL.startswith("https://"))

    def test_release_sources_are_consistent(self):
        self.assertTrue(updates.RELEASE_URL.startswith("https://api.github.com/repos/" + updates.REPOSITORY))
        self.assertTrue(updates.DOWNLOAD_PREFIX.startswith(f"https://github.com/{updates.REPOSITORY}/"))
        self.assertTrue(updates.SERVER_DOWNLOAD_PREFIX.startswith(updates.UPDATE_BASE_URL))
        self.assertTrue(updates.SERVER_RELEASE_URL.startswith(updates.UPDATE_BASE_URL))


@patch.object(updates, "UPDATE_PUBLIC_KEYS", (PUBLIC,))
class GitHubSourceTests(unittest.TestCase):
    @patch("updates.requests.get")
    def test_checks_github_first(self, get):
        get.return_value = response(json_data=release())
        updates.check("1.10.0", "windows")
        self.assertEqual(get.call_args_list[0].args[0], updates.RELEASE_URL)
        self.assertEqual(get.call_count, 1)

    @patch("updates.requests.get")
    def test_falls_back_to_update_server_when_github_fails(self, get):
        server = release()
        for a in server["assets"]:
            a["browser_download_url"] = a["browser_download_url"].replace(updates.DOWNLOAD_PREFIX, updates.SERVER_DOWNLOAD_PREFIX)
        get.side_effect = [response(403), response(json_data=server)]
        result = updates.check("1.10.0", "windows")
        self.assertEqual((result["available"], result["url"]), (True, updates.SERVER_RELEASES_PAGE))
        self.assertEqual(get.call_args_list[1].args[0], updates.SERVER_RELEASE_URL)

    @patch("updates.requests.get")
    def test_reports_the_github_error_when_both_fail(self, get):
        get.side_effect = [response(403), response(500)]
        with self.assertRaisesRegex(updates.UpdateError, "HTTP 403"):
            updates.latest_release()

    @patch("updates.requests.get")
    def test_download_falls_back_to_update_server_when_github_files_fail(self, get):
        """GitHub 피드는 되지만 파일 서버(release-assets)만 막힌 망: 업데이트 서버에서 피드·서명·파일을 받는다."""
        server = release()
        for a in server["assets"]:
            a["browser_download_url"] = a["browser_download_url"].replace(updates.DOWNLOAD_PREFIX, updates.SERVER_DOWNLOAD_PREFIX)
        get.side_effect = [response(json_data=release()), response(text=sign()), response(403),
                           response(json_data=server), response(text=sign()), response()]
        with tempfile.TemporaryDirectory() as temp:
            path, version = updates.download("1.10.0", temp, "windows")
            self.assertEqual((Path(path).read_bytes(), version), (DATA, "1.11.0"))
        self.assertEqual(get.call_args_list[3].args[0], updates.SERVER_RELEASE_URL)
        self.assertTrue(get.call_args_list[-1].args[0].startswith(updates.SERVER_DOWNLOAD_PREFIX))

    @patch("updates.requests.get")
    def test_cancel_does_not_retry_on_the_update_server(self, get):
        get.side_effect = serve(release())
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(updates.UpdateError, "취소"):
            updates.download("1.10.0", temp, "windows", cancelled=lambda: True)
        self.assertEqual(get.call_count, 3)

    @patch("updates.requests.get")
    def test_update_server_redirect_to_its_www_host_is_allowed(self, get):
        host = updates.urlparse(updates.UPDATE_BASE_URL).hostname
        redirect = Mock(status_code=301, headers={"Location": f"https://www.{host}/api/releases/latest"})
        get.side_effect = [response(403), redirect, response(json_data=release())]
        self.assertEqual(updates.latest_release()["version"], "1.11.0")

    @patch("updates.requests.get")
    def test_download_follows_github_redirect_to_allowed_host(self, get):
        redirect = Mock(status_code=302, headers={"Location": "https://release-assets.githubusercontent.com/x/y"})
        get.side_effect = [response(json_data=release()), response(text=sign()), redirect, response()]
        with tempfile.TemporaryDirectory() as temp:
            path, version = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)
        self.assertEqual(get.call_args_list[-1].args[0], "https://release-assets.githubusercontent.com/x/y")

    @patch("updates.requests.get")
    def test_download_refuses_redirect_to_other_host(self, get):
        redirect = Mock(status_code=302, headers={"Location": "https://evil.example.com/POSCHAT-Setup.exe"})
        get.side_effect = [response(json_data=release()), response(text=sign()), redirect, response(503)]
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(updates.UpdateError, "허용한 곳이 아닙니다"):
            updates.download("1.10.0", temp, "windows")

    @patch("updates.requests.get")
    def test_download_refuses_http_redirect(self, get):
        redirect = Mock(status_code=302, headers={"Location": "http://github.com/x"})
        get.side_effect = [response(json_data=release()), response(text=sign()), redirect, response(503)]
        with tempfile.TemporaryDirectory() as temp, self.assertRaisesRegex(updates.UpdateError, "허용한 곳이 아닙니다"):
            updates.download("1.10.0", temp, "windows")


@patch.object(updates, "UPDATE_PUBLIC_KEYS", (PUBLIC,))
class ResumeTests(unittest.TestCase):
    """2.3.1: 끊기면 이어 받고, 느리거나 막힌 출처에서 받은 부분은 다른 출처에서 이어 받는다."""

    @patch("updates.requests.get")
    def test_resumes_after_a_dropped_connection(self, get):
        get.side_effect = [response(json_data=release()), response(text=sign()), broken(DATA[:7]), ranged(7)]
        with tempfile.TemporaryDirectory() as temp:
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)
            self.assertFalse((Path(temp) / "POSCHAT-Setup.exe.part.id").exists())
        self.assertEqual(get.call_args_list[-1].kwargs["headers"]["Range"], "bytes=7-")
        self.assertNotIn("Range", get.call_args_list[2].kwargs["headers"])

    @patch("updates.requests.get")
    def test_read_timeout_is_short(self, get):
        get.side_effect = serve(release())
        with tempfile.TemporaryDirectory() as temp:
            updates.download("1.10.0", temp, "windows")
        self.assertEqual(get.call_args_list[2].kwargs["timeout"][1], updates.READ_TIMEOUT)
        self.assertLessEqual(updates.READ_TIMEOUT, 30)

    @patch("updates.requests.get")
    def test_switches_to_update_server_and_continues_from_the_part(self, get):
        github_down = [broken(DATA[:5], requests.ConnectionError("reset"))] + \
            [broken(b"", requests.ConnectionError("reset"), start=5) for _ in range(updates.RESUME_ATTEMPTS)]
        get.side_effect = [response(json_data=release()), response(text=sign())] + github_down + \
            [response(json_data=server_release()), response(text=sign()), ranged(5)]
        with tempfile.TemporaryDirectory() as temp:
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)
        last = get.call_args_list[-1]
        self.assertTrue(last.args[0].startswith(updates.SERVER_DOWNLOAD_PREFIX))
        self.assertEqual(last.kwargs["headers"]["Range"], "bytes=5-")

    @patch("updates.requests.get")
    def test_server_without_range_support_restarts_cleanly(self, get):
        get.side_effect = [response(json_data=release()), response(text=sign()), broken(DATA[:4]), response()]
        with tempfile.TemporaryDirectory() as temp:
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)

    @patch("updates.requests.get")
    def test_wrong_content_range_is_refused_and_part_dropped(self, get):
        bad = ranged(3)
        get.side_effect = [response(json_data=release()), response(text=sign()), broken(DATA[:7]), bad, response(503)]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(updates.UpdateError, "다른 부분"):
                updates.download("1.10.0", temp, "windows")
            self.assertFalse((Path(temp) / "POSCHAT-Setup.exe.part").exists())

    @patch("updates.requests.get")
    def test_part_of_another_version_is_not_reused(self, get):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "POSCHAT-Setup.exe.part").write_bytes(b"garbage-from-old")
            (Path(temp) / "POSCHAT-Setup.exe.part.id").write_text("v1.0.0\n1\nx\n", encoding="utf-8")
            get.side_effect = serve(release())
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)
        self.assertNotIn("Range", get.call_args_list[2].kwargs["headers"])

    @patch("updates.requests.get")
    def test_pressing_update_again_resumes_from_the_kept_part(self, get):
        with tempfile.TemporaryDirectory() as temp:
            get.side_effect = [response(json_data=release()), response(text=sign()), broken(DATA[:6])] + \
                [broken(b"", start=6) for _ in range(updates.RESUME_ATTEMPTS)] + [response(503)]
            with self.assertRaisesRegex(updates.UpdateError, "이어서"):
                updates.download("1.10.0", temp, "windows")
            get.side_effect = [response(json_data=release()), response(text=sign()), ranged(6)]
            get.reset_mock()
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)
        self.assertEqual(get.call_args_list[-1].kwargs["headers"]["Range"], "bytes=6-")

    @patch("updates.requests.get")
    def test_cancel_keeps_the_part_for_later(self, get):
        get.side_effect = serve(release())
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(updates.UpdateError, "취소"):
                updates.download("1.10.0", temp, "windows", cancelled=lambda: True)
            self.assertTrue((Path(temp) / "POSCHAT-Setup.exe.part.id").exists())

    @patch("updates.requests.get")
    @patch.object(updates, "SLOW_AFTER", -1)
    @patch.object(updates, "SLOW_BYTES_PER_SEC", 10 ** 12)
    def test_slow_source_hands_over_to_the_next_one(self, get):
        get.side_effect = [response(json_data=release()), response(text=sign()), response(chunks=[DATA[:5], DATA[5:]]),
                           response(json_data=server_release()), response(text=sign()), ranged(5)]
        with tempfile.TemporaryDirectory() as temp:
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)
        self.assertEqual(get.call_args_list[-1].kwargs["headers"]["Range"], "bytes=5-")

    @patch("updates.requests.get")
    @patch.object(updates, "SLOW_AFTER", -1)
    @patch.object(updates, "SLOW_BYTES_PER_SEC", 10 ** 12)
    def test_slow_source_is_finished_when_the_other_one_fails(self, get):
        get.side_effect = [response(json_data=release()), response(text=sign()), response(chunks=[DATA[:5], DATA[5:]]),
                           response(500), response(json_data=release()), response(text=sign()), ranged(5)]
        with tempfile.TemporaryDirectory() as temp:
            path, _ = updates.download("1.10.0", temp, "windows")
            self.assertEqual(Path(path).read_bytes(), DATA)


class CleanupTests(unittest.TestCase):
    def test_removes_finished_installers_and_stale_parts_only(self):
        import os
        import time
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            now = time.time()
            files = {"old.exe": now - 3600, "fresh.exe": now - 10, "a.part": now - 3600, "b.part": now - 8 * 86400}
            for name, mtime in files.items():
                (d / name).write_bytes(b"x")
                os.utime(d / name, (mtime, mtime))
            updates.cleanup(d, now)
            self.assertEqual(sorted(p.name for p in d.iterdir()), ["a.part", "fresh.exe"])
            updates.cleanup(d / "missing", now)   # 폴더가 없어도 조용히 지나간다


if __name__ == "__main__":
    unittest.main()
