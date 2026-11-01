# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""앱과 설치 프로그램을 빌드한다.

    python build_installer.py

필요 패키지: requirements.txt와 pyinstaller (pip install -r requirements.txt pyinstaller)
결과: Windows는 release/POSCHAT-Setup.exe, release/POSCHAT-Store-Setup.exe(1.18), release/POSCHAT.msix(Microsoft Store 제출용, 2.0.1),
macOS는 release/POSCHAT-mac.dmg(앱 아이콘을 위해 pillow도 필요)
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
# 2.0.1 Microsoft Store 제출용(MSIX 방식): Store가 심사 뒤 Microsoft 인증서로 다시 서명하므로 코드 서명 인증서가 없어도 된다.
# 사용자는 브라우저로 exe를 받지 않고 Store에서 설치하므로 Chrome·SmartScreen의 다운로드 경고가 뜨지 않는다.
# 서명하지 않은 MSIX는 Windows가 설치하지 않으므로 릴리스에는 올리지 않고 CI 산출물로만 둔다(파트너 센터에 직접 올린다).
MSIX_FILE = "POSCHAT.msix"
PE_SUFFIXES = (".exe", ".dll", ".pyd")
DMG_FILE = "POSCHAT-mac.dmg"
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


def main():
    if sys.platform == "darwin":
        if WORK.exists():
            shutil.rmtree(WORK)
        return build_mac()
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

    print("[+] Microsoft Store 패키지(MSIX)")
    build_msix(app_dir, out / MSIX_FILE)


def msix_identity():
    """파트너 센터 → 제품 ID(Product identity)에 나오는 세 값. 저장소 변수(MSIX_*)로 넣는다.

    값이 없으면 시험용 값으로 만든다. 이 패키지는 CI 자가 진단에만 쓰고 Store에는 낼 수 없다(게시자가 달라 거절됨).
    """
    return {
        "name": os.environ.get("MSIX_IDENTITY_NAME", "").strip() or "PIDSTech.POSCHAT.Test",
        "publisher": os.environ.get("MSIX_PUBLISHER", "").strip() or "CN=POSCHAT Test",
        "publisher_display": os.environ.get("MSIX_PUBLISHER_DISPLAY_NAME", "").strip() or "PIDS Tech.",
    }


def msix_version(app_version):
    """MSIX 버전은 숫자 네 개이고, Store는 마지막 자리가 0이어야 받는다(2.0.0 → 2.0.0.0)."""
    parts = [int(p) for p in app_version.split(".")]
    if len(parts) != 3 or any(not 0 <= p <= 65535 for p in parts):
        raise ValueError(f"MSIX 버전으로 바꿀 수 없는 앱 버전: {app_version}")
    return ".".join(map(str, parts)) + ".0"


def msix_manifest(app_version, identity):
    """AppxManifest.xml. 일반 데스크톱 앱(전체 신뢰, runFullTrust)으로 PostechChat.exe를 그대로 실행한다."""
    from xml.sax.saxutils import quoteattr

    q = quoteattr
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:uap3="http://schemas.microsoft.com/appx/manifest/uap/windows10/3"
         xmlns:desktop="http://schemas.microsoft.com/appx/manifest/desktop/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap uap3 desktop rescap">
  <Identity Name={q(identity["name"])} Publisher={q(identity["publisher"])}
            Version="{msix_version(app_version)}" ProcessorArchitecture="x64" />
  <Properties>
    <DisplayName>{APP_NAME}</DisplayName>
    <PublisherDisplayName>{_xml_text(identity["publisher_display"])}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0" />
  </Dependencies>
  <Resources>
    <Resource Language="ko-KR" />
  </Resources>
  <Applications>
    <Application Id="POSCHAT" Executable="PostechChat.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{APP_NAME}" Description="학생과 연구자를 위한 AI 작업 공간"
                          BackgroundColor="transparent"
                          Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" />
      <Extensions>
        <!-- 명령 줄에서 poschat.exe로 실행(CI 자가 진단도 이 이름으로 실행한다) -->
        <uap3:Extension Category="windows.appExecutionAlias" Executable="PostechChat.exe" EntryPoint="Windows.FullTrustApplication">
          <uap3:AppExecutionAlias>
            <desktop:ExecutionAlias Alias="poschat.exe" />
          </uap3:AppExecutionAlias>
        </uap3:Extension>
      </Extensions>
    </Application>
  </Applications>
  <Capabilities>
    <Capability Name="internetClient" />
    <rescap:Capability Name="runFullTrust" />
    <DeviceCapability Name="microphone" />
  </Capabilities>
</Package>
"""


def _xml_text(text):
    from xml.sax.saxutils import escape
    return escape(text)


# MSIX 그림: 이름 → 크기(px). 자원 한정자가 붙은 이름(targetsize-44 등)은 resources.pri가 있어야 하므로 쓰지 않는다.
MSIX_LOGOS = {
    "StoreLogo.png": 50,
    "Square44x44Logo.png": 44,
    "Square150x150Logo.png": 150,
}


def msix_layout(app_dir, layout, app_version, identity):
    """makeappx에 넘길 폴더: 앱 + Store판 표시(distribution.txt) + 그림 + AppxManifest.xml."""
    from PIL import Image

    if layout.exists():
        shutil.rmtree(layout)
    shutil.copytree(app_dir, layout)
    # Store판: 스스로 업데이트 파일을 받지 않고 Store로 안내한다(version.distribution). MSIX는 Store가 업데이트한다.
    (layout / "_internal" / version.DISTRIBUTION_FILE).write_text("store\n", encoding="utf-8")
    assets = layout / "Assets"
    assets.mkdir()
    with Image.open(ICON_PNG) as icon:
        icon = icon.convert("RGBA")
        for name, size in MSIX_LOGOS.items():
            icon.resize((size, size), Image.LANCZOS).save(assets / name)
    (layout / "AppxManifest.xml").write_text(msix_manifest(app_version, identity), encoding="utf-8")
    return layout


# MSIX 패키지 안 파일 이름 규칙: Windows 예약 장치 이름(확장자가 붙어도), 금지 문자, 끝의 점·공백은 넣을 수 없다.
MSIX_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}


def msix_bad_names(layout):
    """패키지에 넣을 수 없는 이름의 파일·폴더(layout 기준 상대 경로) 목록."""
    bad = []
    for f in sorted(Path(layout).rglob("*")):
        name = f.name
        if (name.split(".")[0].lower() in MSIX_RESERVED or name.endswith((".", " "))
                or any(c in name for c in '<>:"|?*%') or any(ord(c) < 32 for c in name)):
            bad.append(f.relative_to(layout).as_posix())
    return bad


def _msix_probe(layout):
    import re
    tool = sdk_tool("makeappx.exe")
    base = [layout / "AppxManifest.xml", *sorted((layout / "Assets").iterdir()), layout / "PostechChat.exe"]
    odd = [f for f in sorted(layout.rglob("*")) if f.is_file() and not re.fullmatch(r"[A-Za-z0-9._-]+", f.name)]
    print(f"[진단] 특이한 이름 {len(odd)}개: " + ", ".join(f.relative_to(layout).as_posix() for f in odd[:40]))
    groups = [("기본", [])] + [(f.relative_to(layout).as_posix(), [f]) for f in odd[:25]]
    top = sorted({f.relative_to(layout).parts[1] for f in layout.rglob("*") if f.is_file() and f.relative_to(layout).parts[0] == "_internal" and len(f.relative_to(layout).parts) > 2})
    groups += [(f"_internal/{t}/", [f for f in (layout / "_internal" / t).rglob("*") if f.is_file()]) for t in top]
    for label, extra in groups:
        probe = WORK / "probe"
        if probe.exists():
            shutil.rmtree(probe)
        for f in base + extra:
            dst = probe / f.relative_to(layout)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
        r = subprocess.run([tool, "pack", "/d", str(probe), "/p", str(WORK / "probe.msix"), "/o"], capture_output=True, text=True, errors="replace")
        print(f"[진단] {label}: {'OK' if r.returncode == 0 else '실패'}")


def build_msix(app_dir, target):
    identity = msix_identity()
    layout = msix_layout(app_dir, WORK / "msix", version.APP_VERSION, identity)
    bad = msix_bad_names(layout)
    if bad:
        sys.exit("MSIX에 넣을 수 없는 이름의 파일: " + ", ".join(bad[:20]))
    target.unlink(missing_ok=True)
    # CI 러너의 %TEMP%는 짧은 이름(RUNNER~1)이다. makeappx가 0x8007007b(경로 문법 오류)로 실패한 적이 있어
    # 긴 이름으로 바꾸고, 결과도 작업 폴더에 만든 뒤 옮긴다.
    layout = Path(os.path.realpath(layout))
    built = Path(os.path.realpath(WORK)) / MSIX_FILE
    built.unlink(missing_ok=True)
    r = subprocess.run([sdk_tool("makeappx.exe"), "pack", "/d", str(layout), "/p", str(built), "/o"],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0:   # makeappx는 실패 이유(매니페스트 오류·파일 이름 등)를 표준 출력에 쓴다
        out = [x for x in r.stdout.splitlines() if x.strip()]
        done = [x for x in out if x.startswith("Processing ")]
        _msix_probe(layout)   # 임시 진단: 어떤 파일이 실패를 일으키는지 작은 패키지로 하나씩 시험
        sys.exit(f"makeappx 실패({r.returncode}, 파일 {len(done)}개 처리):\n"
                 + "\n".join(x for x in out if not x.startswith("Processing ")) + "\n마지막으로 처리한 파일:\n"
                 + "\n".join(done[-3:]) + f"\n{r.stderr[-2000:]}\n확장자: "
                 + " ".join(sorted({f.suffix for f in layout.rglob("*") if f.is_file()})))
    shutil.move(str(built), str(target))
    test = "" if os.environ.get("MSIX_PUBLISHER", "").strip() else " — 시험용 게시자(Store에 낼 수 없음)"
    print(f"완료: {target} ({target.stat().st_size / 1024 / 1024:.1f} MB, {identity['name']}{test})")


def zip_app(app_dir, target, extra=None):
    """앱 폴더를 설치 프로그램에 넣을 payload.zip으로. extra: {zip 안 경로: 글} — 더 넣을 파일."""
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(app_dir).as_posix())
        for name, text in (extra or {}).items():
            zf.writestr(name, text)


def sdk_tool(name):
    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    tools = sorted(kits.glob(f"*/x64/{name}"))
    if not tools:
        sys.exit(f"{name}를 찾지 못했습니다. Windows SDK를 설치하세요.")
    return str(tools[-1])


def signtool():
    return sdk_tool("signtool.exe")


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
