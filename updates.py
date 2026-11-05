# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""GitHub 릴리스에서 새 버전을 확인하고 이 기기용 설치 파일을 내려받는다.

저장소가 공개라서 GitHub 릴리스(`api.github.com/repos/<저장소>/releases/latest`)를 먼저 본다. GitHub가 막히거나 요청 한도에
걸리면 자체 업데이트 서버(UPDATE_BASE_URL)로 한 번 더 시도한다. 서버는 GitHub와 같은 모양의 JSON과 파일 주소를 준다.
어느 쪽에서 받든 설치 파일은 릴리스를 만든 CI의 Ed25519 서명(`<이름>.sig`)을 앱에 넣은 공개키로
확인한 뒤에만 쓴다. 서명이 없거나 맞지 않으면 설치하지 않는다(건너뛰는 설정은 없다). 크기와 SHA-256(digest)도 함께 확인한다.
"""
import base64
import hashlib
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

REPOSITORY = "pidstech/POSCHAT"  # 소스 코드 주소(설정의 라이선스 정보)와 GitHub 릴리스 확인에 쓴다.
# 보조 업데이트 서버(HTTPS). GitHub에서 받지 못할 때만 쓴다. 1.18.7 이하 앱은 이 서버만 보므로 서버는 계속 서비스한다.
UPDATE_BASE_URL = "https://pidstech.com"
# 서명 공개키(Ed25519 raw 32바이트의 base64). 여러 개를 두면 하나라도 맞을 때 받아들인다(키 교체: docs/security.md).
UPDATE_PUBLIC_KEYS = ("Et1RfxsTZ4VAy/odq+idHpUVPwcvfoHkkp8fPwY4g/A=",)
# Microsoft Store 제품 ID(파트너 센터의 'Store ID', 9N…로 시작). 비어 있으면 Store의 '다운로드 및 업데이트' 화면을 연다.
STORE_PRODUCT_ID = ""
RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
DOWNLOAD_PREFIX = f"https://github.com/{REPOSITORY}/releases/download/"
SERVER_RELEASE_URL = f"{UPDATE_BASE_URL}/api/releases/latest"
SERVER_RELEASES_PAGE = f"{UPDATE_BASE_URL}/"
SERVER_DOWNLOAD_PREFIX = f"{UPDATE_BASE_URL}/releases/download/"
# (피드 주소, 릴리스 페이지, 파일 주소 앞부분). 앞에서부터 시도한다.
SOURCES = (
    (RELEASE_URL, RELEASES_PAGE, DOWNLOAD_PREFIX),
    (SERVER_RELEASE_URL, SERVER_RELEASES_PAGE, SERVER_DOWNLOAD_PREFIX),
)
# GitHub는 릴리스 파일을 이 호스트들로 넘긴다(리디렉션). 이 밖의 주소로는 따라가지 않는다.
# 업데이트 서버가 www 주소로 넘기는 경우도 받아들인다(같은 운영자의 호스트).
_SERVER_HOST = urlparse(UPDATE_BASE_URL).hostname or ""
REDIRECT_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com",
                  "github-releases.githubusercontent.com", _SERVER_HOST, "www." + _SERVER_HOST.removeprefix("www."))
MAX_REDIRECTS = 5
ASSETS = {
    "windows": "POSCHAT-Setup.exe",
    "macos": "POSCHAT-mac.dmg",
    "linux": "POSCHAT-linux-x86_64.AppImage",   # 2.2: Linux(x86_64) AppImage
    "android": "POSCHAT.apk",
}
USER_AGENT = "POSCHAT"
MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024
MAX_SIGNATURE_BYTES = 1024
SIGNATURE_CONTEXT = b"POSCHAT-update-v1"


class UpdateError(Exception):
    pass


def current_platform():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "android" or hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ:
        return "android"
    if sys.platform.startswith("linux"):
        import platform
        return "linux" if platform.machine() in ("x86_64", "AMD64") else "unsupported"   # 배포본은 x86_64만 만든다
    return "unsupported"


def appimage_path():
    """AppImage로 실행 중이면 그 AppImage 파일의 경로(AppImage 런타임이 APPIMAGE에 넣어 준다). 아니면 None."""
    value = os.environ.get("APPIMAGE")
    if not value or not getattr(sys, "frozen", False):
        return None
    path = Path(value)
    return path if path.is_file() else None


def replace_appimage(new_file, target):
    """내려받아 서명까지 확인한 AppImage(new_file)로 실행 중인 AppImage(target)를 바꾼다.

    실행 중인 파일도 같은 폴더에서 이름을 바꿔 덮으면(os.replace) 지금 프로세스는 옛 파일을 계속 쓰고, 다음 실행부터 새 버전이
    뜬다. 다른 파일 시스템에서 바로 옮기면 중간에 끊길 수 있으므로 target 옆에 먼저 복사한 뒤 바꾼다."""
    import shutil
    import stat

    new_file, target = Path(new_file), Path(target)
    staged = target.with_name(f".{target.name}.update")
    try:
        shutil.copyfile(new_file, staged)
        mode = target.stat().st_mode if target.exists() else 0o755
        os.chmod(staged, stat.S_IMODE(mode) | stat.S_IXUSR | stat.S_IRUSR)
        os.replace(staged, target)
    except OSError as e:
        staged.unlink(missing_ok=True)
        raise UpdateError(f"AppImage를 바꾸지 못했습니다({target.parent}에 쓸 수 있는지 확인하세요): {e}") from e
    new_file.unlink(missing_ok=True)
    return target


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", str(value or "").strip())
    if not match:
        raise UpdateError(f"릴리스 버전 형식이 올바르지 않습니다: {value}")
    return tuple(map(int, match.groups()))


def signed_message(tag, name, size, sha256):
    """서명하는 내용: 태그·파일 이름·크기·SHA-256. 다른 버전이나 다른 파일의 서명을 바꿔치기할 수 없다."""
    return b"\n".join([SIGNATURE_CONTEXT, tag.encode(), name.encode(), str(size).encode(), sha256.encode()])


def verify_signature(message, signature, keys=None):
    """signature(base64 문자열)가 공개키 중 하나로 message에 맞는지 확인한다. 아니면 UpdateError."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as e:
        raise UpdateError("서명을 확인할 수 없어 업데이트를 설치하지 않습니다.") from e
    try:
        raw = base64.b64decode(str(signature).strip(), validate=True)
    except ValueError as e:
        raise UpdateError("업데이트 서명 형식이 올바르지 않습니다.") from e
    for key in UPDATE_PUBLIC_KEYS if keys is None else keys:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True)).verify(raw, message)
            return
        except (InvalidSignature, ValueError):
            continue
    raise UpdateError("업데이트 서명이 맞지 않습니다. 설치하지 않습니다.")


def _get(url, **kwargs):
    """requests.get이되 리디렉션은 허용한 https 호스트로만 직접 따라간다."""
    for _ in range(MAX_REDIRECTS + 1):
        r = requests.get(url, allow_redirects=False, **kwargs)
        if r.status_code not in (301, 302, 303, 307, 308):
            return r
        location = r.headers.get("Location") if isinstance(r.headers, dict) or hasattr(r.headers, "get") else None
        if not isinstance(location, str) or not location:
            return r  # 갈 곳을 알려 주지 않으면 그대로 돌려줘 호출한 쪽이 오류로 알린다
        target = urljoin(url, location)
        parts = urlparse(target)
        r.close()
        if parts.scheme != "https" or parts.hostname not in REDIRECT_HOSTS:
            raise UpdateError("업데이트 파일 주소가 허용한 곳이 아닙니다.")
        url = target
    raise UpdateError("업데이트 주소가 너무 많이 넘어갑니다.")


def _fetch_release(feed_url, page_url, download_prefix, timeout):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    try:
        response = _get(feed_url, headers=headers, timeout=(10, timeout))
    except requests.RequestException as e:
        raise UpdateError(f"업데이트 서버에 연결하지 못했습니다: {e}") from e
    if response.status_code == 404:
        raise UpdateError("올라온 릴리스가 아직 없습니다.")
    if response.status_code != 200:
        raise UpdateError(f"업데이트 확인 실패 (HTTP {response.status_code}).")
    try:
        release = response.json()
    except ValueError as e:
        raise UpdateError("업데이트 정보 형식이 올바르지 않습니다.") from e
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        raise UpdateError("정식 릴리스를 찾지 못했습니다.")
    version = str(release.get("tag_name", "")).removeprefix("v")
    version_tuple(version)
    return {
        "version": version,
        "name": str(release.get("name") or f"POSCHAT {version}"),
        "notes": str(release.get("body") or "").strip(),
        "url": page_url,
        "download_prefix": download_prefix,
        "assets": {a.get("name"): a for a in release.get("assets") or [] if isinstance(a, dict)},
    }


def latest_release(timeout=15):
    """최신 정식 릴리스 {"version", "name", "notes", "url", "assets": {이름: asset}}. GitHub가 안 되면 업데이트 서버."""
    error = None
    for feed_url, page_url, download_prefix in SOURCES:
        try:
            return _fetch_release(feed_url, page_url, download_prefix, timeout)
        except UpdateError as e:
            error = error or e  # 첫 오류(GitHub)를 알려 준다
    raise error


def asset_name(release, platform=None):
    """릴리스에 있는 이 기기용 설치 파일 이름(서명 파일이 함께 있을 때만) 또는 None."""
    name = ASSETS.get(platform or current_platform())
    if name and name in release["assets"] and name + ".sig" in release["assets"]:
        return name
    return None


def check(installed_version, platform=None):
    """{"available", "version", "name", "notes", "url", "asset"(이 기기용 파일 이름 또는 None)}."""
    release = latest_release()
    newer = version_tuple(release["version"]) > version_tuple(installed_version)
    return {"available": newer, "version": release["version"], "name": release["name"],
            "notes": release["notes"][:4000], "url": release["url"], "asset": asset_name(release, platform)}


def _asset_url(release, asset, name):
    """릴리스가 알려 준 파일 주소. 이 저장소(또는 업데이트 서버)의 이 버전 폴더 안 이름이 같은 파일만 받아들인다."""
    url = str(asset.get("browser_download_url") or "")
    if url != f"{release['download_prefix']}v{release['version']}/{name}":
        raise UpdateError("업데이트 파일 주소가 이 릴리스의 파일이 아닙니다.")
    return url


def _fetch_signature(url):
    try:
        r = _get(url, headers={"User-Agent": USER_AGENT}, timeout=(15, 30))
    except requests.RequestException as e:
        raise UpdateError(f"업데이트 서명을 내려받지 못했습니다: {e}") from e
    if r.status_code != 200:
        raise UpdateError(f"업데이트 서명을 내려받지 못했습니다 (HTTP {r.status_code}).")
    text = r.text
    if not text.strip() or len(text) > MAX_SIGNATURE_BYTES:
        raise UpdateError("업데이트 서명 형식이 올바르지 않습니다.")
    return text


def download(installed_version, directory, platform=None, on_progress=None, cancelled=None, timeout=15):
    """새 버전의 이 기기용 설치 파일을 받아 서명·크기·SHA-256을 확인한 뒤 directory에 두고 경로를 돌려준다.
    출처(GitHub → 업데이트 서버)마다 피드·서명·파일 받기까지 한 번에 시도하고, 어느 단계든 실패하면 다음 출처로 넘어간다
    (GitHub 파일 서버만 막힌 학교·회사 망). 둘 다 실패하면 첫 오류를 알린다. 사용자가 취소하면 바로 멈춘다."""
    error = None
    for feed_url, page_url, download_prefix in SOURCES:
        try:
            release = _fetch_release(feed_url, page_url, download_prefix, timeout)
            return _download_release(release, installed_version, directory, platform, on_progress, cancelled)
        except UpdateError as e:
            if cancelled and cancelled():
                raise
            error = error or e
    raise error


def _download_release(release, installed_version, directory, platform, on_progress, cancelled):
    if version_tuple(release["version"]) <= version_tuple(installed_version):
        raise UpdateError("이미 최신 버전입니다.")
    name = asset_name(release, platform)
    asset = release["assets"].get(name) if name else None
    if not asset:
        raise UpdateError(f"{release['version']} 릴리스에 이 기기용 설치 파일이나 서명이 없습니다. 릴리스 페이지에서 받으세요.")
    url, size = _asset_url(release, asset, name), asset.get("size")
    if not isinstance(size, int) or not 0 < size <= MAX_DOWNLOAD_BYTES:
        raise UpdateError("업데이트 파일 크기 정보가 올바르지 않습니다.")
    digest = str(asset.get("digest") or "").lower()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise UpdateError("업데이트 파일의 SHA-256 정보가 없습니다. 설치하지 않습니다.")
    expected = digest[len("sha256:"):]
    signature = _fetch_signature(_asset_url(release, release["assets"][name + ".sig"], name + ".sig"))
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path, part = directory / name, directory / (name + ".part")
    sha, done = hashlib.sha256(), 0
    try:
        with _get(url, headers={"User-Agent": USER_AGENT}, timeout=(15, 120), stream=True) as r:
            if r.status_code != 200:
                raise UpdateError(f"업데이트 파일을 내려받지 못했습니다 (HTTP {r.status_code}).")
            with open(part, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if cancelled and cancelled():
                        raise UpdateError("내려받기를 취소했습니다.")
                    done += len(chunk)
                    if done > size:
                        raise UpdateError("업데이트 파일이 예상보다 큽니다.")
                    sha.update(chunk)
                    out.write(chunk)
                    if on_progress:
                        on_progress(done, size)
        if done != size:
            raise UpdateError("업데이트 파일을 끝까지 받지 못했습니다. 다시 시도하세요.")
        if sha.hexdigest() != expected:
            raise UpdateError("내려받은 업데이트 파일이 손상되었습니다(SHA-256 불일치). 다시 시도하세요.")
        verify_signature(signed_message(f"v{release['version']}", name, size, expected), signature)
        os.replace(part, path)  # 서명까지 맞은 파일만 최종 이름이 된다
    except requests.RequestException as e:
        raise UpdateError(f"업데이트 파일을 내려받지 못했습니다: {e}") from e
    finally:
        part.unlink(missing_ok=True)
    return path, release["version"]


def store_url():
    """Store판의 업데이트 안내에서 여는 주소: 제품 페이지(ID가 있으면) 또는 Store의 다운로드 및 업데이트."""
    if STORE_PRODUCT_ID:
        return f"ms-windows-store://pdp/?productid={STORE_PRODUCT_ID}"
    return "ms-windows-store://downloadsandupdates"
