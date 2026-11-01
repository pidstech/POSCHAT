# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""모델 API 호출: POSTECH GenAI와 개인 Claude API(Anthropic)·개인 GPT API(OpenAI).

다섯 가지 방식을 지원한다.
- chat_completions(기본): POSTECH GenAI의 OpenAI 호환 Chat Completions(`.../agent/openai_compatible/a1/v1`).
  GPT·Claude·Gemini를 모델 ID로 고른다. 인증은 x-api-key 헤더(다른 OpenAI 호환 서버를 위해 Bearer도 함께 보낸다).
- responses: 게이트웨이의 OpenAI Responses API(`.../a<번호>/openai/responses`). 모델을 고를 수 있다.
  주소의 a<번호>는 POSTECH GenAI 콘솔에서 확인해 설정에 넣는다.
- a1: `agent/api/a1/gpt` 단일 호출 API. 모델은 서버가 정한다.
- anthropic(1.11): 사용자가 직접 발급한 Anthropic API 키로 Claude Messages API(api.anthropic.com)를 부른다.
  데스크톱은 공식 Anthropic Python SDK를 쓰고, SDK를 설치할 수 없는 안드로이드(Chaquopy에 pydantic-core·jiter가
  없다)는 같은 요청을 HTTP로 보낸다.
- openai(1.18): 사용자가 직접 발급한 OpenAI API 키로 OpenAI Responses API(api.openai.com/v1/responses)를 부른다.
  요청·응답 형식은 responses 방식과 같고 인증만 Bearer 토큰이다. SDK 없이 HTTP로 보낸다(안드로이드도 같다).

stream을 켜면 받은 글자를 on_delta(지금까지의 전체 텍스트)로 넘긴다. OpenAI 방식은 표준 SSE를,
a1은 문서에 형식이 없어서 SSE·JSON Lines·일반 텍스트를 모두 받아 주고, 실패하면 한 번에 받는 방식으로 다시 요청한다.
응답 헤더의 크레딧 사용량은 on_credit으로 알린다.
"""
import codecs
import json
import re
import ssl
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlsplit, urlunsplit

import requests

import certs

try:
    # genai.postech.ac.kr은 중간 인증서를 보내지 않아 certifi로는 검증에 실패한다.
    # OS 인증서 저장소(Windows는 중간 인증서를 자동으로 받아 옴)로 검증하도록 한다.
    import truststore
    truststore.inject_into_ssl()
    TRUSTSTORE = True
except ImportError:
    TRUSTSTORE = False  # 안드로이드 등: 검증 실패 때 중간 인증서를 직접 받아 온다(certs.py)

# 중간 인증서를 보내지 않는 것을 확인한 서버. 이 서버에만 AIA로 중간 인증서를 받아 온다.
AIA_HOSTS = {"genai.postech.ac.kr"}
_aia_sessions = {}  # 호스트 -> 중간 인증서를 더한 CA 묶음으로 검증하는 세션


class _StrictCAAdapter(requests.adapters.HTTPAdapter):
    """받아 온 중간 인증서를 신뢰 기준점으로 삼지 않도록 VERIFY_X509_PARTIAL_CHAIN을 끈 연결.

    Python 3.13+와 urllib3는 이 옵션을 켜므로, 그대로 두면 CA 묶음에 넣은 중간 인증서만으로 검증이
    끝나 버린다. 끄면 중간 인증서는 체인을 잇는 데만 쓰이고 certifi의 루트까지 서명이 이어져야 통과한다.
    """

    def __init__(self, ca_file):
        self._ca_file = ca_file
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        from urllib3.util.ssl_ import create_urllib3_context

        ctx = create_urllib3_context(verify_flags=0)
        ctx.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
        ctx.load_verify_locations(self._ca_file)
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)

URL = "https://genai.postech.ac.kr/agent/api/a1/gpt"

# 게이트웨이 Responses API에서 쓸 수 있는 GPT 모델(posicube-services/llm-agent-api README 기준)
MODELS = [
    ("gpt-5.1-gs-2025-11-13", "GPT-5.1 — 권장: 성능과 비용의 균형"),
    ("gpt-5.2-gs-2025-12-11", "GPT-5.2 — 가장 좋은 성능, 비용 높음"),
    ("gpt-5-gs-2025-08-07", "GPT-5"),
    ("gpt-5-mini-gs-2025-08-07", "GPT-5 mini — 빠르고 저렴"),
    ("gpt-4.1-mini-gs-2025-04-14", "GPT-4.1 mini — 추론 없음, 저렴"),
    ("gpt-6.1-sol", "GPT-6.1 Sol"),
    ("gpt-6-astra", "GPT-6 Astra"),
    ("claude-opus-5-5", "Claude Opus 5.5"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5"),
    ("gemini-3.8-flash", "Gemini 3.8 Flash"),
]
RESPONSES_MODELS = MODELS[:5]
DEFAULT_MODEL = MODELS[0][0]
MODEL_LABELS = dict(MODELS)
# 1.9 이전 목록의 잘못된 모델 ID. 게이트웨이는 Claude를 점 대신 -로 쓴다(claude-opus-5-5).
MODEL_ALIASES = {"claude-opus-5.5": "claude-opus-5-5", "claude-sonnet-5.5": "claude-sonnet-5-5"}
# 콘솔(에이전트 API)에 안내된 POSTECH GenAI의 OpenAI 호환 주소. 설정에 주소가 없으면 이 주소를 쓴다.
DEFAULT_CHAT_COMPLETIONS_URL = "https://genai.postech.ac.kr/agent/openai_compatible/a1/v1/chat/completions"
DEFAULT_MODE = "chat_completions"  # 1.9부터. a1/gpt는 2026년 10월 현재 서버 오류만 돌려준다
# 개인 Claude API(Anthropic Messages API). 키는 POSTECH 키와 따로 저장한다(config의 anthropic_api_key).
ANTHROPIC_MODE = "anthropic"
# 1.18 개인 GPT API(OpenAI). 키는 config의 openai_api_key(없으면 환경 변수 OPENAI_API_KEY).
OPENAI_MODE = "openai"
MODES = ("a1", "responses", "chat_completions", ANTHROPIC_MODE, OPENAI_MODE)
OPENAI_BASE_URL = "https://api.openai.com/v1"
# 기본 목록. '모델 목록 불러오기'로 이 키로 쓸 수 있는 모델을 OpenAI에서 받아 바꾼다.
OPENAI_MODELS = [
    ("gpt-5.1", "GPT-5.1 — 권장: 성능과 비용의 균형"),
    ("gpt-5.2", "GPT-5.2 — 가장 좋은 성능, 비용 높음"),
    ("gpt-5-mini", "GPT-5 mini — 빠르고 저렴"),
    ("gpt-4.1-mini", "GPT-4.1 mini — 추론 없음, 저렴"),
]
DEFAULT_OPENAI_MODEL = OPENAI_MODELS[0][0]
OPENAI_LABELS = dict(OPENAI_MODELS)
# 대화용이 아닌 모델(목록에서 뺀다): 음성·실시간·이미지·검색 전용·임베딩·검열·옛 완성
_OPENAI_NOT_CHAT = re.compile(r"audio|realtime|transcribe|tts|image|dall-e|embedding|moderation|search|whisper|"
                              r"instruct|davinci|babbage|codex-mini|computer-use|sora", re.I)
ANTHROPIC_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2026-10-21"  # SDK 2.x의 기본 API 버전과 같게 둔다
ANTHROPIC_MODELS = [
    ("claude-opus-5-5", "Claude Opus 5.5 — 권장"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 — 빠르고 저렴"),
    ("claude-haiku-5-5", "Claude Haiku 5.5 — 가장 빠르고 저렴"),
    ("claude-fable-5-1", "Claude Fable 5.1 — 가장 높은 성능, 비용 높음"),
]
DEFAULT_ANTHROPIC_MODEL = ANTHROPIC_MODELS[0][0]
ANTHROPIC_LABELS = dict(ANTHROPIC_MODELS)
# 안전 정책으로 답하지 않으면 서버가 Anthropic이 권하는 다른 모델로 다시 답하게 한다(fallbacks: "default").
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"
ANTHROPIC_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"}
ANTHROPIC_EFFORT = "medium"  # 5 세대 모델에만 보낸다(이전 모델 일부는 effort를 받지 않는다)
ANTHROPIC_MAX_TOKENS = 64000  # 스트리밍
ANTHROPIC_MAX_TOKENS_ONCE = 16000  # 한 번에 받기(HTTP 시간 제한 안에 끝나도록)
STT_MODEL = "gemini-3.8-flash"  # OpenAI 호환 API에서 음성(input_audio)을 받아 적을 수 있는 모델
REASONING_EFFORT = "low"  # 에이전트는 단계마다 호출하므로 추론 토큰을 아낀다


class ApiError(Exception):
    pass


# 호출이 끝날 때마다 on_usage(mode, model, usage)를 부른다. usage는 서버가 알려 준 토큰 수
# {"input_tokens", "output_tokens"} 또는 None. 앱(main.py)이 storage.record_usage로 설정한다.
on_usage = None
# 성공·실패와 관계없이 호출마다 on_trace(info, prompt, reply)를 부른다(관측: telemetry.on_llm_call).
# info: {"mode", "model", "ms", "ok", "error", "input_tokens", "output_tokens", "stream", "retries"}
on_trace = None
# 1.17: Cloud 모델 호출 직전에 부른다(kind: "chat" | "stt"). Local Only 정책이면 ApiError를 내서 막는다(main.py가 설정한다).
# 라우터를 거치지 않는 호출(PO노트·대화 요약·자동 평가·직접 고른 Cloud 모델)까지 여기서 한 번 더 막는다.
cloud_guard = None


def _guard(kind):
    if cloud_guard:
        cloud_guard(kind)


@dataclass
class ApiSettings:
    mode: str = "a1"               # "a1" | "responses" | "chat_completions" | "anthropic" | "openai"(설정의 기본값은 DEFAULT_MODE)
    responses_url: str = ""
    chat_completions_url: str = ""
    model: str = DEFAULT_MODEL
    stream: bool = True

    @classmethod
    def from_config(cls, config):
        mode = config.get("api_mode", DEFAULT_MODE)
        mode = mode if mode in MODES else DEFAULT_MODE
        return cls(
            mode=mode,
            responses_url=endpoint_url(config.get("responses_url"), RESPONSES_PATH),
            chat_completions_url=endpoint_url(config.get("chat_completions_url"), CHAT_COMPLETIONS_PATH)
            or DEFAULT_CHAT_COMPLETIONS_URL,
            model=(config.get("anthropic_model") or DEFAULT_ANTHROPIC_MODEL) if mode == ANTHROPIC_MODE
            else (config.get("openai_model") or DEFAULT_OPENAI_MODEL) if mode == OPENAI_MODE
            else normalize_model(config.get("model") or DEFAULT_MODEL),
            stream=bool(config.get("stream", True)),
        )


def model_config_key(mode):
    """mode의 기본 모델을 저장하는 설정 이름. POSTECH 방식과 개인 Claude·GPT API는 모델 목록이 달라 따로 둔다."""
    return {ANTHROPIC_MODE: "anthropic_model", OPENAI_MODE: "openai_model"}.get(mode, "model")


def default_model(mode):
    """mode의 기본 모델 ID."""
    return {ANTHROPIC_MODE: DEFAULT_ANTHROPIC_MODEL, OPENAI_MODE: DEFAULT_OPENAI_MODEL}.get(mode, DEFAULT_MODEL)


RESPONSES_PATH = "/responses"
CHAT_COMPLETIONS_PATH = "/chat/completions"


def normalize_model(model_id):
    model_id = str(model_id or "")
    return MODEL_ALIASES.get(model_id, model_id)


def _auth_headers(api_key, **extra):
    """OpenAI 호환 API 인증. POSTECH 게이트웨이는 x-api-key를, 다른 OpenAI 호환 서버는 Bearer 토큰을 본다."""
    return {"x-api-key": api_key, "Authorization": f"Bearer {api_key}", **extra}


def endpoint_url(value, path):
    """설정에 넣은 주소를 호출할 주소로 맞춘다.

    OpenAI 호환 도구처럼 기본 주소(`.../v1`, `.../openai`)만 넣어도 path(/responses, /chat/completions)를
    붙여 준다. 끝의 /와 실수로 넣은 /models도 정리한다. `?api-version=...` 같은 쿼리는 경로 뒤에 그대로 둔다.
    """
    url = str(value or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    base = parts.path.rstrip("/")
    if base.endswith("/models"):
        base = base[: -len("/models")]
    if not base.endswith(path):
        base += path
    return urlunsplit(parts._replace(path=base))


def _sibling_url(chat_completions_url, path):
    """Chat Completions 주소와 같은 기본 주소 아래의 다른 API 주소(.../models, .../audio/transcriptions)."""
    url = endpoint_url(chat_completions_url, CHAT_COMPLETIONS_PATH)
    if not url:
        return ""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=parts.path[: -len(CHAT_COMPLETIONS_PATH)] + path))


def models_url(chat_completions_url):
    """Chat Completions 주소와 같은 기본 주소의 모델 목록(GET .../models) 주소."""
    return _sibling_url(chat_completions_url, "/models")


def list_models(api_key, chat_completions_url, timeout=20):
    """OpenAI 호환 API가 알려 주는 모델 ID 목록. 서버가 정한 순서를 지킨다."""
    url = models_url(chat_completions_url)
    if not url:
        raise ApiError("Chat Completions 주소를 먼저 입력하세요.")
    try:
        response = _request("GET", url, _auth_headers(api_key, Accept="application/json"), None, timeout, stream=False)
    except ApiError as e:
        if "API 오류 404" in str(e):
            raise ApiError("이 서버는 모델 목록(GET .../models)을 알려 주지 않습니다. 기본 목록을 그대로 쓰세요.") from e
        raise
    try:
        data = response.json()
    except ValueError as e:
        raise ApiError(f"모델 목록 형식 오류: {response.text[:300]}") from e
    items = data.get("data") if isinstance(data, dict) else data
    if isinstance(items, dict):  # 게이트웨이 공통 형식 {"code", "message", "data": {"data": [...]}}
        items = items.get("data")
    if not isinstance(items, list):
        raise ApiError(f"모델 목록 형식 오류: {response.text[:300]}")
    ids = []
    for item in items:
        model_id = item.get("id") if isinstance(item, dict) else item
        if isinstance(model_id, str) and model_id.strip() and model_id.strip() not in ids:
            ids.append(model_id.strip())
    if not ids:
        raise ApiError("서버가 사용할 수 있는 모델을 알려 주지 않았습니다.")
    return ids


def model_label(model_id):
    return MODEL_LABELS.get(model_id) or ANTHROPIC_LABELS.get(model_id) or OPENAI_LABELS.get(model_id, model_id)


def transcribe(api_key, chat_completions_url, wav_b64, language=None, context="", model=STT_MODEL, timeout=120):
    """OpenAI 호환 Chat Completions에 음성(input_audio)을 보내 받아 적게 한다.

    POSTECH 게이트웨이에는 /audio/transcriptions가 없지만 Gemini는 Chat Completions로 음성을 받는다.
    """
    _guard("stt")
    lang = {"ko": "한국어", "en": "영어"}.get(language, "들리는 언어")
    instruction = (f"이 강의 음성을 {lang} 그대로 받아 적으세요. 받아 적은 글만 출력하고, 요약·설명·따옴표를 붙이지 마세요. "
                   "말이 없거나 알아들을 수 없으면 아무것도 출력하지 마세요.")
    if context:
        instruction += f"\n\n참고(앞부분 전사·강의 자료 용어, 받아 적지 말 것):\n{context[-600:]}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": instruction},
            {"type": "input_audio", "input_audio": {"data": wav_b64, "format": "wav"}},
        ]}],
        "reasoning_effort": "none",
    }
    url = endpoint_url(chat_completions_url, CHAT_COMPLETIONS_PATH) or DEFAULT_CHAT_COMPLETIONS_URL
    response = _post(url, _auth_headers(api_key, **{"Content-Type": "application/json"}), payload, timeout, stream=False)
    try:
        data = response.json()
        text = data["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ApiError(f"음성 인식 응답 형식 오류: {response.text[:300]}") from e
    if on_usage:
        try:
            on_usage("stt", model, _usage(data))
        except Exception:
            pass
    return text.strip()


_NUMBERED_RE = re.compile(r"^\s*\[?(\d+)\]?\s*[|:.)\]]\s?(.*)$")


def refine_transcript(api_key, chat_completions_url, wav_b64, drafts, language=None, context="", model=STT_MODEL,
                      timeout=180):
    """로컬 음성 인식 초안 drafts(구간 글 목록)를 음성과 대조해 고친다.

    음성은 drafts의 구간을 차례로 이어 붙인 것이다. 고친 글 목록(drafts와 같은 길이)을 돌려주고,
    모델이 번호를 맞춰 답하지 않으면 번호 없이 이어 쓴 글(str)을 돌려준다.
    """
    _guard("stt")
    lang = {"ko": "한국어", "en": "영어"}.get(language, "들리는 언어")
    lines = "\n".join(f"{i}| {t}" for i, t in enumerate(drafts, 1))
    instruction = (f"이 강의 음성은 아래 {len(drafts)}개 구간을 차례로 이어 붙인 것입니다. 각 줄은 로컬 음성 인식기가 받아 적은 초안이라 "
                   f"틀린 글자가 있을 수 있습니다. 음성을 듣고 구간마다 {lang} 그대로 고쳐 `번호| 고친 글` 형식으로 "
                   f"1번부터 {len(drafts)}번까지 한 줄씩 출력하세요. 맞는 초안은 그대로 두고, 말이 없는 구간은 `번호|`만 쓰세요. "
                   "다른 설명은 쓰지 마세요.")
    if context:
        instruction += f"\n\n참고(강의 자료 용어·앞부분, 받아 적지 말 것):\n{context[-600:]}"
    instruction += f"\n\n[초안]\n{lines}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": instruction},
            {"type": "input_audio", "input_audio": {"data": wav_b64, "format": "wav"}},
        ]}],
        "reasoning_effort": "none",
    }
    url = endpoint_url(chat_completions_url, CHAT_COMPLETIONS_PATH) or DEFAULT_CHAT_COMPLETIONS_URL
    response = _post(url, _auth_headers(api_key, **{"Content-Type": "application/json"}), payload, timeout, stream=False)
    try:
        data = response.json()
        text = data["choices"][0]["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ApiError(f"음성 인식 응답 형식 오류: {response.text[:300]}") from e
    if on_usage:
        try:
            on_usage("stt", model, _usage(data))
        except Exception:
            pass
    return parse_numbered(text, len(drafts))


def parse_numbered(text, count):
    """`번호| 글` 줄들을 count개 목록으로. 번호가 다 맞지 않으면 번호를 뗀 글 전체(str)."""
    found, loose = {}, []
    for line in (text or "").strip().splitlines():
        match = _NUMBERED_RE.match(line)
        if match and 1 <= int(match.group(1)) <= count:
            found[int(match.group(1))] = match.group(2).strip()
        elif line.strip():
            loose.append(line.strip())
    if len(found) == count:
        return [found[i] for i in range(1, count + 1)]
    return " ".join([found[i] for i in sorted(found)] + loose).strip()


# ---- 크레딧 ----
# POSTECH 게이트웨이는 모든 응답 헤더에 이번 주기(WEEKLY 등)의 크레딧 사용량과 한도를 담아 준다.
# 크레딧 정보가 담긴 응답을 받을 때마다 on_credit({"usage", "limit", "interval"})을 부른다.
on_credit = None


def _credit(headers):
    def num(name):
        try:
            return float(headers.get(name))
        except (TypeError, ValueError):
            return None
    usage, limit = num("x-role-ratelimit-credit-usage"), num("x-role-ratelimit-credit-limit")
    if usage is None and limit is None:
        return None
    return {"usage": usage, "limit": limit, "interval": (headers.get("x-role-ratelimit-credit-limit-interval") or "").strip()}


def credit(api_key, chat_completions_url=None, timeout=15):
    """크레딧 사용량만 확인한다. GET .../models는 POSTECH에서 404지만 크레딧 헤더가 붙고 크레딧을 쓰지 않는다."""
    url = models_url(chat_completions_url or DEFAULT_CHAT_COMPLETIONS_URL)
    response = _send("GET", url, _auth_headers(api_key, Accept="application/json"), timeout=timeout, stream=False)
    if response.status_code in (401, 403):
        raise ApiError(f"API 키를 확인하세요 (HTTP {response.status_code}).")
    info = _credit(response.headers)
    if info is None:
        raise ApiError("이 서버는 크레딧 정보를 알려 주지 않습니다.")
    return info


def _notify_credit(info):
    if info and on_credit:
        try:
            on_credit(info)
        except Exception:
            pass


def ask(api_key, message, timeout=180, settings=None, on_delta=None, cancelled=None, images=None, cache_prefix=0,
        usage_out=None):
    """모델 답변 전체를 돌려준다. on_delta가 있고 스트리밍이 켜져 있으면 받는 동안 중간 텍스트를 넘긴다.

    images는 [(MIME 형식, base64)]이며 Responses/호환 API에서 보낸다(a1은 글자만 받는다).
    1.17: cache_prefix(글자 수)를 주면 message의 앞부분 그만큼을 프롬프트 캐시 대상으로 표시한다(Claude API의 cache_control).
    OpenAI 호환 서버는 표시 방법이 없어 그대로 보낸다(앞부분이 같으면 서버가 스스로 캐시할 수 있다).
    usage_out(dict)을 주면 서버가 알려 준 토큰 사용량(input_tokens, output_tokens, cache_read_input_tokens,
    cache_creation_input_tokens)을 채운다. 알려 주지 않으면 비워 둔다.
    """
    _guard("chat")
    settings = settings or ApiSettings()
    stream = bool(on_delta) and settings.stream
    started, retries = time.monotonic(), [0]
    try:
        text, usage = _ask_any(api_key, message, timeout, settings, on_delta, cancelled, images, stream, retries, cache_prefix)
    except ApiError as e:
        _trace(settings, started, stream, retries[0], None, error=_error_class(e), prompt=message)
        raise
    _trace(settings, started, stream, retries[0], usage, prompt=message, reply=text)
    if usage_out is not None and usage:
        usage_out.update(usage)
    if on_usage:
        try:
            on_usage(settings.mode, settings.model if settings.mode != "a1" else "a1", usage)
        except Exception:
            pass  # 사용량 기록 실패로 답변을 잃지 않는다
    return text


def _error_class(error):
    """관측용 오류 분류(오류 문구 자체는 남기지 않는다)."""
    text = str(error)
    for code in ("401", "403", "404", "429", "500", "502", "503", "504"):
        if code in text:
            return f"http_{code}"
    if "시간" in text or "timeout" in text.lower():
        return "timeout"
    if "연결" in text or "connect" in text.lower():
        return "connection"
    return "api_error"


def _trace(settings, started, stream, retries, usage, error="", prompt=None, reply=None):
    if not on_trace:
        return
    info = {"mode": settings.mode, "model": settings.model if settings.mode != "a1" else "a1",
            "ms": int((time.monotonic() - started) * 1000), "ok": not error, "error": error,
            "input_tokens": (usage or {}).get("input_tokens"), "output_tokens": (usage or {}).get("output_tokens"),
            "stream": stream, "retries": retries}
    try:
        on_trace(info, prompt, reply)
    except Exception:
        pass  # 관측 기록 실패로 답변을 잃지 않는다


def _ask_any(api_key, message, timeout, settings, on_delta, cancelled, images, stream, retries, cache_prefix=0):
    if settings.mode == "responses":
        text, usage = _ask_responses(api_key, message, timeout, settings, on_delta if stream else None, cancelled,
                                     images)
    elif settings.mode == ANTHROPIC_MODE:
        text, usage = _ask_anthropic(api_key, message, timeout, settings, on_delta if stream else None, cancelled,
                                     images, cache_prefix)
    elif settings.mode == OPENAI_MODE:
        text, usage = _ask_openai(api_key, message, timeout, settings, on_delta if stream else None, cancelled, images)
    elif settings.mode == "chat_completions":
        text, usage = _ask_chat_completions(api_key, message, timeout, settings,
                                            on_delta if stream else None, cancelled, images)
    else:
        text, usage = None, None
        if stream:
            try:
                text, usage = _ask_a1(api_key, message, timeout, on_delta, cancelled)
            except _StreamFormatError:
                retries[0] += 1  # 서버가 알 수 없는 형식으로 보냈다: 한 번에 받는 방식으로 다시 요청한다
        if text is None:
            text, usage = _ask_a1(api_key, message, timeout, None, cancelled)
    return text, usage


def _ask_chat_completions(api_key, message, timeout, settings, on_delta, cancelled, images=None):
    if not settings.chat_completions_url:
        raise ApiError("OpenAI 호환 API를 쓰려면 설정에서 Chat Completions 주소를 입력하세요.")
    content = message
    if images:
        content = [{"type": "text", "text": message}] + [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}
            for mime, data in images
        ]
    payload = {
        "model": settings.model,
        "messages": [{"role": "user", "content": content}],
        "stream": bool(on_delta),
    }
    headers = _auth_headers(api_key, **{"Content-Type": "application/json"})
    response = _post(settings.chat_completions_url, headers, payload, timeout, stream=bool(on_delta))
    if on_delta and not _is_json(response):
        try:
            return _read_stream(response, on_delta, cancelled)
        except _StreamFormatError as e:
            raise ApiError(f"스트리밍 응답을 해석하지 못했습니다: {e}") from e
    try:
        data = response.json()
        choice = data["choices"][0]
        text = choice["message"]["content"]
        if isinstance(text, list):
            text = "".join(part.get("text", "") for part in text if isinstance(part, dict))
        if not isinstance(text, str):
            raise TypeError("응답 내용이 문자열이 아닙니다.")
        return text, _usage(data)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise ApiError(f"응답 형식 오류: {response.text[:300]}") from e


def _usage(data):
    """응답(또는 게이트웨이가 감싼 응답)의 토큰 사용량. 없으면 None."""
    if not isinstance(data, dict):
        return None
    for obj in (data.get("usage"), (data.get("response") or {}).get("usage") if isinstance(data.get("response"), dict) else None,
                (data.get("data") or {}).get("usage") if isinstance(data.get("data"), dict) else None):
        if isinstance(obj, dict):
            inp = obj.get("input_tokens", obj.get("prompt_tokens"))
            out = obj.get("output_tokens", obj.get("completion_tokens"))
            if isinstance(inp, int) or isinstance(out, int):
                usage = {"input_tokens": int(inp or 0), "output_tokens": int(out or 0)}
                # 1.17: 서버가 알려 준 캐시 적중 토큰(OpenAI: prompt_tokens_details.cached_tokens, Responses: input_tokens_details)
                details = obj.get("prompt_tokens_details") or obj.get("input_tokens_details") or {}
                cached = details.get("cached_tokens") if isinstance(details, dict) else None
                if isinstance(cached, int) and cached:
                    usage["cache_read_input_tokens"] = cached
                return usage
    return None


# ---- a1 단일 호출 ----

def _ask_a1(api_key, message, timeout, on_delta, cancelled):
    headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}
    data = {"message": message, "stream": bool(on_delta)}
    response = _post(URL, headers, data, timeout, stream=bool(on_delta))
    if not on_delta or _is_json(response):
        try:
            data = response.json()
            text, usage = data["message"], _usage(data)
        except (ValueError, KeyError, TypeError) as e:
            raise ApiError(f"응답 형식 오류: {response.text[:300]}") from e
    else:
        text, usage = _read_stream(response, on_delta, cancelled)
    _check_a1_error(text)
    return text, usage


# 서버가 답변 대신 보내는 오류 표시. 2026년 10월 기준 a1/gpt는 모든 요청에 이것만 돌려준다(코드 10000).
_A1_ERROR_RE = re.compile(r'^\s*<div\s+cls="error"\s+attr="(\d+)"\s*>\s*</div>\s*$')


def _check_a1_error(text):
    match = _A1_ERROR_RE.match(text or "")
    if match:
        raise ApiError(f"기본(a1/gpt) 서버가 답변 대신 오류 {match.group(1)}을(를) 돌려줬습니다. "
                       "설정 → API 방식에서 'OpenAI 호환 API'를 고르세요(주소는 비워 두면 POSTECH 주소를 씁니다).")


# ---- 개인 Claude API(Anthropic Messages API) ----

_SDK_MISSING = object()
_sdk_module = None


def _anthropic_sdk():
    """공식 Anthropic SDK. 설치되어 있지 않으면(안드로이드) None. 시작이 느려지지 않게 처음 쓸 때 불러온다."""
    global _sdk_module
    if _sdk_module is None:
        try:
            import anthropic
            _sdk_module = anthropic
        except ImportError:
            _sdk_module = _SDK_MISSING
    return None if _sdk_module is _SDK_MISSING else _sdk_module


def _anthropic_effort_ok(model):
    return bool(re.match(r"claude-(opus|sonnet|haiku|fable|mythos)-5", model or ""))


def _anthropic_params(settings, message, images, stream, cache_prefix=0):
    """(Messages API 요청 본문, beta 이름 목록). cache_prefix>0이면 앞부분을 따로 나눈 글 블록에 cache_control을 단다(1.17)."""
    content = message
    cut = int(cache_prefix or 0)
    if 0 < cut < len(message):
        text_blocks = [{"type": "text", "text": message[:cut], "cache_control": {"type": "ephemeral"}},
                       {"type": "text", "text": message[cut:]}]
    elif cut >= len(message) > 0:
        text_blocks = [{"type": "text", "text": message, "cache_control": {"type": "ephemeral"}}]
    else:
        text_blocks = None
    if images or text_blocks:
        content = [{"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
                   for mime, data in images or []] + (text_blocks or [{"type": "text", "text": message}])
    params = {"model": settings.model, "max_tokens": ANTHROPIC_MAX_TOKENS if stream else ANTHROPIC_MAX_TOKENS_ONCE,
              "messages": [{"role": "user", "content": content}]}
    if _anthropic_effort_ok(settings.model):
        params["output_config"] = {"effort": ANTHROPIC_EFFORT}
    if settings.model in ANTHROPIC_FALLBACK_MODELS:
        params["fallbacks"] = "default"
        return params, [ANTHROPIC_FALLBACK_BETA]
    return params, []


def _anthropic_headers(api_key, betas=(), **extra):
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION, **extra}
    if betas:
        headers["anthropic-beta"] = ",".join(betas)
    return headers


def _anthropic_status_error(status, detail=""):
    if status == 401:
        return ApiError("Anthropic API 키를 확인하세요 (HTTP 401).")
    if status == 403:
        return ApiError(f"이 Anthropic API 키로는 이 요청을 할 수 없습니다 (HTTP 403). {detail}".strip())
    if status == 429:
        return ApiError("Anthropic API 요청 한도를 넘었습니다. 잠시 뒤 다시 시도하세요 (HTTP 429).")
    return ApiError(f"API 오류 {status}: {detail}"[:400])


def _anthropic_answer(blocks, stop_reason, stop_details=None):
    """응답 블록에서 답변 글을 꺼낸다. 안전 정책으로 답하지 않았으면(대체 모델도 거절) 오류로 알린다.

    서버가 대체 모델로 다시 답하면 앞 모델이 쓴 부분과 이어 쓴 부분이 모두 text 블록이므로 그대로 잇는다.
    """
    if stop_reason == "refusal":
        category = (stop_details or {}).get("category") if isinstance(stop_details, dict) else getattr(
            stop_details, "category", None)
        raise ApiError("Claude가 안전 정책에 따라 이 요청에 답하지 않았습니다"
                       + (f"(분류: {category})" if category else "") + ". 질문을 바꿔 다시 시도하세요.")
    return "".join(b.get("text", "") if isinstance(b, dict) else getattr(b, "text", "")
                   for b in blocks or () if (b.get("type") if isinstance(b, dict) else getattr(b, "type", "")) == "text")


def _anthropic_usage(usage):
    """input_tokens는 예전처럼 캐시 쓰기·읽기를 더한 전체 입력이다. 1.17부터 캐시 몫을 따로도 남긴다(비용 계산용)."""
    if usage is None:
        return None
    get = usage.get if isinstance(usage, dict) else (lambda name: getattr(usage, name, None))
    inp = sum(int(get(name) or 0) for name in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    out = {"input_tokens": inp, "output_tokens": int(get("output_tokens") or 0)}
    for name in ("cache_read_input_tokens", "cache_creation_input_tokens"):
        if int(get(name) or 0):
            out[name] = int(get(name) or 0)
    return out


def _ask_anthropic(api_key, message, timeout, settings, on_delta, cancelled, images=None, cache_prefix=0):
    params, betas = _anthropic_params(settings, message, images, bool(on_delta), cache_prefix)
    sdk = _anthropic_sdk()
    if sdk is not None:
        return _ask_anthropic_sdk(sdk, api_key, params, betas, timeout, on_delta, cancelled)
    return _ask_anthropic_http(api_key, params, betas, timeout, on_delta, cancelled)


def _ask_anthropic_sdk(sdk, api_key, params, betas, timeout, on_delta, cancelled):
    client = sdk.Anthropic(api_key=api_key, base_url=ANTHROPIC_BASE_URL, timeout=sdk.Timeout(timeout, connect=15.0),
                           max_retries=2)
    messages, extra = (client.beta.messages, {"betas": betas}) if betas else (client.messages, {})
    try:
        if on_delta:
            text = ""
            with messages.stream(**params, **extra) as stream:
                for piece in stream.text_stream:
                    if cancelled and cancelled():
                        return text, None
                    text += piece
                    on_delta(text)
                final = stream.get_final_message()
        else:
            final = messages.create(**params, **extra)
    except sdk.APIStatusError as e:
        raise _anthropic_status_error(e.status_code, getattr(e, "message", "") or str(e)) from e
    except sdk.APITimeoutError as e:
        raise ApiError("Anthropic API 응답 시간이 초과되었습니다(timeout). 다시 시도하세요.") from e
    except sdk.APIConnectionError as e:
        raise ApiError(f"네트워크 오류(Anthropic API 연결): {e}") from e
    except sdk.AnthropicError as e:  # 스트림 도중 서버가 보낸 오류 이벤트 등
        raise ApiError(f"Anthropic API 오류: {e}"[:400]) from e
    return _anthropic_answer(final.content, final.stop_reason, getattr(final, "stop_details", None)), \
        _anthropic_usage(final.usage)


def _ask_anthropic_http(api_key, params, betas, timeout, on_delta, cancelled):
    """SDK가 없는 곳(안드로이드)에서 같은 요청을 보낸다."""
    body = dict(params, stream=bool(on_delta))
    headers = _anthropic_headers(api_key, betas, **{"Content-Type": "application/json"})
    response = _send("POST", f"{ANTHROPIC_BASE_URL}/v1/messages", headers, body, timeout, stream=bool(on_delta))
    if response.status_code != 200:
        try:
            detail = (response.json().get("error") or {}).get("message", "")
        except (ValueError, AttributeError):
            detail = response.text[:300]
        response.close()
        raise _anthropic_status_error(response.status_code, detail)
    if not on_delta:
        try:
            data = response.json()
        except ValueError as e:
            raise ApiError(f"응답 형식 오류: {response.text[:300]}") from e
        return _anthropic_answer(data.get("content"), data.get("stop_reason"), data.get("stop_details")), \
            _anthropic_usage(data.get("usage"))
    return _read_anthropic_stream(response, on_delta, cancelled)


def _read_anthropic_stream(response, on_delta, cancelled):
    text, usage, stop_reason, stop_details = "", {}, None, None
    try:
        for event, data in _events(response):
            if cancelled and cancelled():
                return text, None
            try:
                obj = json.loads(data)
            except (TypeError, ValueError):
                continue
            kind = obj.get("type") or event
            if kind == "message_start":
                usage.update((obj.get("message") or {}).get("usage") or {})
            elif kind == "content_block_delta":
                delta = obj.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text += delta.get("text", "")
                    on_delta(text)
            elif kind == "message_delta":
                stop_reason = (obj.get("delta") or {}).get("stop_reason") or stop_reason
                stop_details = (obj.get("delta") or {}).get("stop_details") or stop_details
                usage.update({k: v for k, v in (obj.get("usage") or {}).items() if v is not None})
            elif kind == "error":
                err = obj.get("error") or {}
                raise ApiError(f"Anthropic API 오류: {err.get('type', '')} {err.get('message', '')}".strip()[:400])
            elif kind == "message_stop":
                break
    except requests.RequestException as e:
        raise ApiError(f"네트워크 오류(스트리밍 중): {e}") from e
    finally:
        response.close()
    _anthropic_answer([], stop_reason, stop_details)  # 거절이면 오류로 알린다(받은 일부는 버린다)
    return text, _anthropic_usage(usage) if usage else None


def list_anthropic_models(api_key, timeout=20):
    """이 Anthropic API 키로 쓸 수 있는 모델 ID 목록(서버가 정한 순서, 최신 모델이 먼저)."""
    sdk = _anthropic_sdk()
    ids = []
    if sdk is not None:
        client = sdk.Anthropic(api_key=api_key, base_url=ANTHROPIC_BASE_URL,
                               timeout=sdk.Timeout(timeout, connect=15.0), max_retries=1)
        try:
            ids = [m.id for m in client.models.list(limit=100)]
        except sdk.APIStatusError as e:
            raise _anthropic_status_error(e.status_code, getattr(e, "message", "")) from e
        except sdk.APIConnectionError as e:
            raise ApiError(f"네트워크 오류(Anthropic API 연결): {e}") from e
    else:
        models_url_ = f"{ANTHROPIC_BASE_URL}/v1/models"
        url = models_url_ + "?limit=100"
        while url:
            response = _send("GET", url, _anthropic_headers(api_key, Accept="application/json"), timeout=timeout)
            if response.status_code != 200:
                raise _anthropic_status_error(response.status_code, response.text[:300])
            try:
                data = response.json()
            except ValueError as e:
                raise ApiError(f"모델 목록 형식 오류: {response.text[:300]}") from e
            ids += [m.get("id") for m in data.get("data") or [] if isinstance(m, dict)]
            url = f"{models_url_}?limit=100&after_id={data['last_id']}" if data.get("has_more") and \
                data.get("last_id") else ""
    ids = [m for i, m in enumerate(ids) if isinstance(m, str) and m and m not in ids[:i]]
    if not ids:
        raise ApiError("Anthropic API가 사용할 수 있는 모델을 알려 주지 않았습니다.")
    return ids


# ---- OpenAI Responses ----

def _responses_payload(model, message, images, stream):
    content = message
    if images:
        content = [{"role": "user", "content": [{"type": "input_text", "text": message}] + [
            {"type": "input_image", "image_url": f"data:{mime};base64,{data}"} for mime, data in images]}]
    payload = {"model": model, "input": content, "stream": bool(stream), "store": False}
    if _reasoning_model(model):
        payload["reasoning"] = {"effort": REASONING_EFFORT}
    return payload


def _reasoning_model(model):
    """추론(reasoning.effort)을 받는 모델: GPT-5 계열·o 계열. GPT-4 계열과 '...-chat-...'(채팅 전용)은 받지 않는다."""
    m = str(model or "").lower()
    return not m.startswith(("gpt-4", "chatgpt")) and "-chat" not in m


def _ask_responses(api_key, message, timeout, settings, on_delta, cancelled, images=None):
    if not settings.responses_url:
        raise ApiError("모델 선택(Responses API)을 쓰려면 설정에서 Responses API 주소를 입력하세요.")
    payload = _responses_payload(settings.model, message, images, on_delta)
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    response = _post(settings.responses_url, headers, payload, timeout, stream=bool(on_delta))
    return _responses_result(response, on_delta, cancelled)


def _responses_result(response, on_delta, cancelled):
    if on_delta and not _is_json(response):
        try:
            return _read_stream(response, on_delta, cancelled)
        except _StreamFormatError as e:
            raise ApiError(f"스트리밍 응답을 해석하지 못했습니다: {e}") from e
    try:
        data = response.json()
    except ValueError as e:
        raise ApiError(f"응답 형식 오류: {response.text[:300]}") from e
    text = _response_text(data)
    if text is None:
        raise ApiError(f"응답 형식 오류: {response.text[:300]}")
    return text, _usage(data)


def _response_text(data):
    """Responses API 응답(또는 게이트웨이가 감싼 응답)에서 답변 텍스트를 꺼낸다."""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("data"), dict):  # 게이트웨이 공통 형식 {"code", "message", "data"}
        inner = _response_text(data["data"])
        if inner is not None:
            return inner
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    if isinstance(data.get("output"), list):
        parts = [c.get("text", "") for item in data["output"] if isinstance(item, dict) and item.get("type") == "message"
                 for c in item.get("content") or [] if isinstance(c, dict) and c.get("type") == "output_text"]
        return "".join(parts)
    if isinstance(data.get("message"), str):
        return data["message"]
    return None


# ---- 개인 GPT API(OpenAI, 1.18) ----

def _openai_headers(api_key, **extra):
    return {"Authorization": f"Bearer {api_key}", **extra}


def _openai_status_error(status, detail=""):
    """OpenAI API 오류를 사용자가 알아들을 말로. detail은 서버가 준 오류 JSON의 앞부분."""
    message = ""
    try:
        message = (json.loads(detail).get("error") or {}).get("message") or ""
    except (ValueError, AttributeError):
        message = detail
    message = str(message)[:300]
    if status == 401:
        return ApiError("OpenAI API 키가 올바르지 않습니다(401). 설정 → API 방식 '일반 AI 모델 (GPT)'에서 키를 확인하세요.")
    if status == 403:
        return ApiError(f"이 OpenAI 키로는 이 모델이나 기능을 쓸 수 없습니다(403): {message}")
    if status == 404:
        return ApiError(f"OpenAI에 없는 모델이거나 이 키로 쓸 수 없는 모델입니다(404). 설정에서 '모델 목록 불러오기'로 확인하세요: {message}")
    if status == 429:
        return ApiError(f"OpenAI 사용 한도에 걸렸거나 잔액이 부족합니다(429). 잠시 뒤 다시 하거나 OpenAI 결제 설정을 확인하세요: {message}")
    return ApiError(f"OpenAI API 오류 {status}: {message}")


def _ask_openai(api_key, message, timeout, settings, on_delta, cancelled, images=None):
    if not api_key:
        raise ApiError("OpenAI API 키가 없습니다. 설정 → API 방식 '일반 AI 모델 (GPT)'에서 키를 입력하세요.")
    url = f"{OPENAI_BASE_URL}/responses"
    headers = _openai_headers(api_key, **{"Content-Type": "application/json"})
    payload = _responses_payload(settings.model, message, images, on_delta)
    response = _send("POST", url, headers, payload, timeout, stream=bool(on_delta))
    if response.status_code == 400 and "reasoning" in payload and "reasoning" in response.text[:2000]:
        payload.pop("reasoning")   # 추론 설정을 받지 않는 모델: 빼고 한 번 더
        response = _send("POST", url, headers, payload, timeout, stream=bool(on_delta))
    if response.status_code != 200:
        detail = response.text[:2000]
        response.close()
        raise _openai_status_error(response.status_code, detail)
    return _responses_result(response, on_delta, cancelled)


def list_openai_models(api_key, timeout=20):
    """이 OpenAI API 키로 쓸 수 있는 대화용 모델 ID(최근에 나온 것 먼저). 음성·이미지·임베딩 전용 모델은 뺀다."""
    response = _send("GET", f"{OPENAI_BASE_URL}/models", _openai_headers(api_key, Accept="application/json"), timeout=timeout)
    if response.status_code != 200:
        raise _openai_status_error(response.status_code, response.text[:2000])
    try:
        items = response.json().get("data") or []
    except (ValueError, AttributeError) as e:
        raise ApiError(f"모델 목록 형식 오류: {response.text[:300]}") from e
    rows = []
    for m in items:
        mid = m.get("id") if isinstance(m, dict) else None
        if not isinstance(mid, str) or not re.match(r"(gpt-|chatgpt-|o\d)", mid) or _OPENAI_NOT_CHAT.search(mid):
            continue
        rows.append((-(m.get("created") or 0), mid))
    ids = []
    for _, mid in sorted(rows):
        if mid not in ids:
            ids.append(mid)
    if not ids:
        raise ApiError("OpenAI API가 이 키로 쓸 수 있는 대화 모델을 알려 주지 않았습니다.")
    return ids


# ---- 공통 ----

class _StreamFormatError(Exception):
    pass


RAW = object()  # _events가 SSE도 JSON도 아닌 텍스트 조각에 붙이는 표시


def _post(url, headers, data, timeout, stream):
    return _request("POST", url, headers, data, timeout, stream)


def _request(method, url, headers, data, timeout, stream, form=None, files=None):
    response = _send(method, url, headers, data, timeout, stream, form, files)
    if response.status_code != 200:
        raise ApiError(f"API 오류 {response.status_code}: {response.text[:300]}")
    return response


def _send(method, url, headers, data=None, timeout=60, stream=False, form=None, files=None):
    """요청을 보내고 응답을 그대로 돌려준다(상태 코드는 보지 않는다). 크레딧 헤더가 있으면 on_credit으로 알린다."""
    host = urlparse(url).hostname
    kwargs = dict(headers=headers, timeout=(15, timeout), stream=stream)
    if data is not None:
        kwargs["json"] = data
    if form is not None:
        kwargs["data"] = form
    if files is not None:
        kwargs["files"] = files
    try:
        if host in _aia_sessions:
            response = _aia_sessions[host].request(method, url, **kwargs)
        else:
            try:
                response = requests.request(method, url, **kwargs)
            except requests.exceptions.SSLError:
                if TRUSTSTORE or host not in AIA_HOSTS:
                    raise
                session = requests.Session()
                session.mount(f"https://{host}", _StrictCAAdapter(_aia_bundle(url, host)))
                response = session.request(method, url, **kwargs)
                _aia_sessions[host] = session
    except requests.RequestException as e:
        raise ApiError(f"네트워크 오류: {e}") from e
    _notify_credit(_credit(response.headers))
    return response


def _aia_bundle(url, host):
    import certifi

    out = Path(tempfile.gettempdir()) / f"postech-chat-ca-{host}.pem"
    try:
        return certs.build_bundle(url, certifi.where(), out, lambda u: requests.get(u, timeout=15).content)
    except (certs.CertError, OSError, requests.RequestException) as e:
        raise ApiError(f"서버 인증서를 검증하지 못했습니다(중간 인증서 받기 실패): {e}") from e


def _is_json(response):
    return "application/json" in response.headers.get("Content-Type", "").lower()


def _events(response):
    """SSE면 (event, data)를, JSON Lines면 (None, 줄)을, 그 밖의 텍스트면 (RAW, 받은 글자)를 차례로 내놓는다."""
    ctype = response.headers.get("Content-Type", "").lower()
    if "text/event-stream" not in ctype and "json" not in ctype:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")  # 조각 경계에서 한글이 잘려도 이어 붙인다
        for raw in response.iter_content(chunk_size=None):
            text = decoder.decode(raw)
            if text:
                yield RAW, text
        return
    sse = "text/event-stream" in ctype
    event, data = None, []
    for raw in response.iter_lines():
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        if not sse:
            if line.strip():
                yield None, line
            continue
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = None, []
        elif line.startswith(":"):
            continue  # 주석(연결 유지용)
        else:
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event = value
            elif field == "data":
                data.append(value)
    if data:
        yield event, "\n".join(data)


def _read_stream(response, on_delta, cancelled):
    """(답변 텍스트, 토큰 사용량 또는 None)."""
    text, final, usage = "", None, None
    saw_delta = False
    try:
        for event, data in _events(response):
            if cancelled and cancelled():
                break
            kind, value = _chunk(event, data)
            if kind == "done":
                break
            if kind == "delta":
                text += value
                saw_delta = True
            elif kind == "chunk":
                # 형식이 문서에 없는 a1 스트림: 지금까지의 전체 텍스트를 다시 보내는 방식이면 바꾸고, 조각이면 잇는다.
                text = value if text and value.startswith(text) else text + value
            elif kind == "final":
                final, usage = value
                break
            else:
                continue
            on_delta(text)
    except requests.RequestException as e:
        raise ApiError(f"네트워크 오류(스트리밍 중): {e}") from e
    finally:
        response.close()
    result = final if final else text
    # 2.0: 정식 조각(delta)·최종 답(final)을 받았으면 그 글이 답이다. 모델이 JSON 예시를 답하면 한 필드("OK")로 바뀌던 문제
    if not saw_delta and not final and result.lstrip().startswith("{"):
        # 형식 표시 없이 JSON 응답 하나를 통째로 보낸 경우({"message": ...})
        try:
            result = _response_text(json.loads(result)) or result
        except ValueError:
            pass
    if not result and not (cancelled and cancelled()):
        raise _StreamFormatError("받은 내용이 없습니다")
    return result, usage


def _chunk(event, data):
    """스트림 조각 하나를 (종류, 값)으로 바꾼다. 종류: delta, chunk, final, done, None(무시)."""
    if event is RAW:
        return "delta", data
    if data.strip() == "[DONE]":
        return "done", None
    try:
        obj = json.loads(data)
    except ValueError:
        return "chunk", data  # JSON이 아닌 일반 텍스트 조각
    if isinstance(obj, str):
        return "chunk", obj
    if not isinstance(obj, dict):
        return None, None
    kind = obj.get("type") or event or ""
    if kind == "response.output_text.delta":
        return "delta", str(obj.get("delta", ""))
    if kind == "response.completed":
        return "final", (_response_text(obj.get("response") or {}) or None, _usage(obj))
    if kind in ("response.failed", "response.incomplete", "error"):
        err = (obj.get("response") or {}).get("error") or obj.get("error") or obj
        raise ApiError(f"모델 오류: {json.dumps(err, ensure_ascii=False)[:300]}")
    if kind.startswith("response."):
        return None, None  # 생성 시작·추론 요약 같은 진행 이벤트
    choices = obj.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        content = (choices[0].get("delta") or {}).get("content")
        return ("delta", content) if isinstance(content, str) else (None, None)
    for key in ("delta", "text", "content", "message", "answer"):
        if isinstance(obj.get(key), str):
            return "chunk", obj[key]
    return None, None
