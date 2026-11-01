# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""PO노트: 강의 녹음의 전사(transcript), 강의 자료, 내 메모, AI가 만든 필기 노트(note.md)를 강의마다 보관한다.

<데이터 폴더>/po_notes/<id>/
    meta.json        제목·만든 때·녹음 길이·강의 자료 목록·인식 엔진
    transcript.json  [{"start": 초, "end": 초, "text": 글}]
    note.md          AI가 만든(그리고 사용자가 고친) 필기 노트
    memo.md          강의 중에 직접 적은 메모(노트를 만들 때 함께 참고)
    materials/<mid>/<파일>   강의 자료(PPT·PDF·Word·한글 등). 뽑은 글자는 같은 폴더의 .text에 둔다
"""
import base64
import json
import re
import shutil
import threading
import time
import uuid

import documents
import storage

NOTES_DIR = storage.APP_DIR / "po_notes"
MATERIAL_EXTS = documents.DOCUMENT_EXTS | {".txt", ".md"}
MAX_MATERIAL_BYTES = documents.MAX_DOCUMENT_BYTES
MAX_MATERIALS = 10
MATERIAL_BUDGET = 40000      # 노트 한 번 만들 때 넣는 강의 자료 글자 수
TRANSCRIPT_CHUNK = 24000     # 전사가 이보다 길면 나눠서 부분 노트를 만든 뒤 합친다
TEXT_CACHE = ".text"
_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class NoteError(Exception):
    pass


def _dir(note_id):
    if not isinstance(note_id, str) or not _ID_RE.match(note_id):
        raise NoteError("잘못된 노트 ID입니다.")
    return NOTES_DIR / note_id


# 2.0: 전사(transcript.json)는 받아 적는 스레드(append_segment)와 서버 보정 스레드(apply_refinement)가 함께 고친다.
# 읽고-고치고-쓰는 동안 잠그지 않으면 한쪽이 다른 쪽이 넣은 구간을 덮어 지운다
_transcript_lock = threading.RLock()


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_text(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _meta(note_id):
    meta = _read_json(_dir(note_id) / "meta.json", None)
    if not isinstance(meta, dict):
        raise NoteError("노트를 찾을 수 없습니다.")
    return meta


def _save_meta(meta, touch=True):
    if touch:
        meta["updated"] = time.time()
    storage._write_json(_dir(meta["id"]) / "meta.json", meta)


def fmt_time(seconds):
    seconds = int(seconds or 0)
    h, rest = divmod(seconds, 3600)
    return f"{h}:{rest // 60:02d}:{rest % 60:02d}" if h else f"{rest // 60:02d}:{rest % 60:02d}"


# ---- 노트 목록 ----

def create(title=None):
    note_id = uuid.uuid4().hex
    d = _dir(note_id)
    (d / "materials").mkdir(parents=True)
    now = time.time()
    meta = {"id": note_id, "title": (title or "").strip()[:80] or time.strftime("%m월 %d일 강의", time.localtime(now)),
            "created": now, "updated": now, "duration": 0.0, "materials": [], "engine": ""}
    _save_meta(meta)
    storage._write_json(d / "transcript.json", [])
    return load(note_id)


def list_notes():
    out = []
    if not NOTES_DIR.is_dir():
        return out
    for d in NOTES_DIR.iterdir():
        meta = _read_json(d / "meta.json", None)
        if not isinstance(meta, dict) or not _ID_RE.match(str(meta.get("id", ""))):
            continue
        out.append({"id": meta["id"], "title": meta.get("title", ""), "created": meta.get("created", 0),
                    "updated": meta.get("updated", 0), "duration": meta.get("duration", 0),
                    "materials": len(meta.get("materials", [])), "has_note": (d / "note.md").is_file()})
    return sorted(out, key=lambda n: n["updated"], reverse=True)


def load(note_id):
    meta = _meta(note_id)
    d = _dir(note_id)
    note = d / "note.md"
    memo = d / "memo.md"
    return {**meta, "transcript": transcript(note_id),
            "note": note.read_text(encoding="utf-8") if note.is_file() else "",
            "memo": memo.read_text(encoding="utf-8") if memo.is_file() else "",
            "folder": str(d)}


def rename(note_id, title):
    meta = _meta(note_id)
    title = (title or "").strip()[:80]
    if title:
        meta["title"] = title
        _save_meta(meta)
    return meta


def delete(note_id):
    shutil.rmtree(_dir(note_id), ignore_errors=True)


def save_note(note_id, text):
    _meta(note_id)
    _write_text(_dir(note_id) / "note.md", text or "")
    touch(note_id)


def save_memo(note_id, text):
    _meta(note_id)
    _write_text(_dir(note_id) / "memo.md", text or "")
    touch(note_id)


def touch(note_id, **fields):
    meta = _meta(note_id)
    meta.update(fields)
    _save_meta(meta)
    return meta


# ---- 전사 ----

def transcript(note_id):
    items = _read_json(_dir(note_id) / "transcript.json", [])
    return items if isinstance(items, list) else []


def append_segment(note_id, segment):
    with _transcript_lock:
        return _append_segment(note_id, segment)


def _append_segment(note_id, segment):
    items = transcript(note_id)
    item = {"start": float(segment["start"]), "end": float(segment["end"]), "text": str(segment["text"])}
    for key in ("id", "conf", "src"):
        if segment.get(key) is not None:
            item[key] = segment[key]
    items.append(item)
    items.sort(key=lambda x: x["start"])
    storage._write_json(_dir(note_id) / "transcript.json", items)


def next_segment_id(note_id):
    return max((int(x["id"]) for x in transcript(note_id) if isinstance(x.get("id"), int)), default=-1) + 1


def apply_refinement(note_id, ids, fixed):
    """서버 보정 결과를 전사에 반영한다. fixed가 ids와 같은 길이의 목록이면 구간마다 바꾸고,
    이어 쓴 글(str)이면 그 구간들을 하나로 합친다. 빈 글이 된 구간은 지운다. 바뀐 전사를 돌려준다."""
    with _transcript_lock:
        return _apply_refinement(note_id, ids, fixed)


def _apply_refinement(note_id, ids, fixed):
    items = transcript(note_id)
    targets = [x for x in items if x.get("id") in set(ids)]
    if not targets:
        return items
    if isinstance(fixed, list) and len(fixed) == len(ids):
        by_id = dict(zip(ids, fixed))
        for x in targets:
            x["text"], x["src"] = by_id[x["id"]].strip(), "server"
        items = [x for x in items if x.get("text")]
    else:
        merged = {"id": targets[0]["id"], "start": min(x["start"] for x in targets),
                  "end": max(x["end"] for x in targets), "text": str(fixed).strip(), "src": "server"}
        items = [x for x in items if x not in targets] + ([merged] if merged["text"] else [])
        items.sort(key=lambda x: x["start"])
    storage._write_json(_dir(note_id) / "transcript.json", items)
    return items


def transcript_text(items, stamps=True):
    return "\n".join((f"[{fmt_time(x['start'])}] " if stamps else "") + x["text"] for x in items if x.get("text"))


def export_files(note_id):
    """다른 앱에서 열 수 있게 transcript.md를 쓰고 노트 폴더 경로를 돌려준다."""
    meta = _meta(note_id)
    d = _dir(note_id)
    _write_text(d / "transcript.md", f"# {meta['title']} — 전사\n\n" + transcript_text(transcript(note_id)) + "\n")
    if not (d / "note.md").exists():
        _write_text(d / "note.md", "")
    return d


# ---- 강의 자료 ----

def _safe_name(name):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name or "").strip())[:120].strip(". ")
    return name or "자료"


def upload_material(note_id, upload_id, name, offset, data_b64, last):
    """화면이 강의 자료를 조각으로 나눠 보낸다(첨부 파일과 같은 방식). 마지막 조각이면 자료 정보를 돌려준다."""
    meta = _meta(note_id)
    if not isinstance(upload_id, str) or not _ID_RE.match(upload_id):
        raise NoteError("잘못된 업로드 ID입니다.")
    name = _safe_name(name)
    suffix = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if suffix in documents.LEGACY_EXTS:
        raise NoteError(f"예전 형식({suffix})은 읽을 수 없습니다. {documents.LEGACY_EXTS[suffix]}로 저장한 뒤 올리세요.")
    if suffix not in MATERIAL_EXTS:
        raise NoteError("강의 자료는 PPT·PDF·Word·Excel·한글 문서와 텍스트 파일만 올릴 수 있습니다.")
    d = _dir(note_id) / "materials" / upload_id
    path = d / name
    if offset == 0:
        if len(meta.get("materials", [])) >= MAX_MATERIALS:
            raise NoteError(f"강의 자료는 노트 하나에 {MAX_MATERIALS}개까지 올릴 수 있습니다.")
        if d.exists():
            raise NoteError("이미 올린 자료입니다.")
        d.mkdir(parents=True)
    elif not path.exists() or path.stat().st_size != offset:
        shutil.rmtree(d, ignore_errors=True)
        raise NoteError("파일을 받는 중 순서가 어긋났습니다. 다시 올리세요.")
    chunk = base64.b64decode(data_b64 or "")
    if offset + len(chunk) > MAX_MATERIAL_BYTES:
        shutil.rmtree(d, ignore_errors=True)
        raise NoteError(f"'{name}'이(가) 너무 큽니다({MAX_MATERIAL_BYTES // 1024 // 1024}MB 초과).")
    with open(path, "ab") as f:
        f.write(chunk)
    if not last:
        return None
    try:
        text = _extract(path)
    except NoteError:
        shutil.rmtree(d, ignore_errors=True)
        raise
    (d / TEXT_CACHE).write_text(text, encoding="utf-8")
    item = {"id": upload_id, "name": name, "size": path.stat().st_size, "chars": len(text)}
    meta = _meta(note_id)
    meta.setdefault("materials", []).append(item)
    _save_meta(meta)
    return item


def _extract(path):
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_bytes().decode("utf-8", errors="replace").strip()
    try:
        return documents.extract_text(path)
    except documents.DocumentError as e:
        raise NoteError(f"'{path.name}'을(를) 읽지 못했습니다: {e}") from e


def _material(note_id, material_id):
    meta = _meta(note_id)
    for item in meta.get("materials", []):
        if item.get("id") == material_id:
            return meta, item, _dir(note_id) / "materials" / material_id
    raise NoteError("강의 자료를 찾을 수 없습니다.")


def material_path(note_id, material_id):
    _, item, d = _material(note_id, material_id)
    return d / item["name"]


def material_text(note_id, material_id):
    _, item, d = _material(note_id, material_id)
    try:
        return (d / TEXT_CACHE).read_text(encoding="utf-8")
    except FileNotFoundError:
        text = _extract(d / item["name"])
        (d / TEXT_CACHE).write_text(text, encoding="utf-8")
        return text


def remove_material(note_id, material_id):
    meta, item, d = _material(note_id, material_id)
    meta["materials"] = [m for m in meta["materials"] if m is not item]
    shutil.rmtree(d, ignore_errors=True)
    _save_meta(meta)
    return meta


def vocabulary(note_id, limit=300):
    """강의 자료에서 전문 용어 후보(영문 단어·약어, 긴 낱말)를 뽑는다. 서버 음성 인식에 힌트로 준다."""
    words, seen = [], set()
    for item in _meta(note_id).get("materials", []):
        try:
            text = material_text(note_id, item["id"])
        except NoteError:
            continue
        for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}|[가-힣]{4,}", text):
            if w.lower() not in seen:
                seen.add(w.lower())
                words.append(w)
    return ", ".join(words)[:limit]


# ---- 필기 노트 만들기 ----

NOTE_RULES = """작성 규칙:
- 강의 자료가 있으면 자료의 순서(슬라이드·페이지)를 뼈대로 삼아 `## 제목` 단위로 나누고, 제목 옆에 `(슬라이드 3)`·`(p. 5)`처럼 해당 위치를 적으세요.
- 각 부분에 전사에 나온 설명·예시·이유·주의할 점을 자료 내용과 합쳐 학생의 필기처럼 정리하세요. 자료를 그대로 베끼지 마세요.
- 자료에 없고 말로만 나온 중요한 내용은 `> 💬 강의 중:` 인용으로 표시하세요. 💬는 전사에 실제로 있는 말에만 붙이세요.
- 전사에 나온 "시험", "중요", "꼭", "다음 시간" 같은 강조·공지·과제는 `⭐`와 함께 빠짐없이 남기세요. 전사에 없는 강조·시험 범위·과제를 만들지 마세요.
- 전사는 음성 인식 결과라 틀린 글자가 있을 수 있습니다. 강의 자료와 문맥으로 바로잡되, 전사와 자료 어디에도 없는 교수님의 말이나 예시를 지어내지 마세요.
- 이해를 돕는 일반 지식(정의·유도 등)을 덧붙일 때는 `(보충)`이라고 표시하세요. 강의와 관계없어 보이는 전사는 노트에 넣지 마세요.
- 수식은 LaTeX($...$, $$...$$), 코드는 코드 블록으로 쓰세요. 표가 알맞으면 Markdown 표를 쓰세요.
- 내 메모가 있으면 그 내용과 질문을 반영하세요.
- Markdown 노트만 출력하세요. 노트 밖의 인사말이나 설명은 쓰지 마세요."""

FINAL_SECTIONS = """노트 맨 위에는 `# 강의 제목`과 한 줄 요약을, 맨 아래에는 다음 절을 두세요:
## 핵심 정리 (3~7개 글머리 기호)
## 용어 정리 (용어: 뜻)
## 확인할 것·질문 (이해가 덜 된 부분, 공지·과제)"""


def materials_block(note_id, budget=MATERIAL_BUDGET):
    meta = _meta(note_id)
    items = meta.get("materials", [])
    if not items:
        return ""
    share = max(2000, budget // len(items))
    parts = []
    for item in items:
        try:
            text = material_text(note_id, item["id"])
        except NoteError as e:
            text = f"({e})"
        if len(text) > share:
            text = text[:share] + "\n…(자료가 길어 뒷부분을 줄였습니다)"
        parts.append(f"### 자료: {item['name']}\n{text}")
    return "\n\n".join(parts)


def _chunks(items, size=TRANSCRIPT_CHUNK):
    chunks, cur, n = [], [], 0
    for x in items:
        line = f"[{fmt_time(x['start'])}] {x['text']}"
        if cur and n + len(line) > size:
            chunks.append("\n".join(cur))
            cur, n = [], 0
        cur.append(line)
        n += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def build_prompts(note_id):
    """[(단계 이름, 프롬프트)]와 마지막 합치기 함수가 쓸 템플릿. 전사가 길면 부분 노트 → 합치기 두 단계로 나눈다."""
    meta = _meta(note_id)
    d = _dir(note_id)
    memo = (d / "memo.md").read_text(encoding="utf-8").strip() if (d / "memo.md").is_file() else ""
    items = transcript(note_id)
    mats = materials_block(note_id)
    if not items and not mats:
        raise NoteError("녹음한 전사나 강의 자료가 있어야 노트를 만들 수 있습니다.")
    head = f"강의 제목: {meta['title']}\n"
    memo_block = f"\n[내 메모]\n{memo}\n" if memo else ""
    intro = "당신은 대학 강의를 들은 학생의 필기를 정리해 주는 조교입니다. "
    chunks = _chunks(items)
    if len(chunks) <= 1:
        prompt = (intro + "아래 강의 자료와 강의 음성 전사를 함께 보고, 복습용 Markdown 필기 노트를 만드세요.\n\n"
                  f"{NOTE_RULES}\n{FINAL_SECTIONS}\n\n{head}{memo_block}\n[강의 자료]\n{mats or '(없음)'}\n\n"
                  f"[강의 전사]\n{chunks[0] if chunks else '(녹음 없음 — 자료만으로 정리하세요)'}")
        return [("노트 작성", prompt)], None
    small_mats = materials_block(note_id, budget=MATERIAL_BUDGET // 2)
    steps = []
    for i, chunk in enumerate(chunks, 1):
        steps.append((f"부분 노트 {i}/{len(chunks)}", intro +
                      f"긴 강의를 {len(chunks)}부분으로 나눠 정리하고 있습니다. 지금은 {i}번째 부분입니다. "
                      "이 부분의 전사만 정리해 Markdown 부분 노트를 만드세요(요약·용어 정리 절은 쓰지 마세요).\n\n"
                      f"{NOTE_RULES}\n\n{head}[강의 자료(참고)]\n{small_mats or '(없음)'}\n\n[강의 전사 {i}부분]\n{chunk}"))
    merge = (intro + "아래는 한 강의를 부분별로 정리한 노트들입니다. 겹치는 내용을 합치고 강의 자료의 순서에 맞춰 "
             "하나의 Markdown 필기 노트로 다시 쓰세요. 부분 노트에 있는 설명·예시·강조는 빠뜨리지 마세요.\n\n"
             f"{NOTE_RULES}\n{FINAL_SECTIONS}\n\n{head}{memo_block}\n[부분 노트]\n{{parts}}")
    return steps, merge


def generate(note_id, ask, on_status=None, on_delta=None):
    """ask(prompt, on_delta)로 모델을 불러 note.md를 만든다. 만든 글을 돌려준다."""
    steps, merge = build_prompts(note_id)
    outputs = []
    for i, (label, prompt) in enumerate(steps):
        if on_status:
            on_status(label)
        last = merge is None and i == len(steps) - 1
        outputs.append(ask(prompt, on_delta if last else None).strip())
    if merge is not None:
        if on_status:
            on_status("부분 노트 합치기")
        parts = "\n\n---\n\n".join(f"<부분 {i}>\n{t}" for i, t in enumerate(outputs, 1))
        outputs.append(ask(merge.replace("{parts}", parts), on_delta).strip())
    text = _strip_fence(outputs[-1])
    save_note(note_id, text)
    return text


def _strip_fence(text):
    """모델이 노트 전체를 ```markdown 코드 블록으로 감싸 보내면 벗긴다."""
    m = re.fullmatch(r"\s*```(?:markdown|md)?\s*\n(.*)\n```\s*", text, re.DOTALL)
    return m.group(1).strip() if m else text
