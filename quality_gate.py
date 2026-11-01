# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""작업별 답변 검증(QualityGate, 1.17): 로컬 모델의 답을 그대로 믿지 않고, 규칙으로 확인할 수 있는 것만 확인한다.

check(area, answer, ctx) -> GateResult
- 모델이 스스로 말한 '확신'은 보지 않는다. 검증할 수 있는 항목(verifiable)과 실패 유형(failures)을 따로 남긴다.
- area: general | json | agent_step | browser | paper | code | lab
    general     빈 답, 길이 제한으로 끊김, 같은 줄 반복, 언어(한국어 요청에 한국어 답), JSON 요구 시 JSON
    agent_step  {"action": ...} JSON이고 action이 허용 목록 안
    browser     답에 나온 주소가 원문(웹페이지)에 있는지, 따옴표로 인용한 글이 원문에 있는지
    paper       쪽 번호(p. N)가 문서 범위 안인지, 숫자(단위 포함)가 원문에 있는지, 인용한 글이 원문에 있는지
    code        코드 블록(Python·JSON)이 문법에 맞는지
    lab         답의 숫자가 첨부한 실험 기록에 있는지(없는 숫자는 '추정'이라고 밝혔는지)
- 실패하면 cascade(adaptive_engine)가 같은 로컬 모델로 다시 할지, Cloud로 올릴지 정한다.
"""
import ast
import json
import re
from dataclasses import asdict, dataclass, field

HANGUL = re.compile(r"[가-힣]")
UNTRUSTED_BLOCK = re.compile(r"\[외부 데이터: ([^\]—]*)[^\]]*\]\n(.*?)\n\[외부 데이터 끝\]", re.S)
URL_RE = re.compile(r"https?://[^\s<>\")\]]+")
QUOTE_RE = re.compile(r"[\"“”'‘’「『]([^\"“”'‘’」』\n]{12,200})[\"“”'‘’」』]")
PAGE_RE = re.compile(r"(?i)\b(?:p|pp|page)\.?\s*(\d{1,4})(?:\s*[-–~]\s*(\d{1,4}))?|(\d{1,4})\s*쪽")
NUM_RE = re.compile(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.\d+)?)\s*(%|ms|s|초|배|dB|Hz|kHz|MHz|GHz|nm|mm|cm|m|kg|g|V|mV|A|mA|W|mW|bit|비트|개|명|회)?")
ESTIMATE_RE = re.compile(r"(추정|어림|대략|약\s|예상|가정|approximately|estimate)")
CODE_BLOCK = re.compile(r"```([A-Za-z0-9_+\-]*)\n(.*?)```", re.S)
AGENT_ACTIONS = {"list", "read", "search", "write", "edit", "run", "done", "recall", "skill", "mcp", "browser_read",
                 "browser_open", "browser_snapshot", "browser_click", "browser_type", "browser_select", "browser_scroll",
                 "browser_wait", "browser_extract", "browser_screenshot", "browser_back", "browser_forward", "browser_refresh",
                 "paper_read", "plan",
                 # 2.0: 실제 도구(agent.Agent·code_agent.CodeAgent의 _tool_*)와 맞춘다 — 빠지면 맞는 단계도 실패로 보고 Cloud로 올렸다.
                 # agent를 가져오면 순환 import라 목록으로 두고, 시험(test_code_hardening_2_0)이 _tool_* 전부가 들었는지 확인한다.
                 "glob", "multi_edit", "job_output", "job_stop", "web_search", "web_fetch", "web_download", "paper_search",
                 "plms_courses", "plms_course", "plms_read"}


@dataclass
class GateResult:
    ok: bool = True
    verifiable: bool = False                       # 규칙으로 확인한 항목이 하나라도 있었는지
    failures: list = field(default_factory=list)   # 실패 코드: empty, truncated, repetition, language, json, action, url, quote,
    #                                                page, number, syntax, unsupported_number
    checks: list = field(default_factory=list)     # 확인한 항목 코드
    retryable: bool = False                        # 같은 로컬 모델로 다시 해 볼 만한 실패(형식 문제)인지
    detail: str = ""                               # 사용자에게 보이는 짧은 설명(내용은 담지 않는다)

    def to_dict(self):
        return asdict(self)


FAIL_LABELS = {
    "empty": "빈 답", "truncated": "답이 중간에 끊김", "repetition": "같은 말 반복", "language": "요청한 언어가 아님",
    "json": "JSON 형식이 아님", "action": "단계 형식이 아님", "url": "원문에 없는 주소", "quote": "원문에 없는 인용",
    "page": "문서에 없는 쪽 번호", "number": "원문에 없는 수치", "syntax": "코드 문법 오류", "unsupported_number": "근거 없는 수치",
}
RETRYABLE = {"empty", "json", "action", "repetition", "truncated"}


def sources(prompt):
    """프롬프트 안의 외부 데이터 블록 [(출처 이름, 원문)]."""
    return [(m.group(1).strip(), m.group(2)) for m in UNTRUSTED_BLOCK.finditer(str(prompt or ""))]


def _norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _json_object(text):
    start = text.find("{")
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _repetition(text):
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 8]
    if len(lines) >= 6:
        top = max(lines.count(x) for x in set(lines))
        if top >= max(4, len(lines) // 2):
            return True
    return bool(re.search(r"(.{20,}?)\1{4,}", text, re.S))


LABEL_BEFORE = re.compile(r"(?i)(run|번째|table|fig\.?|figure|eq\.?|표|그림|식|p\.|pp\.|page|section|§|#|v|버전|단계|step)\s*$")


def _numbers(text, measured_only=False):
    """[(원문, 값, 단위)]. measured_only면 측정값처럼 보이는 수(소수·단위가 있거나 100 이상)만, 번호(Run 7, 표 2, p. 3)는 뺀다."""
    out = []
    for m in NUM_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        unit = m.group(2) or ""
        if measured_only:
            if LABEL_BEFORE.search(text[max(0, m.start() - 10):m.start()]):
                continue
            if "." not in raw and not unit and value < 100:
                continue
        out.append((raw, value, unit))
    return out


def check(area, answer, ctx=None):
    """ctx: {"prompt", "korean": bool, "json": bool, "done_reason", "pages": 쪽 수, "allowed_actions": set}"""
    ctx = ctx or {}
    text = str(answer or "")
    r = GateResult()

    def fail(code):
        if code not in r.failures:
            r.failures.append(code)

    def checked(code):
        r.verifiable = True
        r.checks.append(code)

    # 공통
    checked("empty")
    if not text.strip():
        fail("empty")
    if ctx.get("done_reason") == "length":
        checked("truncated")
        fail("truncated")
    checked("repetition")
    if text.strip() and _repetition(text):
        fail("repetition")
    want_json = ctx.get("json") or area in ("json", "agent_step")
    if want_json:
        checked("json")
        obj = _json_object(text)
        if obj is None:
            fail("json")
        elif area == "agent_step":
            checked("action")
            allowed = ctx.get("allowed_actions") or AGENT_ACTIONS
            if not isinstance(obj.get("action"), str) or obj["action"] not in allowed:
                fail("action")
    elif ctx.get("korean") and len(text.strip()) >= 40:
        checked("language")
        hangul = len(HANGUL.findall(text))
        letters = len(re.findall(r"[A-Za-z가-힣]", CODE_BLOCK.sub("", text)))
        if letters >= 40 and hangul / max(1, letters) < 0.2:
            fail("language")
    src = sources(ctx.get("prompt"))
    joined = _norm(" ".join(body for _, body in src))
    raw_joined = " ".join(body for _, body in src)
    if area in ("browser", "paper", "lab", "research") and src:
        urls = URL_RE.findall(text)
        if urls:
            checked("url")
            known = set(URL_RE.findall(raw_joined)) | {u.rstrip("/.,") for u in URL_RE.findall(raw_joined)}
            if any(u.rstrip("/.,") not in known and u not in known for u in urls):
                fail("url")
        quotes = [q for q in QUOTE_RE.findall(text) if len(q.strip()) >= 12]
        if quotes:
            checked("quote")
            if any(_norm(q) not in joined for q in quotes):
                fail("quote")
    if area == "paper":
        pages = int(ctx.get("pages") or 0)
        found = [(int(a or c), int(b or a or c)) for a, b, c in PAGE_RE.findall(text) if (a or c)]
        if pages and found:
            checked("page")
            if any(p < 1 or q > pages for p, q in found):
                fail("page")
    if area in ("paper", "lab") and src:
        nums = _numbers(CODE_BLOCK.sub("", text), measured_only=True)
        if nums:
            checked("number")
            src_values = {v for _, v, _ in _numbers(raw_joined)}
            missing = [n for n in nums if n[1] not in src_values and not any(abs(n[1] - s) <= 1e-9 * max(1, abs(s)) for s in src_values)]
            if missing and len(missing) / len(nums) > 0.3:
                # 계산해서 낸 값일 수 있다: '추정·계산'이라고 밝혔으면 근거 없는 수치로만 남기고 실패로 보지 않는다
                if area == "lab" and ESTIMATE_RE.search(text):
                    r.checks.append("unsupported_number_disclosed")
                else:
                    fail("number" if area == "paper" else "unsupported_number")
    if area in ("code", "general", "lab", "paper", "browser"):
        for lang, body in CODE_BLOCK.findall(text):
            lang = lang.lower()
            if lang in ("python", "py"):
                checked("syntax")
                try:
                    ast.parse(body)
                except SyntaxError:
                    fail("syntax")
            elif lang == "json":
                checked("syntax")
                try:
                    json.loads(body)
                except ValueError:
                    fail("syntax")
    r.ok = not r.failures
    r.retryable = bool(r.failures) and all(f in RETRYABLE for f in r.failures)
    r.detail = ", ".join(FAIL_LABELS.get(f, f) for f in r.failures)
    return r


def area_for(task, purpose):
    """라우터의 작업 유형·목적 → 검증 영역."""
    if purpose in ("agent_step", "code_agent_step", "agent_convert"):
        return "agent_step"
    if purpose == "memory_extract":
        return "json"
    return {"browser": "browser", "paper": "paper", "research": "paper", "coding": "code", "data_lab": "lab"}.get(task, "general")
