# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""앱과 설치 프로그램을 빌드한다.

    python build_installer.py

필요 패키지: requirements.txt와 pyinstaller (pip install -r requirements.txt pyinstaller)
결과: Windows는 release/POSCHAT-Setup.exe와 release/POSCHAT-Store-Setup.exe(Microsoft Store 제출용, 1.18),
macOS는 release/POSCHAT-mac.dmg(앱 아이콘을 위해 pillow도 필요),
Linux(x86_64)는 release/POSCHAT-linux-x86_64.AppImage(2.2. PortAudio(libportaudio2)와 appimagetool이 필요하다. build_linux 참고)
빌드 중간 파일은 %TEMP%\\PostechChat-build 에 만든다(클라우드 동기화 폴더에서 빌드하면 느리다).

1.11부터 앱 이름은 POSCHAT이다. 설치 폴더·실행 파일(PostechChat.exe, PostechChat.app)·데이터 폴더 이름은
이전 버전에서 그대로 업데이트되도록 바꾸지 않고, 화면·바로가기·설치 목록·파일 정보에 보이는 이름만 바꾼다.
"""
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import version

ROOT = Path(__file__).resolve().parent
APP_NAME = "POSCHAT"
SETUP_FILE = "POSCHAT-Setup.exe"
# Microsoft Store 제출용(EXE 방식): 앱이 스스로 업데이트하지 않고 Store로 안내한다(version.distribution).
# Store는 설치 파일과 그 안의 모든 PE 파일(exe·dll·pyd)이 신뢰받는 CA의 인증서로 서명돼 있어야 받는다(정책 10.2.9).
STORE_SETUP_FILE = "POSCHAT-Store-Setup.exe"
PE_SUFFIXES = (".exe", ".dll", ".pyd")
DMG_FILE = "POSCHAT-mac.dmg"
APPIMAGE_FILE = "POSCHAT-linux-x86_64.AppImage"
WORK = Path(tempfile.gettempdir()) / "PostechChat-build"
ICON = ROOT / "assets" / "icon.ico"
ICON_PNG = ROOT / "assets" / "icon.png"
BUNDLE_ID = "io.github.bj0322.poschat"
APP_DATA = [
    "--add-data", f"{ROOT / 'web'}{os.pathsep}web",
    "--add-data", f"{ROOT / 'skills'}{os.pathsep}skills",
    "--add-data", f"{ROOT / 'LICENSE'}{os.pathsep}.",
    "--add-data", f"{ROOT / 'THIRD_PARTY_NOTICES.md'}{os.pathsep}.",
    "--add-data", f"{ROOT / 'licenses'}{os.pathsep}licenses",
    # 1.18 SSH 원격 작업 폴더: 서버로 보내 실행할 원격 도우미 소스(remote_client.bundle이 읽는다)
    *[x for name in ("remote_fs", "code_workspace", "code_git", "code_project", "remote_helper")
      for x in ("--add-data", f"{ROOT / (name + '.py')}{os.pathsep}remote")],
    # python-docx·python-pptx는 새 문서를 만들 때 패키지 안의 기본 서식 파일을 쓴다.
    "--collect-data", "docx", "--collect-data", "pptx",
    # PO노트 음성 인식: sherpa-onnx는 onnxruntime 등 공유 라이브러리를 sherpa_onnx/lib에 둔다.
    # sounddevice의 PortAudio는 PyInstaller 훅이 함께 넣는다.
    "--collect-binaries", "sherpa_onnx",
    # 1.11 개인 Claude API: Anthropic SDK는 리소스 모듈 일부를 처음 쓸 때 불러오므로 하위 모듈을 모두 넣는다.
    "--collect-submodules", "anthropic",
]


# 1.19 설치 파일 줄이기: 앱이 쓰지 않는데 다른 패키지를 따라 들어오던 모듈을 뺀다(1.18.9 Windows 설치 파일 기준 압축 전 약 10MB).
# - Pillow의 AVIF 코덱(_avif, 7.5MB): python-pptx가 Pillow를 쓰지만 AVIF 그림은 다루지 않는다. Pillow는 없으면 건너뛴다.
# - setuptools·pkg_resources: 패키지를 만들 때만 쓰는 도구. 앱 코드는 불러오지 않는다.
APP_EXCLUDES = [x for name in ("PIL.AvifImagePlugin", "PIL._avif", "setuptools", "pkg_resources", "_distutils_hack")
                for x in ("--exclude-module", name)]


def dependency_licenses():
    """번들에 들어가는 Python 패키지의 라이선스 원문을 모아 licenses/python/으로 넣는 PyInstaller 인자."""
    sys.path.insert(0, str(ROOT / "tools"))
    import license_check
    dest = WORK / "pylicenses"
    license_check.collect(dest)
    return ["--add-data", f"{dest}{os.pathsep}licenses/python"]


def version_file(file_name, description):
    """Windows 실행 파일의 파일 정보(작업 관리자·속성 창에 보이는 이름과 버전)를 PyInstaller 형식으로 만든다."""
    from version import APP_VERSION

    numbers = tuple(int(x) for x in APP_VERSION.split(".")) + (0,)
    strings = {"CompanyName": "PIDS Tech.", "FileDescription": description, "FileVersion": APP_VERSION,
               "InternalName": APP_NAME, "LegalCopyright": "Copyright © 2026 Beomjoon Kim (AGPL-3.0-only)",
               "OriginalFilename": file_name, "ProductName": APP_NAME, "ProductVersion": APP_VERSION}
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041204B0', [{", ".join(f"StringStruct({k!r}, {v!r})" for k, v in strings.items())}])]),
    VarFileInfo([VarStruct('Translation', [1042, 1200])])
  ]
)
"""
    path = WORK / f"version-{file_name}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def pyinstaller(*args):
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN",
        "--workpath", str(WORK / "work"), "--specpath", str(WORK / "spec"), *args,
    ], check=True)


def build_mac():
    """PostechChat.app을 만들고 '응용 프로그램'으로 끌어다 놓는 디스크 이미지(.dmg)로 묶는다."""
    from version import APP_VERSION

    print("[1/2] 앱 빌드")
    pyinstaller(
        "--windowed", "--onedir", "--name", "PostechChat", "--icon", str(ICON_PNG),
        "--osx-bundle-identifier", BUNDLE_ID, *APP_DATA, *APP_EXCLUDES, *dependency_licenses(),
        "--distpath", str(WORK / "app"),
        str(ROOT / "main.py"),
    )
    app = WORK / "app" / "PostechChat.app"
    plist_path = app / "Contents" / "Info.plist"
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
    plist.update(CFBundleDisplayName=APP_NAME, CFBundleName=APP_NAME, CFBundleShortVersionString=APP_VERSION,
                 CFBundleVersion=APP_VERSION, NSHighResolutionCapable=True,
                 # PO노트 녹음. 이 문구가 없으면 macOS가 마이크를 묻지도 않고 막는다.
                 NSMicrophoneUsageDescription="PO노트에서 강의를 녹음해 받아 적으려면 마이크가 필요합니다.")
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)
    # Info.plist를 바꾸면 서명이 깨지므로 다시 임시(ad-hoc) 서명한다. Apple Silicon은 서명 없는 앱을 실행하지 않는다.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)

    print("[2/2] 디스크 이미지 만들기")
    stage = WORK / "dmg"
    stage.mkdir()
    shutil.copytree(app, stage / app.name, symlinks=True)
    (stage / "Applications").symlink_to("/Applications")
    # 디스크 이미지를 열면 바로 보이도록 라이선스 전문(AGPL-3.0-only)과 제3자 고지를 함께 둔다(앱 안에도 들어 있다)
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", stage / "THIRD_PARTY_NOTICES.md")
    out = ROOT / "release"
    out.mkdir(exist_ok=True)
    target = out / DMG_FILE
    target.unlink(missing_ok=True)
    subprocess.run(["hdiutil", "create", "-volname", APP_NAME, "-srcfolder", str(stage),
                    "-ov", "-format", "UDZO", str(target)], check=True)
    print(f"완료: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")


def _portaudio_library():
    """시스템의 PortAudio 공유 라이브러리 경로. Linux의 sounddevice 패키지는 PortAudio를 싣지 않으므로 앱에 함께 넣는다."""
    import ctypes.util
    name = ctypes.util.find_library("portaudio")
    if not name:
        return None
    if os.path.isabs(name):
        return Path(name)
    for folder in ("/usr/lib/x86_64-linux-gnu", "/usr/lib64", "/usr/lib", "/lib/x86_64-linux-gnu"):
        if (Path(folder) / name).exists():
            return (Path(folder) / name).resolve()
    return None


def _appimagetool():
    """appimagetool 실행 경로: APPIMAGETOOL 환경 변수 또는 PATH."""
    tool = os.environ.get("APPIMAGETOOL") or shutil.which("appimagetool") or shutil.which("appimagetool-x86_64.AppImage")
    if not tool:
        sys.exit("appimagetool을 찾지 못했습니다. https://github.com/AppImage/appimagetool/releases 에서 받아\n"
                 "  APPIMAGETOOL=/경로/appimagetool-x86_64.AppImage python build_installer.py 로 실행하세요.")
    return tool


def build_linux():
    """2.2: PostechChat 앱 폴더를 만들고 실행 파일 하나짜리 AppImage로 묶는다.

    창은 pywebview의 Qt 방식(PyQt6-WebEngine, pip 패키지에 Qt가 함께 들어 있다)으로 띄워 배포판의 WebKitGTK에 기대지 않는다.
    빌드한 컴퓨터보다 glibc가 오래된 배포판에서는 돌지 않으므로 CI는 ubuntu-22.04(glibc 2.35)에서 빌드한다."""
    from version import APP_VERSION

    portaudio = _portaudio_library()
    if not portaudio:
        sys.exit("PortAudio 라이브러리를 찾지 못했습니다. 예) sudo apt install libportaudio2")
    tool = _appimagetool()

    print("[1/2] 앱 빌드")
    pyinstaller(
        "--windowed", "--onedir", "--name", "PostechChat", *APP_DATA, *APP_EXCLUDES, *dependency_licenses(),
        "--add-data", f"{ICON_PNG}{os.pathsep}assets",   # 앱 메뉴 등록(main._register_desktop_entry)에 쓰는 아이콘
        "--add-binary", f"{portaudio}{os.pathsep}.",     # main._prepare_linux가 sounddevice에 이 파일을 알려 준다
        # pywebview는 Qt 모듈을 qtpy를 거쳐 실행 중에 불러오므로 PyInstaller가 따라가지 못한다. Qt WebEngine까지 직접 알려 준다
        *[x for name in ("webview.platforms.qt", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore", "PyQt6.QtWebChannel",
                         "PyQt6.QtNetwork", "PyQt6.QtPrintSupport")
          for x in ("--hidden-import", name)],
        "--collect-submodules", "qtpy",
        "--exclude-module", "webview.platforms.gtk", "--exclude-module", "gi",   # 배포본은 Qt만 쓴다
        "--distpath", str(WORK / "app"),
        str(ROOT / "main.py"),
    )
    app_dir = WORK / "app" / "PostechChat"

    print("[2/2] AppImage 만들기")
    appdir = WORK / "AppDir"
    shutil.copytree(app_dir, appdir / "usr" / "lib" / "poschat", symlinks=True)
    run = appdir / "AppRun"
    run.write_text('#!/bin/sh\nHERE="$(dirname "$(readlink -f "$0")")"\nexec "$HERE/usr/lib/poschat/PostechChat" "$@"\n',
                   encoding="utf-8")
    run.chmod(0o755)
    (appdir / "poschat.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=POSCHAT\nComment=POSTECH GenAI 채팅\nExec=PostechChat\nIcon=poschat\n"
        f"Terminal=false\nCategories=Office;Education;Chat;\nStartupWMClass=POSCHAT\nX-AppImage-Version={APP_VERSION}\n",
        encoding="utf-8")
    shutil.copy2(ICON_PNG, appdir / "poschat.png")
    (appdir / ".DirIcon").symlink_to("poschat.png")
    # AppImage를 풀었을 때도 보이도록 라이선스 전문과 제3자 고지를 맨 위에 둔다(앱 안에도 들어 있다)
    shutil.copy2(ROOT / "LICENSE", appdir / "LICENSE.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", appdir / "THIRD_PARTY_NOTICES.md")
    out = ROOT / "release"
    out.mkdir(exist_ok=True)
    target = out / APPIMAGE_FILE
    target.unlink(missing_ok=True)
    # CI 러너처럼 FUSE가 없는 곳에서도 appimagetool(AppImage)이 돌도록 풀어서 실행하게 한다
    env = dict(os.environ, ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1")
    subprocess.run([tool, "--no-appstream", str(appdir), str(target)], check=True, env=env)
    target.chmod(0o755)
    print(f"완료: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")


def main():
    if sys.platform == "darwin":
        if WORK.exists():
            shutil.rmtree(WORK)
        return build_mac()
    if sys.platform.startswith("linux"):
        if WORK.exists():
            shutil.rmtree(WORK)
        return build_linux()
    if (Path(sys.base_prefix) / "conda-meta").is_dir():
        # conda의 OpenSSL은 실행 파일에 OPENSSL_Applink가 있어야 해서, PyInstaller exe에서는
        # HTTPS 요청 때 "OPENSSL_Uplink: no OPENSSL_Applink"로 프로세스가 꺼진다.
        sys.exit("Anaconda/conda Python으로는 빌드할 수 없습니다. python.org 공식 Python 3.11 이상으로 실행하세요.\n"
                 "  예) py -3.12 -m venv .buildenv && .buildenv\\Scripts\\python -m pip install -r requirements.txt pyinstaller\n"
                 "      .buildenv\\Scripts\\python build_installer.py")
    try:
        import tkinter  # noqa: F401  설치 프로그램 화면에 필요
    except ImportError:
        sys.exit("이 Python에는 tkinter가 없습니다. python.org 설치 프로그램으로 설치한 Python(tcl/tk 포함)을 쓰세요.")
    if WORK.exists():
        shutil.rmtree(WORK)

    print("[1/3] 앱 빌드")
    pyinstaller(
        "--windowed", "--onedir", "--name", "PostechChat", "--icon", str(ICON), *APP_DATA, *APP_EXCLUDES, *dependency_licenses(),
        "--collect-all", "winpty",  # 1.18 터미널: ConPTY 확장 모듈·conpty.dll·OpenConsole.exe(terminal.py가 필요할 때 가져온다)
        "--version-file", version_file("PostechChat.exe", APP_NAME),
        "--distpath", str(WORK / "app"),
        str(ROOT / "main.py"),
    )
    app_dir = WORK / "app" / "PostechChat"
    sign_tree(app_dir)  # 1.18: 앱의 exe뿐 아니라 아직 서명되지 않은 dll·pyd까지(Store 정책)

    print("[2/3] 앱 압축")
    payload = WORK / "payload.zip"
    zip_app(app_dir, payload)
    store_payload = WORK / "store" / "payload.zip"   # Store판: 같은 앱 + _internal/distribution.txt("store")
    store_payload.parent.mkdir(parents=True, exist_ok=True)
    zip_app(app_dir, store_payload, extra={f"_internal/{version.DISTRIBUTION_FILE}": "store\n"})

    print("[3/3] 설치 프로그램 빌드")
    out = ROOT / "release"
    out.mkdir(exist_ok=True)
    for name, data, label in ((SETUP_FILE, payload, "setup"), (STORE_SETUP_FILE, store_payload, "store-setup")):
        pyinstaller(
            "--windowed", "--onefile", "--name", "PostechChat-Setup", "--icon", str(ICON),
            "--version-file", version_file(name, f"{APP_NAME} 설치 프로그램"),
            "--add-data", f"{data};.",
            "--add-data", f"{ICON};.",
            "--add-data", f"{ICON_PNG};.",
            "--paths", str(ROOT),  # installer.py가 저장소 최상위의 version.py를 가져온다
            "--distpath", str(WORK / label),
            str(ROOT / "installer" / "installer.py"),
        )
        target = out / name
        shutil.copy2(WORK / label / "PostechChat-Setup.exe", target)
        sign(target)
        print(f"완료: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB)")


def zip_app(app_dir, target, extra=None):
    """앱 폴더를 설치 프로그램에 넣을 payload.zip으로. extra: {zip 안 경로: 글} — 더 넣을 파일."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(app_dir).as_posix())
        for name, text in (extra or {}).items():
            zf.writestr(name, text)


def signtool():
    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    tools = sorted(kits.glob("*/x64/signtool.exe"))
    if not tools:
        sys.exit("signtool.exe를 찾지 못했습니다. Windows SDK를 설치하세요.")
    return str(tools[-1])


def sign(*paths):
    """코드 서명 인증서가 있으면 Windows 실행 파일에 서명한다(SmartScreen '알 수 없는 게시자' 경고를 줄인다).

    WINDOWS_SIGN_PFX(.pfx 파일 경로)와 WINDOWS_SIGN_PASSWORD 환경 변수가 있을 때만 서명한다. 없으면 건너뛴다.
    """
    pfx = os.environ.get("WINDOWS_SIGN_PFX")
    if not pfx or not paths:
        return
    tool = signtool()
    for i in range(0, len(paths), 50):   # 명령 줄 길이 제한
        batch = [str(p) for p in paths[i:i + 50]]
        subprocess.run([tool, "sign", "/f", pfx, "/p", os.environ.get("WINDOWS_SIGN_PASSWORD", ""),
                        "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256",
                        "/d", APP_NAME, *batch], check=True, stdout=subprocess.DEVNULL)
    print(f"서명: {', '.join(Path(p).name for p in paths[:3])}{f' 외 {len(paths) - 3}개' if len(paths) > 3 else ''}")


def signed(path):
    """이미 믿을 수 있는 서명(예: python.org의 python312.dll)이 있으면 True — 그 서명은 그대로 둔다."""
    r = subprocess.run([signtool(), "verify", "/pa", "/q", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode == 0


def sign_tree(folder):
    """앱 폴더의 모든 PE 파일(exe·dll·pyd) 가운데 아직 서명되지 않은 것에 서명한다(Microsoft Store 정책 10.2.9)."""
    if not os.environ.get("WINDOWS_SIGN_PFX"):
        return
    files = [p for p in sorted(Path(folder).rglob("*")) if p.is_file() and p.suffix.lower() in PE_SUFFIXES]
    todo = [p for p in files if not signed(p)]
    print(f"PE 파일 {len(files)}개 중 서명이 없는 {len(todo)}개에 서명합니다")
    sign(*todo)
    left = [p for p in todo if not signed(p)]
    if left:
        sys.exit("서명하지 못한 파일: " + ", ".join(p.name for p in left[:10]))


if __name__ == "__main__":
    main()
