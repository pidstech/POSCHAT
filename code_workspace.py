# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""POSCHAT Code(1.15): 작업 폴더 안의 파일을 안전하게 찾고, 읽고, 저장한다. 화면과 상관없는 순수 파일 로직.

경로 규칙(작업 폴더 밖에는 닿지 않는다):
- 화면이 주는 경로는 작업 폴더 기준 상대 경로('/'로 구분)만 받는다. 절대 경로·드라이브 문자·UNC·'..'·NUL·제어 문자는 거절한다.
- 상대 경로를 붙인 뒤 실제 경로(심볼릭 링크·Windows 정션을 모두 따라간 경로)가 작업 폴더의 실제 경로 안인지 다시 본다.
  그래서 링크로 밖을 가리키면 열 수 없다. URL 인코딩(%2e%2e)은 풀지 않으므로 그냥 그런 이름의 파일일 뿐이다.
- 읽을 때는 연 파일 핸들의 장치·inode가 검사한 경로와 같은지 확인한다(검사와 열기 사이에 링크로 바꿔치기 방지).
- 저장은 같은 폴더의 임시 파일에 쓰고 os.replace로 한 번에 바꾼다(도중에 실패해도 원본이 남는다). 바꾸기 직전에
  폴더를 다시 검사하고, 원본의 권한 비트를 옮긴다.

외부 변경 감지: 열 때 파일 내용의 SHA-256(base_hash)을 돌려주고, 저장할 때 디스크의 해시가 다르면 ConflictError를 낸다.

원격(SSH) 작업 폴더(1.18): @remote_ok를 붙인 함수는 작업 폴더가 'ssh://…'이면 같은 함수를 서버의 원격 도우미에서 실행한다
(remote_fs). 그래서 위 규칙이 서버의 파일 시스템에서 그대로 지켜진다. 이 파일은 도우미와 함께 서버로 가므로 Python 3.6에서도 돌아야 한다.
"""
import codecs
import errno
import hashlib
import os
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path, PurePosixPath

import remote_fs
from remote_fs import remote_ok

MAX_EDIT_BYTES = 1 * 1024 * 1024        # 이보다 큰 파일은 읽기 전용으로 연다
MAX_OPEN_BYTES = 8 * 1024 * 1024        # 이보다 큰 파일은 열지 않는다(화면 메모리 보호)
MAX_LIST_ENTRIES = 2000                 # 폴더 하나에서 보여 줄 항목 수
MAX_SEARCH_FILES = 5000
MAX_SEARCH_RESULTS = 300
MAX_SEARCH_FILE_BYTES = 1 * 1024 * 1024
MAX_NAME = 255
ABSENT = "absent"                       # 파일이 없을 때의 base_hash

DEFAULT_EXCLUDES = [".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
                    ".ruff_cache", ".tox", ".gradle", ".idea", "dist", "build", "target", "out", ".next",
                    ".cache", "obj_dir", "xsim.dir", ".Xil", "simv.daidir", "csrc"]
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
_BAD_CHARS = re.compile(r"[\x00-\x1f]")
_WIN_DRIVE = re.compile(r"^[A-Za-z]:")
_WIN_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.I)

LANG_BY_EXT = {
    "py": "python", "pyw": "python", "pyi": "python", "c": "c", "h": "c",
    "cc": "cpp", "cpp": "cpp", "cxx": "cpp", "hpp": "cpp", "hh": "cpp", "hxx": "cpp", "ipp": "cpp", "inl": "cpp",
    "js": "javascript", "mjs": "javascript", "cjs": "javascript", "jsx": "jsx",
    "ts": "typescript", "mts": "typescript", "cts": "typescript", "tsx": "tsx",
    "json": "json", "jsonc": "json", "md": "markdown", "markdown": "markdown", "html": "html", "htm": "html", "css": "css",
    "v": "verilog", "vh": "verilog", "vl": "verilog", "sv": "systemverilog", "svh": "systemverilog", "svi": "systemverilog",
    "tcl": "tcl", "sdc": "tcl", "xdc": "tcl", "upf": "tcl", "sh": "shell", "bash": "shell", "zsh": "shell", "ksh": "shell",
    "sp": "spice", "spi": "spice", "spice": "spice", "cir": "spice", "ckt": "spice", "net": "spice", "lib": "spice",
}
LANG_LABEL = {
    "python": "Python", "c": "C", "cpp": "C++", "javascript": "JavaScript", "jsx": "JavaScript (JSX)",
    "typescript": "TypeScript", "tsx": "TypeScript (TSX)", "json": "JSON", "markdown": "Markdown", "html": "HTML",
    "css": "CSS", "verilog": "Verilog", "systemverilog": "SystemVerilog", "tcl": "Tcl", "shell": "Shell",
    "spice": "SPICE", "text": "일반 텍스트",
}


class WorkspaceError(Exception):
    pass


class ConflictError(WorkspaceError):
    """저장하려는 파일이 연 뒤에 바뀌었다(다른 프로그램·에이전트)."""

    def __init__(self, message, current_hash):
        super().__init__(message)
        self.current_hash = current_hash


def language_of(path):
    name = PurePosixPath(str(path)).name.lower()
    if name in ("makefile", "dockerfile"):
        return "text"
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    return LANG_BY_EXT.get(ext, "text")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# ---- 경로 ----

def path_of(workspace):
    """작업 폴더 글 → 경로 객체: 원격이면 RPath, 로컬이면 Path(resolve하지 않는다)."""
    p = remote_fs.path_of(workspace)
    return p if isinstance(p, remote_fs.RPath) else Path(p)


@remote_ok
def _real(path):
    """심볼릭 링크·정션을 모두 따라간 실제 경로(없는 부분은 그대로 붙인다)."""
    return Path(os.path.realpath(os.fspath(path)))


@remote_ok
def root_of(workspace):
    if not workspace:
        raise WorkspaceError("작업 폴더가 지정되지 않았습니다. 사이드바 아래의 '작업 폴더'에서 폴더를 고르세요.")
    root = _real(workspace)
    if not root.is_dir():
        raise WorkspaceError("작업 폴더를 찾을 수 없습니다.")
    return root


def clean_rel(rel):
    """화면이 준 상대 경로를 검사해 정리된 POSIX 상대 경로로. '' 또는 '.'은 작업 폴더 자체."""
    if not isinstance(rel, str):
        raise WorkspaceError("경로가 올바르지 않습니다.")
    text = rel.replace("\\", "/").strip()
    if len(text) > 4096 or _BAD_CHARS.search(text):
        raise WorkspaceError("경로에 쓸 수 없는 글자가 있습니다.")
    if text.startswith("/") or text.startswith("//") or _WIN_DRIVE.match(text) or text.startswith("~"):
        raise WorkspaceError("작업 폴더 기준 상대 경로만 쓸 수 있습니다.")
    parts = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            raise WorkspaceError("작업 폴더 밖의 경로에는 접근할 수 없습니다.")
        if len(part) > MAX_NAME:
            raise WorkspaceError("이름이 너무 깁니다.")
        if os.name == "nt" and (":" in part or part.rstrip(" .") != part or _WIN_RESERVED.match(part)):
            raise WorkspaceError(f"Windows에서 쓸 수 없는 이름입니다: {part}")
        parts.append(part)
    return "/".join(parts)


def _inside(root, real):
    return real == root or root in real.parents


@remote_ok
def resolve(workspace, rel, must_exist=False, allow_root=True):
    """작업 폴더 안의 실제 경로. 링크가 밖을 가리키면 WorkspaceError."""
    root = root_of(workspace)
    clean = clean_rel(rel)
    if not clean and not allow_root:
        raise WorkspaceError("파일을 고르세요.")
    joined = root.joinpath(*clean.split("/")) if clean else root
    real = _real(joined)
    if not _inside(root, real):
        raise WorkspaceError("작업 폴더 밖을 가리키는 링크입니다. 열 수 없습니다.")
    if must_exist and not os.path.lexists(joined):
        raise WorkspaceError(f"파일이 없습니다: {clean or '.'}")
    return real


@remote_ok
def rel_of(workspace, path):
    root = root_of(workspace)
    return Path(path).relative_to(root).as_posix() if Path(path) != root else ""


@remote_ok
def _is_link(path):
    """심볼릭 링크 또는 Windows 정션·재분석 지점."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


# ---- 목록 ----

@remote_ok
def list_dir(workspace, rel="", show_hidden=False, excludes=None):
    """폴더 한 단계만(파일 트리를 펼칠 때마다 부른다). 링크는 표시만 하고 따라가지 않는다."""
    excludes = set(DEFAULT_EXCLUDES if excludes is None else excludes)
    folder = resolve(workspace, rel, must_exist=True)
    if not folder.is_dir():
        raise WorkspaceError("폴더가 아닙니다.")
    base = clean_rel(rel)
    items, skipped, hidden = [], 0, 0
    try:
        entries = list(os.scandir(folder))
    except OSError as e:
        raise WorkspaceError(f"폴더를 읽지 못했습니다: {e.strerror or e}")
    for entry in entries:
        name = entry.name
        if name in excludes:
            skipped += 1
            continue
        if name.startswith(".") and not show_hidden:
            hidden += 1
            continue
        link = _is_link(entry.path)
        try:
            is_dir = entry.is_dir(follow_symlinks=False) and not link
            st = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        items.append({"name": name, "path": f"{base}/{name}" if base else name, "dir": is_dir, "link": link,
                      "size": 0 if is_dir else st.st_size, "mtime": int(st.st_mtime)})
    items.sort(key=lambda x: (not x["dir"], x["name"].lower()))
    more = max(0, len(items) - MAX_LIST_ENTRIES)
    return {"path": base, "items": items[:MAX_LIST_ENTRIES], "more": more, "excluded": skipped, "hidden": hidden}


@remote_ok
def walk_files(workspace, show_hidden=False, excludes=None, limit=MAX_SEARCH_FILES):
    """(상대 경로, 실제 경로)를 하나씩. 링크와 제외 폴더는 들어가지 않는다."""
    excludes = set(DEFAULT_EXCLUDES if excludes is None else excludes)
    root = root_of(workspace)
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes and (show_hidden or not d.startswith("."))
                             and not _is_link(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            if name in excludes or (not show_hidden and name.startswith(".")):
                continue
            path = os.path.join(dirpath, name)
            if _is_link(path):
                continue
            yield Path(path).relative_to(root).as_posix(), path
            count += 1
            if count >= limit:
                return


# ---- 읽기 ----

def _newline_style(text):
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    kinds = [k for k, n in (("\r\n", crlf), ("\n", lf), ("\r", cr)) if n]
    if not kinds:
        return "\n", False
    if len(kinds) == 1:
        return kinds[0], False
    dominant = max((("\r\n", crlf), ("\n", lf), ("\r", cr)), key=lambda x: x[1])[0]
    return dominant, True


def decode(raw):
    """(텍스트, 인코딩, 확실한지). BOM이 있으면 그 인코딩, 아니면 UTF-8 → CP949 순서. 어느 것도 아니면 확실하지 않음."""
    for bom, enc in ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16")):
        if raw.startswith(bom):
            try:
                return raw.decode(enc), enc, True
            except UnicodeDecodeError:
                break
    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc), enc, True
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8", False


def looks_binary(raw):
    head = raw[:8192]
    if head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return False
    if b"\x00" in head:
        return True
    if not head:
        return False
    control = sum(1 for b in head if b < 32 and b not in (9, 10, 12, 13, 27))
    return control / len(head) > 0.1


@remote_ok
def _read_checked(path, root):
    """검사한 경로의 파일을 열고, 연 핸들이 작업 폴더 안의 그 파일인지 다시 확인한 뒤 바이트를 읽는다.
    (POSIX는 O_NOFOLLOW로 마지막 이름이 링크면 열지 않는다. Windows는 연 뒤에 실제 경로를 다시 확인한다.)"""
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as e:
        raise WorkspaceError(f"파일을 열지 못했습니다: {e.strerror or e}")
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise WorkspaceError("일반 파일이 아닙니다.")
        real = _real(path)
        if not _inside(root, real):
            raise WorkspaceError("작업 폴더 밖을 가리키는 링크입니다. 열 수 없습니다.")
        now = os.stat(real)
        if (now.st_dev, now.st_ino) != (st.st_dev, st.st_ino):
            raise WorkspaceError("파일이 여는 도중에 바뀌었습니다. 다시 여세요.")
        if st.st_size > MAX_OPEN_BYTES:
            raise WorkspaceError(f"파일이 너무 큽니다({st.st_size / 1048576:.1f}MB). {MAX_OPEN_BYTES // 1048576}MB까지 열 수 있습니다.")
        with os.fdopen(os.dup(fd), "rb") as f:
            return f.read(), st
    finally:
        os.close(fd)


@remote_ok
def read_file(workspace, rel):
    """편집기에 보낼 내용. text는 줄 끝을 \\n으로 맞춘 것이고, 저장할 때 newline으로 되돌린다."""
    path = resolve(workspace, rel, must_exist=True, allow_root=False)
    if not path.is_file():
        raise WorkspaceError("파일이 아닙니다.")
    raw, st = _read_checked(path, root_of(workspace))
    clean = clean_rel(rel)
    info = {"path": clean, "name": path.name, "size": st.st_size, "mtime": st.st_mtime, "hash": sha256(raw),
            "language": language_of(clean), "binary": False, "readonly": False, "reason": ""}
    if looks_binary(raw):
        info.update(binary=True, readonly=True, text="", encoding="", newline="\n", mixed_newlines=False,
                    final_newline=False, reason="바이너리 파일이라 편집기에서 열지 않습니다.")
        return info
    text, encoding, sure = decode(raw)
    newline, mixed = _newline_style(text)
    info.update(text=text.replace("\r\n", "\n").replace("\r", "\n"), encoding=encoding, newline=newline,
                mixed_newlines=mixed, final_newline=text.endswith(("\n", "\r")))
    if not sure:
        info.update(readonly=True, reason="인코딩을 알 수 없어(UTF-8·CP949 아님) 읽기 전용으로 엽니다. 저장하면 내용이 깨질 수 있습니다.")
    elif st.st_size > MAX_EDIT_BYTES:
        info.update(readonly=True, reason=f"1MB가 넘는 파일이라 읽기 전용으로 엽니다({st.st_size / 1048576:.1f}MB).")
    elif not os.access(path, os.W_OK):
        info.update(readonly=True, reason="쓰기 권한이 없는 파일입니다.")
    return info


@remote_ok
def current_hash(workspace, rel):
    path = resolve(workspace, rel, allow_root=False)
    if not os.path.lexists(path):
        return ABSENT
    raw, _ = _read_checked(path, root_of(workspace))
    return sha256(raw)


# ---- 쓰기 ----

def encode_text(text, encoding="utf-8", newline="\n"):
    """편집기 글(\\n)을 원래 줄 끝·인코딩으로. 인코딩에 없는 글자가 있으면 WorkspaceError."""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    if newline in ("\r\n", "\r"):
        text = text.replace("\n", newline)
    encoding = encoding or "utf-8"
    try:
        return text.encode(encoding)
    except UnicodeEncodeError as e:
        raise WorkspaceError(f"{encoding} 인코딩으로 저장할 수 없는 글자가 있습니다({e.object[e.start:e.end]!r}). "
                             "UTF-8로 저장을 고르세요.")
    except LookupError:
        raise WorkspaceError(f"알 수 없는 인코딩입니다: {encoding}")


def _default_mode():
    mask = os.umask(0)
    os.umask(mask)
    return 0o666 & ~mask


DEFAULT_MODE = _default_mode()  # 새 파일 권한(보통 0644). 시작할 때 한 번 읽는다(umask 읽기는 스레드에 안전하지 않다)


@remote_ok
def atomic_write(path, data, mode_from=None):
    """같은 폴더의 임시 파일에 쓰고 os.replace로 바꾼다. 실패하면 원본은 그대로이고 임시 파일은 지운다.
    원본의 권한을 옮기고(새 파일은 umask대로), 쓰기 권한이 없는(읽기 전용) 파일은 바꾸지 않는다."""
    path = Path(path)
    if path.exists() and not os.access(path, os.W_OK):
        raise PermissionError(errno.EACCES, "읽기 전용 파일이라 저장하지 않았습니다", str(path))
    folder = path.parent
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name[:40]}.", suffix=".poschat-tmp", dir=str(folder))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        source = mode_from if mode_from is not None else (path if path.exists() else None)
        try:
            if source is not None:
                shutil.copymode(source, tmp)
            else:
                os.chmod(tmp, DEFAULT_MODE)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@remote_ok
def write_file(workspace, rel, text, base_hash, encoding="utf-8", newline="\n", force=False):
    """편집기에서 저장. base_hash가 디스크와 다르면 ConflictError(force면 덮어쓴다). 새 해시와 정보를 돌려준다."""
    path = resolve(workspace, rel, allow_root=False)
    clean = clean_rel(rel)
    if path.is_dir():
        raise WorkspaceError("폴더에는 저장할 수 없습니다.")
    data = encode_text(text, encoding, newline)
    now = current_hash(workspace, clean)
    expected = base_hash or ABSENT  # 기준이 없으면 새 파일이어야 한다
    if not force and now != expected:
        what = "지워졌습니다" if now == ABSENT else "다른 프로그램(또는 에이전트)이 바꿨습니다"
        raise ConflictError(f"연 뒤에 파일이 {what}. 덮어쓰기 전에 바뀐 내용을 확인하세요.", now)
    if not path.parent.is_dir():
        raise WorkspaceError("저장할 폴더가 없습니다.")
    if not _inside(root_of(workspace), _real(path.parent)):  # 바꾸기 직전에 한 번 더
        raise WorkspaceError("작업 폴더 밖에는 저장할 수 없습니다.")
    if os.path.lexists(path) and _is_link(path):
        raise WorkspaceError("링크 파일에는 저장하지 않습니다. 링크가 가리키는 파일을 여세요.")
    atomic_write(path, data)
    st = os.stat(path)
    return {"path": clean, "hash": sha256(data), "size": st.st_size, "mtime": st.st_mtime}


@remote_ok
def create(workspace, rel, kind="file"):
    """새 파일(빈 파일)이나 폴더. 이미 있으면 거절한다."""
    clean = clean_rel(rel)
    if not clean:
        raise WorkspaceError("이름을 입력하세요.")
    path = resolve(workspace, clean, allow_root=False)
    if os.path.lexists(path):
        raise WorkspaceError(f"이미 있습니다: {clean}")
    if not path.parent.is_dir():
        raise WorkspaceError("상위 폴더가 없습니다.")
    if kind == "dir":
        path.mkdir()
    else:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
        os.close(fd)
    return {"path": clean, "dir": kind == "dir"}


@remote_ok
def _entry(workspace, clean):
    """이름 바꾸기·지우기 대상: 마지막 이름이 링크면 링크 자체(따라가지 않음). 어느 경우든 그 이름이 든 폴더의
    실제 경로가 작업 폴더 안이어야 한다(밖을 가리키는 폴더 링크를 거쳐 밖의 파일을 옮기지 못하게)."""
    root = root_of(workspace)
    if not clean:
        raise WorkspaceError("파일을 고르세요.")
    lex = root.joinpath(*clean.split("/"))
    parent = _real(lex.parent)
    if not _inside(root, parent):
        raise WorkspaceError("작업 폴더 밖을 가리키는 링크입니다. 다룰 수 없습니다.")
    path = parent / lex.name
    if not os.path.lexists(path):
        raise WorkspaceError(f"파일이 없습니다: {clean}")
    if not _is_link(path) and not _inside(root, _real(path)):
        raise WorkspaceError("작업 폴더 밖을 가리키는 링크입니다. 다룰 수 없습니다.")
    return path


@remote_ok
def rename(workspace, src, dst):
    """이름 바꾸기·옮기기(작업 폴더 안에서만, 덮어쓰지 않는다). 링크는 링크 자체의 이름을 바꾼다."""
    a, b = clean_rel(src), clean_rel(dst)
    if not a or not b:
        raise WorkspaceError("이름을 입력하세요.")
    src_path = _entry(workspace, a)
    dst_path = resolve(workspace, b, allow_root=False)
    if os.path.lexists(dst_path):
        raise WorkspaceError(f"같은 이름이 이미 있습니다: {b}")
    if not dst_path.parent.is_dir():
        raise WorkspaceError("옮길 폴더가 없습니다.")
    os.rename(src_path, dst_path)
    return {"path": b}


@remote_ok
def delete_to_trash(workspace, rel, trash_dir):
    """파일을 앱의 휴지통 폴더로 옮긴다(되살릴 수 있게). 폴더는 비어 있을 때만 지운다."""
    clean = clean_rel(rel)
    if not clean:
        raise WorkspaceError("지울 파일이 없습니다.")
    path = _entry(workspace, clean)
    if path.is_dir() and not _is_link(path):
        try:
            path.rmdir()
        except OSError:
            raise WorkspaceError("비어 있지 않은 폴더는 지우지 않습니다. 안의 파일을 먼저 지우세요.")
        return {"path": clean, "trash": ""}
    if not trash_dir:   # 원격(SSH) 작업 폴더: 서버의 ~/.cache/poschat/trash
        trash_dir = os.path.join(os.path.expanduser("~"), ".cache", "poschat", "trash")
    # 2.0: 초 단위 시각만으로 이름을 지으면 같은 초에 같은 경로를 두 번 지울 때 앞의 것을 덮어쓴다 — 폴더를 새로 만들어 겹치지 않게
    Path(trash_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(tempfile.mkdtemp(prefix=time.strftime("%Y%m%d-%H%M%S") + "-", dir=str(trash_dir))) / clean
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    return {"path": clean, "trash": str(dest)}


# ---- 찾기 ----

@remote_ok
def search(workspace, query, mode="name", regex=False, case=False, show_hidden=False, excludes=None):
    """mode=name: 파일 이름·경로에 query가 든 파일. mode=text: 내용에서 찾기(1MB 이하 텍스트 파일)."""
    query = str(query or "")
    if not query.strip():
        return {"results": [], "truncated": False}
    if len(query) > 500:
        raise WorkspaceError("검색어가 너무 깁니다.")
    results, truncated, scanned = [], False, 0
    if mode == "name":
        q = query.lower()
        for rel, _ in walk_files(workspace, show_hidden, excludes):
            if q in rel.lower():
                results.append({"path": rel})
                if len(results) >= MAX_SEARCH_RESULTS:
                    truncated = True
                    break
        return {"results": results, "truncated": truncated}
    flags = 0 if case else re.IGNORECASE
    try:
        rx = re.compile(query if regex else re.escape(query), flags)
    except re.error as e:
        raise WorkspaceError(f"정규식이 올바르지 않습니다: {e}")
    for rel, path in walk_files(workspace, show_hidden, excludes):
        scanned += 1
        try:
            if os.path.getsize(path) > MAX_SEARCH_FILE_BYTES:
                continue
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            continue
        if looks_binary(raw):
            continue
        text, _, _ = decode(raw)
        for no, line in enumerate(text.splitlines(), 1):
            m = rx.search(line)
            if m:
                results.append({"path": rel, "line": no, "col": m.start() + 1, "text": line.strip()[:200]})
                if len(results) >= MAX_SEARCH_RESULTS:
                    truncated = True
                    break
        if truncated:
            break
    return {"results": results, "truncated": truncated, "scanned": scanned}
