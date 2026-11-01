# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""대화 스레드와 설정을 %APPDATA%\\PostechChat(맥은 ~/Library/Application Support/PostechChat) 아래에 JSON으로, 메모리와 사용자 정보를 Markdown으로 저장한다."""
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path


def _app_dir():
    if os.environ.get("APPDATA"):
        base = os.environ["APPDATA"]
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = str(Path.home() / ".config")
    return Path(base) / "PostechChat"


APP_DIR = _app_dir()
THREADS_DIR = APP_DIR / "threads"
USER_SKILLS_DIR = APP_DIR / "skills"
CONFIG_PATH = APP_DIR / "config.json"
MEMORY_PATH = APP_DIR / "memory.md"
OLD_MEMORY_PATH = APP_DIR / "memory.json"  # 1.4 이전 형식. 처음 읽을 때 memory.md로 옮긴다
PROFILE_PATH = APP_DIR / "USER.md"  # 사용자 정보. INIT.md처럼 모든 대화에 들어간다
ATTACH_DIR = APP_DIR / "attachments"
MCP_PATH = APP_DIR / "mcp.json"  # 외부 MCP 서버 설정(Claude Desktop과 같은 형식)
USAGE_PATH = APP_DIR / "usage.json"  # 날짜별 모델 API 사용량(이 앱에서 보낸 것만)
USAGE_KEEP_DAYS = 400

DEFAULT_CONFIG = {
    "api_key": "",
    "workspace": "",
    "agent_mode": True,
    "history_messages": 20,
    "share_threads": True,  # 새 질문과 관련된 다른 대화 내용을 자동으로 참고
}


def ensure_dirs():
    for d in (THREADS_DIR, USER_SKILLS_DIR, ATTACH_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _write_json(path, data):
    # 2.0: 임시 파일 이름을 쓰기마다 다르게(동기화·채팅 스레드가 같은 파일을 동시에 써도 서로의 .tmp를 덮지 않게) 하고,
    # 바꾸기 전에 디스크에 내려 둔다(정전 뒤 config.json·대화가 0바이트로 남지 않게)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


# 1.18.9: API 키·토큰은 config.json(평문, 백업에 복사됨)이 아니라 비밀 저장소(secret_store: OS 키체인, 안 되면 0600 파일)에 둔다.
# 앱 코드는 그대로 config["api_key"]처럼 쓴다: load_config가 채워 주고 save_config가 빼서 비밀 저장소에 넣는다.
# 예전 config.json에 평문으로 남은 값은 처음 save_config할 때 옮겨지고 파일에서 지워진다(migrate_config_secrets).
CONFIG_SECRET_KEYS = ("api_key", "anthropic_api_key", "openai_api_key", "notion_token", "firecrawl_key")
# 키들은 비밀 저장소 항목 하나(JSON)로 묶는다: 키체인을 읽는 횟수(macOS에서 업데이트 뒤 접근 허용을 묻는 창)를 한 번으로.
CONFIG_SECRETS_NAME = "config:secrets"


# 2.0: 시작할 때 비밀 저장소를 읽지 못했다는 표시(설정 dict 안에만 있고 config.json에는 쓰지 않는다).
# 이 표시가 있는 동안 save_config는 저장된 키를 지우지 않는다(macOS 업데이트 뒤 키체인 접근을 한 번 거부했다가
# 다음 저장 때 허용하면, 비어 보이던 설정으로 키 다섯 개를 모두 지우던 문제).
SECRETS_UNREADABLE = "_secrets_unreadable"


def _load_config_secrets(strict=False):
    import secret_store

    data = secret_store.get_json(CONFIG_SECRETS_NAME, strict=strict)
    return {k: str(v) for k, v in data.items() if k in CONFIG_SECRET_KEYS and v} if isinstance(data, dict) else {}


def load_config():
    import secret_store

    cfg = dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):  # 손으로 고쳐 []·null이 된 파일이면 기본값으로 연다(앱이 아예 안 열리지 않게)
            cfg.update(raw)
    except (OSError, ValueError):
        pass
    cfg.pop(SECRETS_UNREADABLE, None)
    try:
        secrets = _load_config_secrets(strict=True)
    except secret_store.SecretStoreError:
        secrets = {}
        cfg[SECRETS_UNREADABLE] = True
    for key, value in secrets.items():
        if not cfg.get(key):   # 파일에 평문 값이 남아 있으면(옮기기 전) 그 값을 쓴다
            cfg[key] = value
    return cfg


def save_config(cfg):
    import secret_store

    data = dict(cfg)
    unreadable = bool(data.pop(SECRETS_UNREADABLE, False))
    secrets = {}
    for key in CONFIG_SECRET_KEYS:
        value = str(data.pop(key, "") or "")
        if value:
            secrets[key] = value
    try:
        stored = _load_config_secrets(strict=True)
    except secret_store.SecretStoreError:
        stored = None  # 지금도 읽지 못한다: 비교할 수 없으니 지우지 않는다
    if unreadable and stored is not None:
        # 시작 때 못 읽은 키를 이제 읽었다: 저장된 키에 이번에 입력한 키만 덮어쓰고, 설정 dict에도 되살린다
        secrets = {**stored, **secrets}
        for key, value in secrets.items():
            if not cfg.get(key):
                cfg[key] = value
        cfg.pop(SECRETS_UNREADABLE, None)
        unreadable = False
    if stored != secrets:   # 바뀌었을 때만 쓴다(모두 비면 지운다)
        if secrets:
            secret_store.set_json(CONFIG_SECRETS_NAME, secrets)
        elif stored and not unreadable:
            secret_store.delete(CONFIG_SECRETS_NAME)
    _write_json(CONFIG_PATH, data)
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def migrate_config_secrets(cfg):
    """config.json에 평문 키가 남아 있으면 비밀 저장소로 옮긴다(앱 시작 때 한 번)."""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(raw, dict) and any(k in raw for k in CONFIG_SECRET_KEYS):
        save_config(cfg)


def make_message(role, content, **extra):
    return {"id": uuid.uuid4().hex, "role": role, "content": content, "ts": time.time(), **extra}


def new_thread():
    now = time.time()
    thread = {"id": uuid.uuid4().hex, "title": "새 대화", "created": now, "updated": now, "messages": []}
    save_thread(thread)
    return thread


def save_thread(thread, update_timestamp=True):
    if update_timestamp:
        thread["updated"] = time.time()
    _write_json(THREADS_DIR / f"{thread['id']}.json", thread)


def load_thread(thread_id):
    try:
        return json.loads((THREADS_DIR / f"{thread_id}.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def list_threads():
    threads = []
    for p in THREADS_DIR.glob("*.json"):
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        threads.append({"id": t["id"], "title": t.get("title", "새 대화"), "updated": t.get("updated", 0)})
    threads.sort(key=lambda t: t["updated"], reverse=True)
    return threads


def delete_thread(thread_id):
    thread = load_thread(thread_id)
    for m in (thread or {}).get("messages", []):
        for a in m.get("attachments") or []:
            delete_attachment(a.get("id"))
    (THREADS_DIR / f"{thread_id}.json").unlink(missing_ok=True)


# ---- 메모리: 모든 대화에 공통으로 들어가는 기억 (memory.md) ----
# "- "로 시작하는 줄 하나가 기억 하나다. 사용자가 파일을 직접 고쳐도 되고, 제목이나 메모를 더 써도
# 모두 모델에게 전달된다. <!-- --> 안의 안내문만 빠진다.

MEMORY_TEMPLATE = """# 메모리

<!-- 모든 대화에 함께 전달되는 기억입니다. 한 줄에 하나씩 "- "로 시작해 적으세요.
     제목이나 설명을 자유롭게 더 써도 됩니다. 이 안내문은 모델에게 전달되지 않습니다. -->

"""

PROFILE_TEMPLATE = """# 사용자 정보

<!-- 나에 대한 정보입니다. 모든 대화에 함께 전달되어 답변을 나에게 맞추는 데 쓰입니다.
     직접 고쳐도 되고, 채팅창에서 /user 를 입력하면 지금까지의 대화를 바탕으로 AI가 작성·업데이트합니다.
     비밀번호나 API 키 같은 비밀 정보는 적지 마세요. 이 안내문은 모델에게 전달되지 않습니다. -->

## 기본 정보
- 

## 하는 일·관심 분야
- 

## 선호하는 답변 방식
- 
"""

_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*\S)\s*$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _write_text(path, text):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _memory_id(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def read_memory_md():
    """memory.md 원문. 없으면 템플릿으로 만든다(예전 memory.json이 있으면 옮겨 온다)."""
    try:
        return MEMORY_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    text = MEMORY_TEMPLATE
    try:
        items = json.loads(OLD_MEMORY_PATH.read_text(encoding="utf-8"))
        lines = [f"- {' '.join(str(m.get('text', '')).split())}" for m in items if isinstance(m, dict) and m.get("text")]
        text += "\n".join(lines) + ("\n" if lines else "")
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        pass
    APP_DIR.mkdir(parents=True, exist_ok=True)
    _write_text(MEMORY_PATH, text)
    return text


def save_memory_md(text):
    _write_text(MEMORY_PATH, str(text).replace("\r\n", "\n"))


def load_memory():
    """memory.md의 "- " 줄 목록. 같은 내용의 줄은 하나로 본다."""
    items, seen = [], set()
    for line in _COMMENT_RE.sub("", read_memory_md()).splitlines():
        m = _BULLET_RE.match(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            items.append({"id": _memory_id(m.group(1)), "text": m.group(1)})
    return items


def add_memory(text):
    text = " ".join(str(text).split())[:500]
    if not text or any(m["text"] == text for m in load_memory()):
        return None
    md = read_memory_md()
    if md and not md.endswith("\n"):
        md += "\n"
    save_memory_md(md + f"- {text}\n")
    return {"id": _memory_id(text), "text": text}


def delete_memory(memory_id):
    lines = read_memory_md().splitlines(keepends=True)
    kept = []
    for line in lines:
        m = _BULLET_RE.match(line)
        if m and _memory_id(m.group(1)) == memory_id:
            continue
        kept.append(line)
    save_memory_md("".join(kept))


def note_for_prompt(text):
    """Markdown 원문에서 안내문(<!-- -->)과 내용 없는 빈 항목·제목을 빼고 모델에게 줄 글만 남긴다."""
    lines = []
    for line in _COMMENT_RE.sub("", text or "").splitlines():
        if re.fullmatch(r"\s*[-*+]\s*", line):
            continue  # 템플릿의 빈 "- " 항목
        lines.append(line.rstrip())
    # 아래에 내용이 없는 제목은 뺀다
    def level(line):
        return len(line) - len(line.lstrip("#")) if line.startswith("#") else 0

    out = []
    for i, line in enumerate(lines):
        if level(line):
            rest = next((l for l in lines[i + 1:] if l.strip()), "")
            if not rest or 0 < level(rest) <= level(line):
                continue
        out.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return text if any(not l.startswith("#") and l.strip() for l in text.splitlines()) else ""


# ---- 사용자 정보 (USER.md) ----

def read_profile():
    """USER.md 원문. 없으면 빈 템플릿을 돌려준다(파일은 만들지 않는다)."""
    try:
        return PROFILE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PROFILE_TEMPLATE


def profile_exists():
    return PROFILE_PATH.exists()


def save_profile(text):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    _write_text(PROFILE_PATH, str(text).replace("\r\n", "\n"))


def recent_user_messages(limit_chars=12000, exclude_prefix=("/user",)):
    """모든 대화의 사용자 메시지를 최근 것부터 모은다(사용자 정보 정리용). [(대화 제목, 시각, 내용)]"""
    msgs = []
    for p in THREADS_DIR.glob("*.json"):
        try:
            thread = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for m in thread.get("messages", []):
            content = str(m.get("content", "")).strip()
            if m.get("role") == "user" and content and not content.lower().startswith(exclude_prefix):
                msgs.append((thread.get("title", ""), m.get("ts", 0), content))
    msgs.sort(key=lambda m: m[1], reverse=True)
    out, total = [], 0
    for title, ts, content in msgs:
        content = content if len(content) <= 600 else content[:600] + " ..."
        if total + len(content) > limit_chars:
            break
        out.append((title, ts, content))
        total += len(content)
    return out


# ---- 백업 ----

BACKUP_MAX_BYTES = 300 * 1024 * 1024


def backup_user_data(label):
    """설정·메모리·사용자 정보·MCP 설정·대화를 backups/<시각>-<label>/에 복사한다. 첨부·모델 파일은 뺀다.
    대화가 너무 크면(300MB 초과) 대화는 빼고 나머지만. 백업 폴더 경로(없으면 None)."""
    sources = [p for p in (CONFIG_PATH, MEMORY_PATH, PROFILE_PATH, MCP_PATH, USAGE_PATH, OLD_MEMORY_PATH) if p.is_file()]
    threads = sorted(THREADS_DIR.glob("*.json")) if THREADS_DIR.is_dir() else []
    if not sources and not threads:
        return None
    target = APP_DIR / "backups" / f"{time.strftime('%Y%m%d-%H%M%S')}-{label}"
    try:
        target.mkdir(parents=True, exist_ok=True)
        for p in sources:
            shutil.copy2(p, target / p.name)
        if sum(p.stat().st_size for p in threads) <= BACKUP_MAX_BYTES:
            (target / "threads").mkdir(exist_ok=True)
            for p in threads:
                shutil.copy2(p, target / "threads" / p.name)
        (target / "README.txt").write_text(
            "POSCHAT 백업입니다. 되돌리려면 앱을 끈 뒤 이 폴더의 파일을 데이터 폴더(이 폴더의 두 단계 위)에 "
            "같은 이름으로 덮어쓰세요. 자세한 방법: docs/migration-1.10.md\n", encoding="utf-8")
    except OSError:
        return None
    return target


# ---- 첨부 파일: attachments/<id>/<파일 이름> ----
# 보내기 전(화면에서 고른 상태)의 파일에는 .staged 표시가 있다. 메시지에 붙으면 지운다.

STAGED_MARK = ".staged"


def attachment_dir(attach_id):
    if not re.fullmatch(r"[0-9a-f]{32}", str(attach_id)):
        raise ValueError("잘못된 첨부 파일 id")
    return ATTACH_DIR / attach_id


def attachment_file(attach_id):
    """첨부 파일의 실제 경로. 없으면 None."""
    try:
        d = attachment_dir(attach_id)
    except ValueError:
        return None
    files = [p for p in d.glob("*") if p.is_file() and not p.name.startswith(".")] if d.is_dir() else []
    return files[0] if files else None


def delete_attachment(attach_id):
    try:
        shutil.rmtree(attachment_dir(attach_id), ignore_errors=True)
    except ValueError:
        pass


def cleanup_staged(max_age=24 * 3600):
    """보내지 않고 남은 첨부 파일(앱이 꺼지는 등)을 지운다."""
    now = time.time()
    for mark in ATTACH_DIR.glob(f"*/{STAGED_MARK}"):
        try:
            if now - mark.stat().st_mtime > max_age:
                shutil.rmtree(mark.parent, ignore_errors=True)
        except OSError:
            pass


# ---- 모델 API 사용량 ----
# POSTECH GenAI API는 남은 한도를 알려 주지 않으므로, 이 앱이 보낸 호출을 날짜별로 센다.
# 토큰 수는 서버가 응답에 사용량을 담아 줄 때만 더한다(token_calls는 토큰 수를 받은 호출 수).

_usage_lock = threading.Lock()


def _load_usage():
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def record_usage(mode, model, usage):
    day = time.strftime("%Y-%m-%d")
    with _usage_lock:
        data = _load_usage()
        entry = data.setdefault(day, {"calls": 0, "token_calls": 0, "input_tokens": 0, "output_tokens": 0})
        entry["calls"] += 1
        if usage:
            entry["token_calls"] += 1
            entry["input_tokens"] += int(usage.get("input_tokens") or 0)
            entry["output_tokens"] += int(usage.get("output_tokens") or 0)
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - USAGE_KEEP_DAYS * 86400))
        data = {k: v for k, v in data.items() if k >= cutoff}
        APP_DIR.mkdir(parents=True, exist_ok=True)
        _write_json(USAGE_PATH, data)


def usage_summary():
    """오늘·이번 달·지난 30일 합계."""
    data = _load_usage()
    today = time.strftime("%Y-%m-%d")
    month = today[:7]
    since30 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 29 * 86400))

    def total(keep):
        out = {"calls": 0, "token_calls": 0, "input_tokens": 0, "output_tokens": 0}
        for day, entry in data.items():
            if keep(day) and isinstance(entry, dict):
                for k in out:
                    out[k] += int(entry.get(k) or 0)
        return out

    # 1.19 그래프: 최근 30일의 날짜별 값(기록이 없는 날은 0)
    daily = []
    for i in range(29, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400))
        entry = data.get(day) if isinstance(data.get(day), dict) else {}
        daily.append({"day": day, **{k: int(entry.get(k) or 0) for k in ("calls", "input_tokens", "output_tokens")}})
    return {"today": total(lambda d: d == today), "month": total(lambda d: d.startswith(month)),
            "last30": total(lambda d: d >= since30), "month_name": month, "daily": daily}


# ---- 다른 대화 검색 ----

def _bigrams(text):
    """한국어는 조사가 붙어 단어 단위로는 잘 안 맞으므로 글자 2개 단위로 비교한다."""
    grams = set()
    for word in re.findall(r"[0-9a-z가-힣]+", text.lower()):
        grams.update(word[i:i + 2] for i in range(len(word) - 1))
    return grams


def shared_bigrams(q, text):
    """len(q & _bigrams(text))와 같은 값. 본문의 글자쌍 집합을 만들지 않고 q의 글자쌍이 본문에 있는지만 센다
    (글자쌍은 낱말 안에서만 만들어지므로 본문에 부분 문자열로 있으면 같은 낱말 안의 쌍이다). 대화·문서가 많을 때 메모리와 시간을 아낀다."""
    text = text.lower()
    return sum(1 for g in q if g in text)


def search_threads(query, exclude_id=None, limit=3, min_score=0.35, min_shared=4):
    """다른 대화에서 query와 겹치는 메시지를 찾는다. 대화마다 가장 잘 맞는 메시지 하나씩.
    메시지 본문은 thread_index의 색인에서 찾고, 이긴 대화만 파일에서 읽는다."""
    import thread_index

    q = _bigrams(query)
    if len(q) < 3:
        return []
    out = []
    for tid, name, idx, role, score in thread_index.candidates(q, exclude_id, min_score, min_shared)[:limit]:
        try:
            thread = json.loads((THREADS_DIR / name).read_text(encoding="utf-8"))
            m = thread["messages"][idx]
        except (OSError, json.JSONDecodeError, KeyError, IndexError):
            continue  # 찾는 사이에 대화가 바뀌었다
        out.append({"thread_id": tid, "title": thread.get("title", ""), "role": role,
                    "content": m["content"], "ts": m.get("ts", 0), "score": round(score, 2)})
    return out
