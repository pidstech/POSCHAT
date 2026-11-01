# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""클라우드 동기화(Opt-in, 종단간 암호화): Windows·macOS·Android 사이에서 메모리·대화·설정·PO노트를 맞춘다.

백엔드(새 서버를 만들지 않는다)
    folder  사용자가 이미 쓰는 동기화 폴더(OneDrive·Dropbox·Google Drive 데스크톱·iCloud Drive 등) 안의 poschat-sync/
    gdrive  Google Drive의 앱 전용 숨김 폴더(appDataFolder, drive.appdata 권한만). 안드로이드에서도 쓸 수 있다.

암호화
    동기화 암호 → scrypt(n=2^15, r=8, p=1) → 32바이트 키. 키는 기기마다 secret_store("sync:key")에만 두고 동기화하지 않는다.
    객체마다 AES-256-GCM(12바이트 nonce). 원격에는 meta.json(형식·솔트·키 확인 값)만 평문이고, 객체 이름은
    HMAC-SHA256(키, "종류:ID")라서 무엇이 몇 개 있는지 외에는 알 수 없다.

동기화 대상(각각 끌 수 있다)
    memory    memory.md                         3-way 줄 병합(기준본 대비 양쪽의 추가·삭제를 모두 반영)
    profile   USER.md                           양쪽이 바뀌면 최신본 + 다른 쪽은 sync-conflicts/에 보관
    threads   대화(threads/*.json)              메시지 id 합집합, 제목·모델은 최신 쪽
    project   통합 메모리 항목·인계             레코드 단위 최종 수정 우선 + 삭제 표시
    research  논문 라이브러리                   레코드 단위 최종 수정 우선 + 삭제 표시
    settings  화면·에이전트 설정 일부(SETTINGS_KEYS)  최종 수정 우선
    po_notes  PO노트 제목·길이·노트·메모·전사   노트 단위 최종 수정 우선 + 진 쪽 노트는 sync-conflicts/
    빠지는 것: API 키·OAuth 토큰·secret_store, 작업 폴더 경로, 첨부 원본, 강의 자료 원본, 권한 설정(permission)

오프라인: sync_state.json에 객체마다 마지막으로 맞춘 내용 해시를 두고, 다음 동기화 때 바뀐 쪽을 판단한다.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

import secret_store
import storage

FORMAT = 1
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 15, 8, 1
AAD = b"poschat-sync-v1"
CHECK = b"poschat-sync-check"
INCLUDE = ("memory", "profile", "threads", "project", "research", "settings", "po_notes")
SETTINGS_KEYS = ("history_messages", "max_steps", "share_threads", "stream", "update_check", "po_engine", "po_model",
                 "po_language", "po_reserve")
NAME_RE = re.compile(r"^([0-9a-f]{40})")
_lock = threading.Lock()


class SyncError(Exception):
    pass


def available():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    except ImportError:
        return False, "이 실행 환경에 암호화 라이브러리(cryptography)가 없어 동기화를 쓸 수 없습니다."
    return True, ""


# ---- 암호 ----

def derive_key(passphrase, salt):
    if len(str(passphrase or "")) < 8:
        raise SyncError("동기화 암호는 8글자 이상이어야 합니다.")
    return hashlib.scrypt(str(passphrase).encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                          maxmem=128 * 1024 * 1024, dklen=32)


class Cipher:
    def __init__(self, key):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        self._aead = AESGCM(hmac.new(key, b"encrypt", hashlib.sha256).digest())
        self._name_key = hmac.new(key, b"name", hashlib.sha256).digest()

    def encrypt(self, obj):
        nonce = secrets.token_bytes(12)
        return nonce + self._aead.encrypt(nonce, json.dumps(obj, ensure_ascii=False).encode("utf-8"), AAD)

    def decrypt(self, blob):
        from cryptography.exceptions import InvalidTag

        try:
            return json.loads(self._aead.decrypt(blob[:12], blob[12:], AAD).decode("utf-8"))
        except (InvalidTag, ValueError):
            raise SyncError("복호화하지 못했습니다(암호가 다르거나 파일이 손상됨).")

    def name(self, key):
        return hmac.new(self._name_key, key.encode("utf-8"), hashlib.sha256).hexdigest()[:40]

    def check_value(self):
        return base64.b64encode(hmac.new(self._name_key, CHECK, hashlib.sha256).digest()).decode("ascii")


# ---- 백엔드 ----

class FolderBackend:
    """동기화 폴더 안의 poschat-sync/. 클라이언트가 만든 충돌 사본("이름 (1).bin" 등)도 목록에 그대로 보인다."""

    def __init__(self, folder):
        if not folder:
            raise SyncError("동기화 폴더를 고르세요.")
        self.root = Path(folder) / "poschat-sync"

    def read_meta(self):
        try:
            return json.loads((self.root / "meta.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            raise SyncError(f"meta.json을 읽지 못했습니다: {e}")

    def write_meta(self, meta):
        self.root.mkdir(parents=True, exist_ok=True)
        self._write(self.root / "meta.json", json.dumps(meta).encode("utf-8"))

    def list(self):
        objects = self.root / "objects"
        if not objects.is_dir():
            return {}
        return {p.name: p.stat().st_mtime for p in objects.iterdir() if p.is_file() and p.suffix == ".bin"}

    def get(self, name):
        return (self.root / "objects" / name).read_bytes()

    def put(self, name, data):
        (self.root / "objects").mkdir(parents=True, exist_ok=True)
        self._write(self.root / "objects" / name, data)
        return (self.root / "objects" / name).stat().st_mtime

    def delete(self, name):
        (self.root / "objects" / name).unlink(missing_ok=True)

    def wipe(self):
        shutil.rmtree(self.root, ignore_errors=True)

    @staticmethod
    def _write(path, data):
        tmp = path.with_name(path.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, path)


class DriveBackend:
    """Google Drive appDataFolder(drive.appdata). 파일 이름은 'poschat-sync.meta.json', 'poschat-sync.<이름>'."""

    API = "https://www.googleapis.com/drive/v3/files"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
    PREFIX = "poschat-sync."

    def __init__(self, connector="gsync"):
        self.connector = connector
        self._ids = {}

    def _http(self, method, url, **kwargs):
        import connectors
        import oauth
        from net import ToolFailure, http

        try:
            token = connectors.credential(self.connector)
        except oauth.OAuthError as e:
            raise SyncError(f"Google Drive 동기화 저장소에 로그인하세요({e}).")
        headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
        for attempt in range(3):
            try:
                r = http(method, url, headers=headers, timeout=60, **kwargs)
            except ToolFailure as e:
                if attempt == 2:
                    raise SyncError(str(e))
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            break
        if r.status_code == 401:
            raise SyncError("Google 인증이 만료되었습니다. 다시 로그인하세요.")
        if r.status_code >= 300 and r.status_code != 404:
            raise SyncError(f"Google Drive 요청 실패(HTTP {r.status_code}): {r.text[:200]}")
        return r

    def _list_all(self):
        files, token = {}, None
        while True:
            params = {"spaces": "appDataFolder", "pageSize": 1000, "fields": "nextPageToken,files(id,name,modifiedTime)",
                      "q": f"name contains '{self.PREFIX}'"}
            if token:
                params["pageToken"] = token
            data = self._http("GET", self.API, params=params).json()
            for f in data.get("files") or []:
                files[f["name"]] = f
            token = data.get("nextPageToken")
            if not token:
                break
        self._ids = {name: f["id"] for name, f in files.items()}
        return files

    def _download(self, full_name):
        fid = self._ids.get(full_name) or self._list_all().get(full_name, {}).get("id")
        if not fid:
            return None
        r = self._http("GET", f"{self.API}/{fid}", params={"alt": "media"})
        return None if r.status_code == 404 else r.content

    def _upload(self, full_name, data, mime="application/octet-stream"):
        import uuid

        fid = self._ids.get(full_name)
        if fid:
            r = self._http("PATCH", f"{self.UPLOAD}/{fid}", params={"uploadType": "media", "fields": "id,modifiedTime"},
                           data=data, headers={"Content-Type": mime})
        else:
            boundary = uuid.uuid4().hex
            meta = json.dumps({"name": full_name, "parents": ["appDataFolder"]})
            body = (f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{meta}\r\n--{boundary}\r\n"
                    f"Content-Type: {mime}\r\n\r\n").encode() + data + f"\r\n--{boundary}--".encode()
            r = self._http("POST", self.UPLOAD, params={"uploadType": "multipart", "fields": "id,modifiedTime"}, data=body,
                           headers={"Content-Type": f"multipart/related; boundary={boundary}"})
        info = r.json()
        self._ids[full_name] = info["id"]
        return info.get("modifiedTime", "")

    def read_meta(self):
        self._list_all()
        data = self._download(self.PREFIX + "meta.json")
        return json.loads(data) if data else None

    def write_meta(self, meta):
        self._upload(self.PREFIX + "meta.json", json.dumps(meta).encode("utf-8"), "application/json")

    def list(self):
        files = self._list_all()
        return {name[len(self.PREFIX):]: f.get("modifiedTime", "") for name, f in files.items()
                if name.startswith(self.PREFIX) and name.endswith(".bin")}

    def get(self, name):
        data = self._download(self.PREFIX + name)
        if data is None:
            raise SyncError(f"원격 객체가 없습니다: {name}")
        return data

    def put(self, name, data):
        return self._upload(self.PREFIX + name, data)

    def delete(self, name):
        fid = self._ids.get(self.PREFIX + name)
        if fid:
            self._http("DELETE", f"{self.API}/{fid}")
            self._ids.pop(self.PREFIX + name, None)

    def wipe(self):
        self._list_all()
        for fid in list(self._ids.values()):
            self._http("DELETE", f"{self.API}/{fid}")
        self._ids = {}


def verify_drive(cid="gsync", config=None):
    """커넥터 연결 확인: appDataFolder 목록을 읽을 수 있는지."""
    from net import ToolFailure

    try:
        files = DriveBackend(cid).list()
    except SyncError as e:
        raise ToolFailure(str(e))
    return {"account": "", "detail": f"앱 전용 폴더 사용 가능(동기화 객체 {len(files)}개)"}


def backend_from_config(config):
    s = config.get("sync") or {}
    if s.get("backend") == "gdrive":
        return DriveBackend()
    return FolderBackend(s.get("folder", ""))


# ---- 상태 ----

def state_path():
    return storage.APP_DIR / "sync_state.json"


def load_state():
    try:
        data = json.loads(state_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def save_state(state):
    tmp = state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, state_path())


def conflicts_dir():
    return storage.APP_DIR / "sync-conflicts"


def digest(obj):
    payload = {"deleted": bool(obj.get("deleted")), "data": obj.get("data")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:32]


# ---- 로컬 데이터 모으기 ----

def _obj(kind, oid, updated, data, deleted=None):
    return {"kind": kind, "id": oid, "updated": float(updated or 0), "deleted": deleted, "data": data}


def _still_on_disk(kind, ident):
    """2.0: collect가 건너뛴 대화·PO노트가 정말 지워졌는지(파일이 없는지) 확인한다."""
    import po_note

    try:
        if kind == "thread":
            path = storage.THREADS_DIR / f"{ident}.json"
            if not path.exists():
                return False
            try:  # 읽히는데 메시지가 없으면(빈 대화) 예전처럼 지운 것으로 본다
                return bool(json.loads(path.read_text(encoding="utf-8")).get("messages"))
            except (OSError, ValueError, AttributeError):
                return True
        if kind == "po":
            return (po_note.NOTES_DIR / ident / "meta.json").exists()
    except (OSError, ValueError):
        return True  # 확인하지 못하면 지우지 않는다
    return False


def collect(include, config):
    """{키: 객체}. 키는 "종류:ID"."""
    import po_note

    out = {}
    if "memory" in include:
        text = storage.read_memory_md()
        out["file:memory.md"] = _obj("file", "memory.md", storage.MEMORY_PATH.stat().st_mtime, text)
    if "profile" in include and storage.profile_exists():
        out["file:USER.md"] = _obj("file", "USER.md", storage.PROFILE_PATH.stat().st_mtime, storage.read_profile())
    if "threads" in include:
        for p in storage.THREADS_DIR.glob("*.json"):
            try:
                thread = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if thread.get("messages"):  # 아무것도 없는 새 대화는 보내지 않는다
                out[f"thread:{thread['id']}"] = _obj("thread", thread["id"], thread.get("updated"), thread)
    if "project" in include:
        import handoff
        import memory_store

        for e in memory_store.entries(include_deleted=True, limit=1_000_000):
            out[f"entry:{e['id']}"] = _obj("entry", e["id"], e["updated"], e, e.get("deleted"))
        for h in handoff.list_handoffs(limit=1_000_000):
            out[f"handoff:{h['task_id']}"] = _obj("handoff", h["task_id"], h["updated"], h)
    if "research" in include:
        import research_library

        data = research_library.load()
        for pid, paper in data["papers"].items():
            out[f"paper:{pid}"] = _obj("paper", pid, paper.get("updated"), paper)
        for pid, ts in data["deleted"].items():
            out.setdefault(f"paper:{pid}", _obj("paper", pid, ts, None, ts))
    if "settings" in include:
        values = {k: config[k] for k in SETTINGS_KEYS if k in config}
        stamp = float(config.get("settings_updated") or 0)
        out["settings:main"] = _obj("settings", "main", stamp, values)
    if "po_notes" in include:
        for note in po_note.list_notes():
            out[f"po:{note['id']}"] = _obj("po", note["id"], note.get("updated") or note.get("created"), _po_data(note["id"]))
    return out


def _po_data(note_id):
    import po_note

    d = po_note._dir(note_id)
    meta = po_note._read_json(d / "meta.json", {})

    def text(name):
        try:
            return (d / name).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    return {"meta": {k: meta.get(k) for k in ("id", "title", "created", "duration", "engine") if k in meta},
            "note": text("note.md"), "memo": text("memo.md"), "transcript": po_note._read_json(d / "transcript.json", [])}


# ---- 병합 ----

def merge_lines(base, local, remote):
    """줄 단위 3-way 병합: 기준본에 있던 줄은 어느 한쪽이라도 지웠으면 지우고, 양쪽에서 더한 줄은 모두 남긴다."""
    base_lines = set((base or "").splitlines())
    a, b = local.splitlines(), remote.splitlines()
    removed = {line for line in base_lines if line.strip() and (line not in a or line not in b)}
    seen = set(a)
    out = [line for line in a if line not in removed] + [line for line in b if line not in seen and line not in removed]
    return "\n".join(out) + "\n"


def _save_conflict(name, text, device):
    d = conflicts_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{time.strftime('%Y%m%d-%H%M%S')}-{device or 'other'}-{name}"
    path.write_text(text, encoding="utf-8")
    return str(path)


def merge(key, local, remote, base_text, conflicts):
    """양쪽이 모두 바뀐 객체를 하나로. 삭제 표시도 최종 수정 우선으로 다룬다."""
    kind = local["kind"]
    newer, older = (local, remote) if local["updated"] >= remote["updated"] else (remote, local)
    if local.get("deleted") or remote.get("deleted"):
        return dict(newer)
    if key == "file:memory.md":
        return _obj("file", "memory.md", max(local["updated"], remote["updated"]),
                    merge_lines(base_text, local["data"], remote["data"]))
    if kind == "file":
        conflicts.append(_save_conflict(local["id"], older["data"], older.get("device", "")))
        return dict(newer)
    if kind == "thread":
        msgs = {m["id"]: m for m in older["data"].get("messages") or [] if isinstance(m, dict) and m.get("id")}
        msgs.update({m["id"]: m for m in newer["data"].get("messages") or [] if isinstance(m, dict) and m.get("id")})
        data = dict(newer["data"], messages=sorted(msgs.values(), key=lambda m: m.get("ts", 0)))
        data["updated"] = max(local["updated"], remote["updated"])
        return _obj("thread", local["id"], data["updated"], data)
    if kind == "po":
        if (older["data"] or {}).get("note") and older["data"]["note"] != (newer["data"] or {}).get("note"):
            conflicts.append(_save_conflict(f"po-{local['id']}-note.md", older["data"]["note"], older.get("device", "")))
        return dict(newer)
    return dict(newer)  # entry·handoff·paper·settings: 최종 수정 우선


# ---- 로컬에 적용 ----

def apply(obj, on_settings=None):
    kind, oid, data = obj["kind"], obj["id"], obj.get("data")
    if kind == "file":
        if obj.get("deleted") or data is None:
            return  # memory.md·USER.md는 동기화로 지우지 않는다
        if oid == "memory.md":
            storage.save_memory_md(data)
        elif oid == "USER.md":
            storage.save_profile(data)
    elif kind == "thread":
        if obj.get("deleted"):
            storage.delete_thread(oid)
        elif isinstance(data, dict) and re.fullmatch(r"[0-9a-f]{32}", str(data.get("id", ""))):
            storage.THREADS_DIR.mkdir(parents=True, exist_ok=True)
            storage.save_thread(data, update_timestamp=False)
    elif kind == "entry":
        import memory_store

        entry = dict(data or {}, id=oid)
        if obj.get("deleted"):
            entry["deleted"] = obj["deleted"]
        if entry.get("layer") and entry.get("text") is not None:
            memory_store.upsert_raw(entry)
    elif kind == "handoff":
        import handoff

        if data:
            handoff.upsert_raw(dict(data, task_id=oid))
    elif kind == "paper":
        import research_library

        with research_library._lock:
            lib = research_library.load()
            if obj.get("deleted"):
                lib["papers"].pop(oid, None)
                lib["deleted"][oid] = obj["deleted"]
            elif data:
                lib["papers"][oid] = dict(data, id=oid)
                lib["deleted"].pop(oid, None)
            research_library.save(lib)
    elif kind == "settings":
        if on_settings and isinstance(data, dict):
            on_settings({k: v for k, v in data.items() if k in SETTINGS_KEYS}, obj["updated"])
    elif kind == "po":
        _apply_po(oid, obj)


def _apply_po(note_id, obj):
    import po_note

    d = po_note._dir(note_id)
    if obj.get("deleted"):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
        return
    data = obj.get("data") or {}
    d.mkdir(parents=True, exist_ok=True)
    meta = po_note._read_json(d / "meta.json", {"id": note_id, "materials": []})
    meta.update({k: v for k, v in (data.get("meta") or {}).items() if k in ("title", "created", "duration", "engine")})
    meta["id"] = note_id
    meta.setdefault("materials", [])
    meta["updated"] = obj["updated"]
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, key in (("note.md", "note"), ("memo.md", "memo")):
        if data.get(key) is not None:
            (d / name).write_text(data[key], encoding="utf-8")
    (d / "transcript.json").write_text(json.dumps(data.get("transcript") or [], ensure_ascii=False), encoding="utf-8")


# ---- 준비·동기화 ----

def setup(backend, passphrase):
    """원격에 동기화 저장소가 있으면 그 솔트로 키를 만들어 암호를 확인하고, 없으면 새로 만든다. 키(바이트)를 돌려준다."""
    ok, reason = available()
    if not ok:
        raise SyncError(reason)
    meta = backend.read_meta()
    if meta:
        if meta.get("format") != FORMAT:
            raise SyncError(f"지원하지 않는 동기화 형식입니다(format {meta.get('format')}). 앱을 업데이트하세요.")
        key = derive_key(passphrase, base64.b64decode(meta["salt"]))
        if not hmac.compare_digest(Cipher(key).check_value(), meta.get("check", "")):
            raise SyncError("동기화 암호가 다른 기기에서 정한 것과 다릅니다.")
        return key
    salt = secrets.token_bytes(16)
    key = derive_key(passphrase, salt)
    backend.write_meta({"format": FORMAT, "salt": base64.b64encode(salt).decode("ascii"),
                        "check": Cipher(key).check_value(), "created": time.time(), "kdf": "scrypt",
                        "kdf_params": {"n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P}, "cipher": "AES-256-GCM"})
    return key


def save_key(key):
    secret_store.set("sync:key", base64.b64encode(key).decode("ascii"))


def load_key():
    raw = secret_store.get("sync:key")
    return base64.b64decode(raw) if raw else None


def forget_key():
    secret_store.delete("sync:key")


def sync_once(config, backend=None, key=None, device="", device_name="", on_settings=None, now=None):
    """한 번 동기화한다. {"uploaded", "downloaded", "merged", "deleted", "conflicts", "errors", "devices"}"""
    with _lock:
        return _sync(config, backend or backend_from_config(config), key or load_key(), device, device_name,
                     on_settings, now or time.time())


def _sync(config, backend, key, device, device_name, on_settings, now):
    import platform

    if key is None:
        raise SyncError("이 기기에 동기화 키가 없습니다. 동기화를 다시 설정하세요.")
    meta = backend.read_meta()
    cipher = Cipher(key)
    if not meta:
        raise SyncError("원격 동기화 저장소가 없습니다(다른 기기에서 지웠을 수 있습니다). 동기화를 다시 설정하세요.")
    if not hmac.compare_digest(cipher.check_value(), meta.get("check", "")):
        raise SyncError("원격 저장소의 암호가 바뀌었습니다. 동기화를 다시 설정하세요.")
    include = [k for k in INCLUDE if ((config.get("sync") or {}).get("include") or {}).get(k, True)]
    state = load_state()
    items = state.setdefault("items", {})
    report = {"uploaded": 0, "downloaded": 0, "merged": 0, "deleted": 0, "conflicts": [], "errors": [], "devices": []}

    local = collect(include, config)
    local[f"device:{device}"] = _obj("device", device, now, {"name": device_name, "platform": platform.system(),
                                                              "last_seen": now})
    remote_names = backend.list()
    groups = {}
    for name, mtime in remote_names.items():
        m = NAME_RE.match(name)
        if m:
            groups.setdefault(m.group(1), []).append((name, mtime))
    by_name = {info.get("name"): key_ for key_, info in items.items() if info.get("name")}
    remote = {}
    for canon, variants in groups.items():
        known = by_name.get(canon)
        info = items.get(known, {}) if known else {}
        if len(variants) == 1 and known and str(info.get("remote_mtime")) == str(variants[0][1]):
            continue  # 지난번 이후 바뀌지 않았다
        envelopes = []
        for name, _ in variants:
            try:
                envelopes.append(cipher.decrypt(backend.get(name)))
            except (SyncError, OSError) as e:
                report["errors"].append(f"{name}: {e}")
        if not envelopes:
            continue
        env = envelopes[0]
        for other in envelopes[1:]:  # 동기화 클라이언트가 만든 충돌 사본: 합친다
            env = merge(env["key"], env, other, None, report["conflicts"])
            env["key"] = envelopes[0]["key"]
        remote[env["key"]] = (env, canon, variants)

    def upload(key_, obj):
        name = cipher.name(key_)
        envelope = dict(obj, key=key_, device=device)
        mtime = backend.put(name + ".bin", cipher.encrypt(envelope))
        report["uploaded"] += 1
        return name, mtime

    for key_ in sorted(set(local) | set(remote) | set(items)):
        kind = key_.split(":", 1)[0]
        if not _wanted(key_, include):
            continue
        info = items.get(key_, {})
        base = info.get("hash")
        loc = local.get(key_)
        if loc is None and info and not info.get("deleted") and kind in ("thread", "po"):
            if _still_on_disk(kind, key_.split(":", 1)[1]):
                # 2.0: 파일은 있는데 읽지 못했다(깨짐·백신이 잠금). 지운 것으로 보내면 다른 기기의 멀쩡한 사본까지 지워진다
                report["errors"].append(f"{key_}: 이 기기의 파일을 읽지 못해 이번에는 건너뜁니다.")
                continue
            loc = _obj(kind, key_.split(":", 1)[1], now, None, now)  # 지난번 이후 이 기기에서 지웠다
        rem_entry = remote.get(key_)
        rem = rem_entry[0] if rem_entry else None
        l_changed = loc is not None and digest(loc) != base
        r_changed = rem is not None and digest(rem) != base
        try:
            final = None
            if l_changed and r_changed:
                final = merge(key_, loc, rem, info.get("base"), report["conflicts"])
                apply(final, on_settings)
                report["merged"] += 1
            elif r_changed:
                final = rem
                apply(final, on_settings)
                report["downloaded"] += 1
                report["deleted"] += bool(rem.get("deleted"))
            elif l_changed:
                final = loc
            if final is None:
                if rem_entry:  # 바뀌지 않았지만 수정 시각만 다른 경우 기록을 맞춘다
                    info["remote_mtime"] = rem_entry[2][0][1]
                continue
            needs_upload = l_changed or (rem_entry and len(rem_entry[2]) > 1)
            name, mtime = upload(key_, final) if needs_upload else (rem_entry[1], rem_entry[2][0][1])
            if rem_entry and len(rem_entry[2]) > 1:
                for variant, _ in rem_entry[2]:
                    if variant != name + ".bin":
                        backend.delete(variant)
            items[key_] = {"hash": digest(final), "name": name, "remote_mtime": mtime, "deleted": bool(final.get("deleted"))}
            if key_ == "file:memory.md" and final.get("data") is not None:
                items[key_]["base"] = final["data"][:65536]
            if kind == "device":
                items[key_]["device"] = final.get("data") or {}
        except (SyncError, OSError, ValueError, KeyError) as e:
            report["errors"].append(f"{key_}: {type(e).__name__}: {e}")
    state["last_sync"] = now
    save_state(state)
    report["devices"] = sorted(({"id": k.split(":", 1)[1], **info["device"]} for k, info in items.items()
                                if k.startswith("device:") and info.get("device")),
                               key=lambda d: -float(d.get("last_seen") or 0))
    return report


KIND_INCLUDE = {"thread": "threads", "entry": "project", "handoff": "project", "paper": "research",
                "settings": "settings", "po": "po_notes"}


def _wanted(key, include):
    if key.startswith("device:"):
        return True
    if key == "file:memory.md":
        return "memory" in include
    if key == "file:USER.md":
        return "profile" in include
    return KIND_INCLUDE.get(key.split(":", 1)[0]) in include


def wipe(backend):
    """원격 동기화 저장소를 지우고 이 기기의 키·상태도 지운다(로컬 데이터는 남긴다)."""
    backend.wipe()
    forget_key()
    state_path().unlink(missing_ok=True)


def selfcheck():
    """설치된 앱 진단: 암호화 라이브러리와 키 유도·암복호화가 되는지."""
    ok, reason = available()
    if not ok:
        return f"FAIL {reason}"
    try:
        cipher = Cipher(hashlib.scrypt(b"selftest-pass", salt=b"0" * 16, n=2 ** 10, r=8, p=1, dklen=32))
        return "OK" if cipher.decrypt(cipher.encrypt({"x": "확인"})) == {"x": "확인"} else "FAIL roundtrip"
    except Exception as e:
        return f"FAIL {type(e).__name__}: {e}"
