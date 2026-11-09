# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""POSCHAT 설치 프로그램.

build_installer.py가 앱 폴더를 payload.zip으로 묶어 이 스크립트와 함께 하나의 exe로 만든다.
관리자 권한 없이 현재 사용자에게 설치한다(%LOCALAPPDATA%\\Programs\\PostechChat).
제거는 앱 자신이 맡는다(PostechChat.exe --uninstall).
1.11부터 앱 이름은 POSCHAT이다. 이전 버전 위에 그대로 업데이트되도록 설치 폴더·실행 파일·등록 키(PostechChat)는 그대로 두고,
바로가기와 설치된 앱 목록에 보이는 이름만 바꾼다(예전 이름의 바로가기는 지운다).

백신(Avast 등)이 PowerShell -EncodedCommand 실행을 멈춰 세우는 것을 확인해,
바로가기는 PowerShell 대신 COM(IShellLink)으로 직접 만든다.
"""
import ctypes
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
import winreg
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# 소스에서 실행할 때는 저장소 최상위의 version.py를 찾는다(빌드한 exe에는 함께 묶인다).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from version import APP_VERSION  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import appfiles  # noqa: E402

APP_NAME = "POSCHAT"
LEGACY_NAMES = ("POSTECH GenAI Chat",)  # 1.10 이전 바로가기 이름
APP_ID = "PostechChat"
APP_EXE = "PostechChat.exe"
VERSION = APP_VERSION
PUBLISHER = "PIDS Tech."
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}"
CSIDL_PROGRAMS = 0x02
CSIDL_DESKTOPDIRECTORY = 0x10
CSIDL_LOCAL_APPDATA = 0x1C
WEBVIEW2_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"),
]
NO_WINDOW = subprocess.CREATE_NO_WINDOW
APP_CLOSE_WAIT = 30  # 설치를 누른 뒤 실행 중인 앱이 닫히기를 기다리는 시간(초)


def shell_folder(csidl):
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
    return Path(buf.value)


DEFAULT_DIR = shell_folder(CSIDL_LOCAL_APPDATA) / "Programs" / APP_ID


def resource(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def app_running():
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {APP_EXE}", "/NH"],
                       capture_output=True, text=True, creationflags=NO_WINDOW, errors="replace")
    return APP_EXE.lower() in r.stdout.lower()


def kill_app():
    """닫히지 않고 남은 앱 프로세스(창을 닫은 뒤 정리 중이거나 응답 없는 내장 MCP 서버 등)를 끝낸다."""
    subprocess.run(["taskkill", "/F", "/T", "/IM", APP_EXE], capture_output=True, creationflags=NO_WINDOW)


def has_webview2():
    for root, key in WEBVIEW2_KEYS:
        try:
            with winreg.OpenKey(root, key) as k:
                version, _ = winreg.QueryValueEx(k, "pv")
                if version and version != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def _save_shortcuts(target, places, created, failed):
    import comtypes
    import comtypes.client
    from comtypes.persist import IPersistFile
    from comtypes.shelllink import IShellLinkW, ShellLink

    comtypes.CoInitialize()  # 작업 스레드에서 돌기 때문에 스레드마다 COM을 초기화한다
    try:
        for place in places:
            error = None
            # 방금 지운 같은 이름의 바로가기를 탐색기·백신이 아직 붙잡고 있으면 그 이름으로는 저장이 거부된다.
            for name in (APP_NAME, f"{APP_NAME} (2)"):
                path = place / f"{name}.lnk"
                try:
                    link = comtypes.client.CreateObject(ShellLink, interface=IShellLinkW)
                    link.SetPath(str(target))
                    link.SetWorkingDirectory(str(target.parent))
                    link.SetIconLocation(str(target), 0)
                    link.SetDescription(APP_NAME)
                    link.QueryInterface(IPersistFile).Save(str(path), True)
                    created.append(str(path))
                    break
                except Exception as e:
                    error = e
            else:
                failed.append(f"{place}: {error}")
    finally:
        comtypes.CoUninitialize()


def previous_shortcuts():
    """이전 설치가 등록해 둔 바로가기 경로들."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
            value, _ = winreg.QueryValueEx(k, "Shortcuts")
            return [str(v) for v in value or [] if v]
    except OSError:
        return []


def remove_legacy_shortcuts():
    """예전 이름(POSTECH GenAI Chat)의 바로가기를 지운다. 새 이름의 바로가기는 이어서 다시 만든다."""
    folders = (shell_folder(CSIDL_PROGRAMS), shell_folder(CSIDL_DESKTOPDIRECTORY))
    names = {f"{n}{suffix}.lnk" for n in LEGACY_NAMES for suffix in ("", " (2)")}
    paths = {folder / name for folder in folders for name in names}
    paths |= {Path(p) for p in previous_shortcuts() if Path(p).name in names}
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass  # 탐색기가 붙잡고 있으면 남겨 둔다(앱은 새 바로가기로 실행된다)


def create_shortcuts(target, desktop, timeout=30):
    """(만든 바로가기 경로들, 실패 메시지들). 바로가기 문제로 설치 전체가 멈추거나 실패하지 않게 한다."""
    remove_legacy_shortcuts()
    places = [shell_folder(CSIDL_PROGRAMS)]
    if desktop:
        places.append(shell_folder(CSIDL_DESKTOPDIRECTORY))
    created, failed = [], []
    worker = threading.Thread(target=_save_shortcuts, args=(target, places, created, failed), daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        failed.append("바로가기 생성이 응답하지 않아 건너뛰었습니다.")
    return list(created), list(failed)


def register_uninstall(dest, size_kb, shortcuts):
    exe = dest / APP_EXE
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as k:
        winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(k, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
        winreg.SetValueEx(k, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(k, "InstallLocation", 0, winreg.REG_SZ, str(dest))
        winreg.SetValueEx(k, "DisplayIcon", 0, winreg.REG_SZ, str(exe))
        winreg.SetValueEx(k, "UninstallString", 0, winreg.REG_SZ, f'"{exe}" --uninstall')
        winreg.SetValueEx(k, "QuietUninstallString", 0, winreg.REG_SZ, f'"{exe}" --uninstall --quiet')
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "Shortcuts", 0, winreg.REG_MULTI_SZ, shortcuts)  # 제거할 때 지울 바로가기


def wait_app_closed(timeout=APP_CLOSE_WAIT):
    end = time.time() + timeout
    while app_running():
        if time.time() > end:
            raise RuntimeError(f"{APP_NAME}이(가) 실행 중입니다. 앱을 닫은 뒤 다시 설치하세요.")
        time.sleep(0.5)
    time.sleep(1)  # 프로세스가 끝난 직후에는 Windows·백신이 파일을 잠깐 더 붙잡고 있다


def check_installed(root, timeout=120):
    """설치한 앱을 창 없이 한 번 실행해, 파이썬과 앱 코드를 불러와 버전을 적는지 확인한다(PostechChat.exe --verify-install)."""
    import tempfile

    fd, out = tempfile.mkstemp(prefix="poschat-verify-", suffix=".txt")
    os.close(fd)
    try:
        try:
            r = subprocess.run([str(Path(root) / APP_EXE), f"--verify-install={out}"], cwd=str(root),
                               timeout=timeout, creationflags=NO_WINDOW, capture_output=True)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"새 버전이 {timeout}초 안에 응답하지 않았습니다.")
        written = Path(out).read_text(encoding="utf-8", errors="replace").strip()
        if written != VERSION:
            raise RuntimeError(f"새 버전 실행 확인 실패(종료 코드 {r.returncode}, 받은 값 '{written[:40]}').")
        return True
    finally:
        Path(out).unlink(missing_ok=True)


def install(dest, desktop, progress):
    """새 파일을 설치 폴더 안의 임시 폴더에 다 푼 뒤 이전 파일과 바꾼다(appfiles). 사용자 데이터(%APPDATA%\\PostechChat)는 건드리지 않는다.

    바꾸다 실패하면 이전 버전을 되돌려 두므로, 설치가 중간에 멈춰도 앱이 열리지 않는 상태가 되지 않는다.
    """
    dest = Path(dest)
    appfiles.cleanup(dest, APP_EXE)  # 지난 설치가 남긴 임시 폴더(복구용 백업은 남긴다)
    with zipfile.ZipFile(resource("payload.zip")) as zf:
        total = sum(m.file_size for m in zf.infolist()) or 1
        stage = appfiles.extract(zf, dest, progress, share=85)
    appfiles.verify(stage, APP_EXE)
    progress(86, "이전 버전과 바꾸는 중...")
    wait_app_closed()

    def check(root):
        progress(89, "새 버전이 실행되는지 확인하는 중...")
        return check_installed(root)

    appfiles.replace(dest, stage, APP_EXE, check=check)
    progress(93, "바로가기 만드는 중...")
    shortcuts, failed = create_shortcuts(dest / APP_EXE, desktop)
    progress(97, "등록하는 중...")
    register_uninstall(dest, total // 1024, shortcuts)
    progress(100, "완료")
    return failed


def had_desktop_shortcut():
    """이전 설치가 바탕화면 바로가기를 만들었는지. 기록이 없으면(예전 설치) True(지금까지처럼 만든다)."""
    previous = previous_shortcuts()
    if not previous:
        return True
    desktop = shell_folder(CSIDL_DESKTOPDIRECTORY)
    return any(Path(p).parent == desktop for p in previous)


class InstallerUI:
    def __init__(self, root, destination=None, update=False):
        self.root = root
        # 2.3.1: 앱의 '업데이트'로 열리면(--update) 사용자는 이미 업데이트를 골랐으므로 '설치'·'마침'을 다시 누르게 하지 않는다.
        # 앱이 닫히기를 기다려 바로 설치하고, 끝나면 새 버전을 열고 이 창을 닫는다. 바탕화면 바로가기는 이전 설치를 따른다.
        self.update = update
        root.title(f"{APP_NAME} 설치")
        root.resizable(False, False)
        try:
            root.iconbitmap(resource("icon.ico"))
        except tk.TclError:
            pass
        dpi_scale = root.winfo_fpixels("1i") / 96
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Malgun Gothic", 15, "bold"))
        style.configure("Body.TLabel", font=("Malgun Gothic", 10))
        style.configure("Muted.TLabel", font=("Malgun Gothic", 9), foreground="#666666")
        style.configure("TCheckbutton", font=("Malgun Gothic", 10))
        style.configure("TButton", font=("Malgun Gothic", 10))

        frm = ttk.Frame(root, padding=(28, 24, 28, 20))
        frm.pack(fill=tk.BOTH, expand=True)
        head = ttk.Frame(frm)
        head.pack(fill=tk.X)
        try:
            factor = 4 if dpi_scale < 1.35 else 2
            self.logo = tk.PhotoImage(file=resource("icon.png")).subsample(factor, factor)
            ttk.Label(head, image=self.logo).pack(side=tk.LEFT, padx=(0, 14))
        except tk.TclError:
            pass
        titles = ttk.Frame(head)
        titles.pack(side=tk.LEFT, fill=tk.X)
        ttk.Label(titles, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text=f"버전 {VERSION} · POSTECH GenAI·개인 Claude API 데스크톱 챗봇·에이전트", style="Muted.TLabel").pack(anchor="w")

        self.body = ttk.Frame(frm)
        self.body.pack(fill=tk.BOTH, expand=True, pady=(22, 0))
        ttk.Label(self.body, text="설치 위치", style="Body.TLabel").pack(anchor="w")
        row = ttk.Frame(self.body)
        row.pack(fill=tk.X, pady=(4, 12))
        self.dest = tk.StringVar(value=str(destination or DEFAULT_DIR))
        ttk.Entry(row, textvariable=self.dest, width=46).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text="찾아보기...", command=self.browse).pack(side=tk.LEFT, padx=(6, 0))
        self.desktop = tk.BooleanVar(value=had_desktop_shortcut() if update else True)
        self.launch = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.body, text="바탕화면에 바로가기 만들기", variable=self.desktop).pack(anchor="w", pady=2)
        ttk.Checkbutton(self.body, text="설치 후 바로 실행", variable=self.launch).pack(anchor="w", pady=2)
        ttk.Label(self.body, text="관리자 권한 없이 현재 사용자 계정에만 설치됩니다. 대화 기록과 설정은 %APPDATA%\\PostechChat에 저장됩니다.",
                  style="Muted.TLabel", wraplength=int(500 * dpi_scale), justify="left").pack(anchor="w", pady=(12, 0))

        self.status = tk.StringVar(value="")
        self.progress = ttk.Progressbar(frm, maximum=100)
        self.status_label = ttk.Label(frm, textvariable=self.status, style="Muted.TLabel")

        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X, side=tk.BOTTOM, pady=(18, 0))
        self.cancel_btn = ttk.Button(btns, text="취소", command=root.destroy)
        self.cancel_btn.pack(side=tk.RIGHT)
        self.install_btn = ttk.Button(btns, text="설치", command=self.start)
        self.install_btn.pack(side=tk.RIGHT, padx=(0, 8))
        root.update_idletasks()
        w, h = int(580 * dpi_scale), int(380 * dpi_scale)  # 고해상도(배율) 화면에서 창이 작아지지 않도록
        root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
        if update:
            root.after(300, self.start)

    def browse(self):
        path = filedialog.askdirectory(initialdir=self.dest.get(), title="설치 위치 선택")
        if path:
            self.dest.set(str(Path(path) / APP_ID) if Path(path).name != APP_ID else path)

    def start(self):
        # 앱의 '업데이트'로 열리면 앱이 이 창을 띄운 직후 스스로 닫히는데, 내장 MCP 서버·녹음 저장 같은 정리에
        # 몇 초 걸린다. 바로 경고하면 '설치'를 두 번 눌러야 하므로, 앱이 닫힐 때까지 기다렸다가 이어서 설치한다.
        if app_running():
            self.install_btn.config(state=tk.DISABLED)
            self.status.set(f"{APP_NAME}이(가) 닫히기를 기다리는 중...")
            self.status_label.pack(anchor="w", pady=(10, 0))
            self._wait_for_app(time.time() + APP_CLOSE_WAIT)
            return
        self._start()

    def _wait_for_app(self, deadline):
        if not app_running():
            self.status_label.pack_forget()
            self.install_btn.config(state=tk.NORMAL)
            return self._start()
        if time.time() < deadline:
            self.root.after(500, lambda: self._wait_for_app(deadline))
            return
        self.install_btn.config(state=tk.NORMAL)
        self.status_label.pack_forget()
        if messagebox.askyesno("설치", f"{APP_NAME}이(가) 아직 실행 중입니다.\n\n"
                               "앱을 강제로 종료하고 설치할까요? 저장하지 않은 입력은 사라질 수 있습니다.", parent=self.root):
            kill_app()
            self.root.after(1000, self.start)

    def _start(self):
        dest = Path(self.dest.get().strip() or DEFAULT_DIR)
        if dest.exists() and any(dest.iterdir()) and not (dest / APP_EXE).exists() and not (dest / "_internal").exists():
            messagebox.showwarning("설치", "비어 있지 않은 다른 폴더에는 설치할 수 없습니다.\n새 폴더를 지정하세요.", parent=self.root)
            return
        if not has_webview2() and not messagebox.askyesno(
                "WebView2 런타임",
                "이 PC에서 Microsoft Edge WebView2 런타임을 찾지 못했습니다.\n"
                "앱 화면을 표시하려면 WebView2가 필요합니다(Windows 11에는 기본 포함).\n\n"
                "그래도 설치를 계속할까요? 앱이 열리지 않으면\n"
                "https://go.microsoft.com/fwlink/p/?LinkId=2124703 에서 설치하세요.", parent=self.root):
            return
        self.dest.set(str(dest))
        self.install_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.DISABLED)
        self.body.pack_forget()
        self.progress.pack(fill=tk.X, pady=(40, 8))
        self.status_label.pack(anchor="w")
        threading.Thread(target=self._work, daemon=True).start()

    def _progress(self, value, text):
        self.root.after(0, lambda: (self.progress.config(value=value), self.status.set(text)))

    def _work(self):
        try:
            failed = install(self.dest.get(), self.desktop.get(), self._progress)
        except Exception as e:
            self.root.after(0, lambda: self._fail(e))
            return
        self.root.after(0, lambda: self._done(failed))

    def _fail(self, error):
        backup = getattr(error, "backup", None)
        text = f"설치 중 오류가 발생했습니다.\n\n{error}\n\n"
        if backup:  # 되돌리기에 실패: 이전 버전이 보관된 폴더를 열어 볼 수 있게 한다
            if messagebox.askyesno("설치 실패", text + "이전 버전을 보관한 폴더를 열까요?", icon="error", parent=self.root):
                os.startfile(backup)
        else:
            messagebox.showerror("설치 실패", text + "백신 프로그램이 설치를 막았다면 잠시 뒤 다시 시도하거나 예외로 허용해 주세요.",
                                 parent=self.root)
        self.root.destroy()

    def _done(self, failed):
        exe = Path(self.dest.get()) / APP_EXE
        note = ("\n\n일부 바로가기를 만들지 못했습니다. 설치 폴더의 PostechChat.exe로 실행할 수 있습니다."
                if failed else "")
        self.status.set(f"설치가 끝났습니다.\n{exe.parent}{note}")
        self.cancel_btn.pack_forget()
        self.install_btn.config(text="마침", state=tk.NORMAL, command=self.finish)
        if self.update and not failed:
            self.root.after(1500, self.finish)   # 업데이트: 새 버전을 바로 연다

    def finish(self):
        if self.launch.get():
            exe = Path(self.dest.get()) / APP_EXE
            subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=subprocess.DETACHED_PROCESS)
        self.root.destroy()


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    if "--silent" in sys.argv:  # 테스트·자동 설치용: 오류 창 대신 %TEMP%\PostechChat-install.log에 남긴다
        dest = DEFAULT_DIR
        for arg in sys.argv:
            if arg.startswith("--dir="):
                dest = Path(arg[6:])
        import tempfile
        import traceback
        log = Path(tempfile.gettempdir(), "PostechChat-install.log")
        log.write_text("", encoding="utf-8")
        last = [""]

        def progress(value, text):
            if text != last[0]:  # 단계가 바뀔 때만 기록해 어디서 멈췄는지 알 수 있게 한다
                last[0] = text
                with log.open("a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%H:%M:%S')} {text}\n")

        try:
            failed = install(dest, "--no-desktop" not in sys.argv, progress)
        except Exception:
            with log.open("a", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            sys.exit(1)
        if failed:
            with log.open("a", encoding="utf-8") as f:
                f.write("바로가기 경고:\n" + "\n".join(failed) + "\n")
        return
    destination = next((arg[6:] for arg in sys.argv if arg.startswith("--dir=")), None)
    root = tk.Tk()
    InstallerUI(root, destination, update="--update" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
