# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""Adaptive Hybrid AI Engine(1.17): 라우터(adaptive_router)가 고른 곳으로 보내고, 로컬 답을 검증(quality_gate)해서
필요하면 같은 로컬 모델로 한 번 더 하거나 정책이 허용할 때 Cloud로 올린다(cascade). 비용·지연·검증 결과를 기록한다.

설정 config["adaptive"](기본은 꺼짐 — 켜기 전에는 예전과 똑같이 대화마다 고른 Cloud 모델만 쓴다):
    enabled, policy(economy|balanced|quality|local_only), escalation(자동 Cloud 승격), max_escalations(요청 하나에서 승격 횟수, 0~2),
    local_retries(같은 로컬 모델로 다시, 0~1), local{endpoint, allow_remote, default_model, num_ctx}, cloud_model,
    budget{weekly_calls, weekly_credits}(0이면 없음), max_cost_per_request(크레딧, 0이면 없음), latency(normal|fast),
    privacy{sensitive_local_only, attachments_to_cloud}, local_only_tools(allow|block: Local Only일 때 MCP 같은 외부 도구), manual_fallback

대화의 모델: "auto"면 이 엔진이 고르고, "local:<모델>"이면 그 로컬 모델만 쓴다(실패해도 Cloud로 바꾸지 않는다 — manual_fallback을 켠 경우만).
그 밖의 모델 ID는 예전처럼 그 Cloud 모델을 직접 부른다(엔진을 거치지 않는다).

부작용 중복 방지: ask()는 글만 돌려주는 순수한 호출이다. 다시 하기·승격은 모두 ask() 안에서 끝나고, 에이전트는 돌려받은
단계 하나를 한 번만 실행한다(agent.py). 그래서 모델을 다시 불러도 파일 쓰기·명령·외부 쓰기가 두 번 일어나지 않는다.

기록(telemetry, 내용 없이): routing_decision · local_inference · cloud_inference · quality_check · escalation · routing_failure
"""
import json
import re
import threading
import time

import adaptive_cost
import adaptive_router as router
import connectors
import local_ai
import quality_gate
import telemetry

DEFAULTS = {
    "enabled": False, "policy": "balanced", "escalation": True, "max_escalations": 2, "local_retries": 1,
    # 3단계(1.17): 경량 Cloud 모델(예: Claude Haiku 5.5·GPT-5 mini). 비우면 쓰지 않는다(로컬 → 프런티어 2단계).
    # consult: 경량 모델이 필요할 때 프런티어에 짧은 질문만 보내 상담. consult_max: 요청 하나에서 상담 횟수(0~2).
    "light_model": "", "consult": True, "consult_max": 1,
    # tiered: 3단계(경량 모델·상담)를 쓸지. 기본 꺼짐 — 켜야 light_model을 쓴다(설정 → AI 실행 정책 → 3단계 켜기).
    # prompt_cache: 같은 앞부분(대화·지시)을 프롬프트 캐시로 표시(Claude API). 상담의 두 번째 경량 호출·에이전트 단계에서 쓴다.
    #   기본 켜짐(토큰 효율): 한 번 부르고 끝나는 대화는 캐시 표시를 하지 않고, 여러 단계를 도는 작업에서만 쓴다.
    # prices: {모델: {input, output, cache_read, cache_write, call}} 100만 토큰당 단가(단위는 모두 같게). 경량·프런티어 단가가
    #   모두 있으면 요청마다 손익분기(adaptive_cost)로 경량·상담·프런티어 중 싼 쪽을 고른다. 없으면 크레딧 기준, 그것도 없으면 규칙만.
    "tiered": False, "prompt_cache": True, "prices": {},
    "local": {"endpoint": local_ai.DEFAULT_ENDPOINT, "allow_remote": False, "default_model": "", "num_ctx": 8192, "speed": {}},
    "cloud_model": "", "budget": {"weekly_calls": 0, "weekly_credits": 0}, "max_cost_per_request": 0, "latency": "normal",
    "privacy": {"sensitive_local_only": False, "attachments_to_cloud": True}, "local_only_tools": "allow",
    "manual_fallback": False, "show_badge": True,
}
MAX_ESCALATIONS = 2          # 요청 하나에서 Cloud 승격 상한(설정이 더 커도)
RUN_ESCALATION_CAP = 6       # 에이전트 실행 하나(여러 단계)에서 승격 상한: 끝없는 비용을 막는다
EST_OUTPUT_TOKENS = 600      # Cloud 비용 추정에 쓰는 답 길이(토큰, 어림)
RUN_CONSULT_CAP = 6         # 실행 하나에서 프런티어 상담 상한
CONSULT_PURPOSES = ("chat", "po_note", "thread_summary")   # 상담을 쓰는 호출(JSON 단계·메모리 추출은 쓰지 않는다)
CONSULT_MARK = "<<CONSULT>>"
CONSULT_RE = re.compile(r"^\s*<<CONSULT>>\s*(\{.*\})\s*$", re.S)
CONSULT_RULE = (
    "[상위 모델 상담 — 이 안내는 앱이 붙였습니다]\n"
    "당신은 빠른 경량 모델입니다. 혼자 정확히 답할 수 있으면 바로 사용자에게 답하세요(이 안내는 말하지 마세요).\n"
    "깊은 추론·검증·계산이 필요해 확신이 없을 때만, 답 대신 아래 꼴의 한 줄만 쓰세요. 상위(프런티어) 모델이 그 질문에만 답하고, "
    "그 답을 받아 당신이 사용자에게 최종 답을 씁니다.\n"
    '<<CONSULT>>{"question": "상위 모델에게 물을 구체적인 질문 하나", "context": "질문에 꼭 필요한 원문·조건만 짧게(대화 전체를 붙이지 마세요)"}')
MAX_CONSULT_QUESTION, MAX_CONSULT_CONTEXT = 1500, 4000
DEFAULT_P_ESCALATE = 0.15    # 경량 모델 답이 검증에 실패할 확률(표본이 모자랄 때의 어림)
MIN_P_ESCALATE_SAMPLES = 10
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
RETRY_HINTS = {
    "json": "[형식 안내] 설명 없이 JSON 객체 하나로만 답하세요.",
    "action": '[형식 안내] {"action": ...} 형식의 JSON 객체 하나로만 답하세요. action은 [단계 종류]에 있는 이름만 씁니다.',
    "empty": "[형식 안내] 빈 답을 하지 말고 요청에 답하세요.",
    "repetition": "[형식 안내] 같은 문장을 되풀이하지 말고 간결하게 답하세요.",
    "truncated": "[형식 안내] 더 짧고 간결하게 답하세요.",
}


class AdaptiveError(Exception):
    pass


def settings(config):
    """config["adaptive"]에 기본값을 채운 사본."""
    raw = (config or {}).get("adaptive") or {}
    out = {}
    for key, default in DEFAULTS.items():
        value = raw.get(key, default)
        if isinstance(default, dict):
            value = {**default, **(value if isinstance(value, dict) else {})}
        out[key] = value
    if out["policy"] not in router.POLICIES:
        out["policy"] = "balanced"
    out["max_escalations"] = max(0, min(MAX_ESCALATIONS, int(out.get("max_escalations") or 0)))
    out["local_retries"] = max(0, min(1, int(out.get("local_retries") or 0)))
    out["consult_max"] = max(0, min(2, int(out.get("consult_max") or 0)))
    out["tiered"] = bool(out.get("tiered"))
    out["prompt_cache"] = bool(out.get("prompt_cache"))
    out["prices"] = out["prices"] if isinstance(out.get("prices"), dict) else {}
    return out


def active(config):
    """자동 선택을 켰는지. 안드로이드에서 켜도 로컬 후보가 없을 뿐 라우팅(Cloud 쪽)은 그대로 돈다."""
    return bool(settings(config)["enabled"])


def local_only(config):
    s = settings(config)
    return bool(s["enabled"]) and s["policy"] == "local_only"


def is_auto(model):
    return model == "auto"


def local_model_of(model):
    """'local:<모델>' → '<모델>', 아니면 ''."""
    model = str(model or "")
    return model[6:] if model.startswith("local:") else ""


class LocalRuntime:
    """로컬 실행기의 상태(연결·모델·기능·자원)를 잠시 기억한다. Bridge가 하나를 두고 여러 실행이 같이 쓴다(스레드 안전)."""

    HEALTH_TTL, MODELS_TTL, RES_TTL = 20, 60, 120

    def __init__(self, config_getter, provider_factory=None):
        self._config = config_getter
        self._factory = provider_factory or local_ai.make_provider
        self._lock = threading.Lock()
        self._cache = {}
        self._provider = None
        self._provider_key = None

    def provider(self):
        local = settings(self._config())["local"]
        key = (local.get("endpoint"), bool(local.get("allow_remote")))
        with self._lock:
            if self._provider is None or self._provider_key != key:
                self._provider = self._factory(self._config())
                self._provider_key = key
                self._cache.clear()
            return self._provider

    def _cached(self, name, ttl, fn):
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(name)
            if hit and now - hit[0] < ttl:
                return hit[1]
        value = fn()
        with self._lock:
            self._cache[name] = (now, value)
        return value

    def forget(self):
        with self._lock:
            self._cache.clear()

    def health(self):
        try:
            p = self.provider()
        except local_ai.LocalAIError as e:
            return {"ok": False, "error": str(e), "kind": e.kind, "version": "", "endpoint": ""}
        return self._cached("health", self.HEALTH_TTL, p.health_check)

    def models(self):
        if not self.health().get("ok"):
            return []
        try:
            return self._cached("models", self.MODELS_TTL, self.provider().list_models)
        except local_ai.LocalAIError:
            return []

    def capabilities(self, model):
        return self._cached("caps:" + model, self.MODELS_TTL * 5, lambda: self.provider().capabilities(model))

    def resources(self):
        return self._cached("res", self.RES_TTL, local_ai.system_resources)

    def candidate(self, model):
        """(Candidate 또는 None, 쓸 수 없는 이유)."""
        if not local_ai.SUPPORTED:
            return None, "이 기기에서는 로컬 AI를 쓸 수 없음"
        if not model:
            return None, "기본 로컬 모델을 고르지 않음"
        health = self.health()
        if not health.get("ok"):
            return None, health.get("error") or "로컬 AI에 연결하지 못함"
        info = next((m for m in self.models() if m["id"] == model), None)
        if info is None:
            return None, f"로컬 모델 '{model}'이(가) 설치되어 있지 않음"
        try:
            caps = self.capabilities(model)
        except local_ai.LocalAIError as e:
            return None, str(e)
        if not caps.get("completion"):
            return None, "이 로컬 모델은 글을 만들지 못함(임베딩 전용 등)"
        num_ctx = int(settings(self._config())["local"].get("num_ctx") or 8192)
        ctx = min(num_ctx, caps.get("context_length") or num_ctx)
        need = local_ai.estimate_memory(info.get("size"), ctx)
        budget = local_ai.memory_budget(self.resources())
        speed = (settings(self._config())["local"].get("speed") or {}).get(model) or {}
        return router.Candidate(provider="local", model=model, context_length=ctx, vision=bool(caps.get("vision")),
                                json=bool(caps.get("json")), memory_ok=need is None or need <= budget,
                                tokens_per_s=float(speed.get("tokens_per_s") or 0)), ""


def cloud_cost(model, est_tokens, rates=None):
    """Cloud 요청 하나의 POSTECH 크레딧 추정. 근거가 있는 모델(telemetry.DOCUMENTED_RATES 또는 사용자가 정한 값)만, 아니면 None."""
    return telemetry.credit_estimate(model, est_tokens, EST_OUTPUT_TOKENS, 1, rates)


def budget_state(config, now=None):
    """지난 7일 Cloud 사용(이 앱의 모든 Cloud 호출)과 주간 예산. {"calls", "credits", "exceeded", "limit_calls", "limit_credits"}."""
    s = settings(config)
    limit_calls = int((s["budget"] or {}).get("weekly_calls") or 0)
    limit_credits = float((s["budget"] or {}).get("weekly_credits") or 0)
    calls, credits = 0, 0.0
    if limit_calls or limit_credits:
        rates = ((config or {}).get("telemetry") or {}).get("rates") or {}
        for e in telemetry.load(7, now):
            if e.get("type") == "llm_call" and e.get("ok", True):
                calls += 1
                est = telemetry.credit_estimate(e.get("model"), e.get("input_tokens") or 0, e.get("output_tokens") or 0, 1, rates)
                credits += est or 0
    exceeded = bool(limit_calls and calls >= limit_calls) or bool(limit_credits and credits >= limit_credits)
    return {"calls": calls, "credits": round(credits, 1), "exceeded": exceeded, "limit_calls": limit_calls,
            "limit_credits": limit_credits}


class AdaptiveEngine:
    """에이전트 실행 하나 동안 쓴다. ask()는 모델 답(글)을 돌려주고, 고른 경로는 self.routes에 쌓는다."""

    def __init__(self, config, runtime, cloud_ask, cloud_model, cloud_available, mode="auto", on_event=None,
                 cancelled=None, area_hint="", light_model="", frontier_session=None):
        """cloud_ask(prompt, model, on_delta, images) -> 글(api.ask로 보낸다). mode: "auto" | "local:<모델>".
        light_model: 3단계의 경량 Cloud 모델(같은 API 방식에서 고를 수 있는 모델, 없으면 ""). frontier_session: 이 대화의
        지난 프런티어 상담 기록 [{"q", "a", "at"}](Bridge가 대화에 저장해 두었다가 넘긴다)."""
        self.config = config
        self.s = settings(config)
        self.runtime = runtime
        self.cloud_ask = cloud_ask
        self.cloud_model = cloud_model
        self.cloud_available = bool(cloud_available) and self.s["policy"] != "local_only"
        self.mode = mode
        self.on_event = on_event or (lambda ev: None)
        self.cancelled = cancelled or (lambda: False)
        self.area_hint = area_hint
        self.routes = []
        self.escalations = 0
        self.consults = 0
        self._budget = None
        # 3단계는 설정에서 켰을 때만(tiered). 끄면 경량 모델을 골라 두었어도 예전처럼 로컬 → 프런티어 2단계다.
        self.light_model = light_model if (self.s["tiered"] and light_model and self.cloud_available
                                           and light_model != cloud_model) else ""
        self.last_usage = {}          # 마지막 Cloud 호출에서 서버가 알려 준 토큰 사용량(없으면 {})
        self._profile = None          # 손익분기 계산에 쓰는 토큰 분포(실측 평균, 실행마다 한 번 읽는다)
        self.frontier_session = list(frontier_session or [])[-6:]

    # ---- 도우미 ----

    def _emit(self, **ev):
        try:
            self.on_event(ev)
        except Exception:
            pass

    def _budget_state(self):
        if self._budget is None or time.monotonic() - self._budget[0] > 30:
            self._budget = (time.monotonic(), budget_state(self.config))
        return self._budget[1]

    def _rates(self):
        return ((self.config or {}).get("telemetry") or {}).get("rates") or {}

    def _local(self, model, prompt, images, on_delta, json_format, num_ctx):
        p = self.runtime.provider()
        req = local_ai.LocalRequest(model=model, prompt=prompt, images=list(images or []), timeout=600,
                                    num_ctx=num_ctx, json_format=json_format)
        start = time.monotonic()
        try:
            res = p.stream(req, on_delta, self.cancelled)
        except local_ai.LocalAIError as e:
            telemetry.record("local_inference", model=f"local:{model}", ms=int((time.monotonic() - start) * 1000), ok=False,
                             error=e.kind, area=self.area_hint)
            raise
        telemetry.record("local_inference", model=f"local:{model}", ms=res.ms, ok=True, error="", area=self.area_hint,
                         input_tokens=res.input_tokens, output_tokens=res.output_tokens, tokens_per_s=res.tokens_per_s,
                         load_ms=res.load_ms, done_reason=res.done_reason)
        return res

    def _cloud(self, prompt, on_delta, images, model=None, escalated=False, tier="frontier", purpose="", cache_prefix=0):
        """cloud_ask(prompt, model, on_delta, images[, cache_prefix=]) → 글 또는 (글, 사용량). 사용량은 서버가 알려 준 실제 토큰
        {input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens}이고 self.last_usage에 남긴다."""
        model = model or self.cloud_model
        start = time.monotonic()
        tokens = router.estimate_tokens(prompt)
        cache_prefix = cache_prefix if self.s["prompt_cache"] and cache_prefix else 0
        self.last_usage = {}
        try:
            reply = self.cloud_ask(prompt, model, on_delta, images, **({"cache_prefix": cache_prefix} if cache_prefix else {}))
        except Exception as e:
            telemetry.record("cloud_inference", model=model, ms=int((time.monotonic() - start) * 1000), ok=False,
                             error=type(e).__name__, area=self.area_hint, escalated=escalated, tier=tier, est_tokens=tokens,
                             purpose=purpose)
            raise
        text, usage = reply if isinstance(reply, tuple) else (reply, None)
        usage = {k: int(v) for k, v in (usage or {}).items() if k in USAGE_KEYS and isinstance(v, (int, float))}
        self.last_usage = usage
        est = telemetry.credit_estimate(model, usage.get("input_tokens", tokens), usage.get("output_tokens", EST_OUTPUT_TOKENS), 1,
                                        self._rates())
        telemetry.record("cloud_inference", model=model, ms=int((time.monotonic() - start) * 1000), ok=True, error="",
                         area=self.area_hint, credits_est=est, escalated=escalated, tier=tier, est_tokens=tokens, purpose=purpose,
                         cache_prefix=bool(cache_prefix), measured=bool(usage), **usage)
        return text

    def _attempt(self, provider, model, t0, **extra):
        """기록할 시도 하나. Cloud 호출이면 서버가 알려 준 토큰 사용량(있으면)을 붙인다."""
        row = {"provider": provider, "model": model, "ok": True, "ms": int((time.monotonic() - t0) * 1000), **extra}
        if provider != "local" and self.last_usage:
            row["usage"] = dict(self.last_usage)
        return row

    def _name(self, tier):
        return {"local": "Local", "light": "Light"}.get(tier) or ("Frontier" if self.light_model else "Cloud")

    def _label(self, provider, task, escalated=False, failed=False, chain=None, consulted=False):
        task_label = router.TASK_LABELS.get(task, task)
        if chain and len(chain) > 1:
            return " → ".join(self._name(t) for t in chain) + f" · {task_label}" + (" · 검증 실패" if failed else "")
        if escalated:
            return f"Local → {self._name('frontier')} · {task_label}"
        if consulted:
            return f"Light ⇄ Frontier · {task_label}"
        tier = "local" if provider == "local" else "light" if provider == "light" else "frontier"
        return self._name(tier) + f" · {task_label}" + (" · 검증 실패" if failed else "")

    # ---- 본체 ----

    def ask(self, prompt, purpose="chat", task_text="", on_delta=None, images=None, side_effects=False, attachments=False,
            cache_prefix=0):
        """cache_prefix: prompt의 앞부분 몇 글자가 호출마다 같은지(에이전트 단계의 지시·도구·대화). 프롬프트 캐싱을 켰을 때만 쓴다."""
        started = time.monotonic()
        self._cache_prefix = int(cache_prefix or 0)
        a = router.analyze(prompt, task_text, purpose, images=bool(images), attachments=attachments, side_effects=side_effects)
        manual_local = local_model_of(self.mode)
        record = {"purpose": purpose, "task": a.task, "difficulty": a.difficulty, "policy": self.s["policy"], "attempts": [],
                  "task_label": router.TASK_LABELS.get(a.task, a.task), "difficulty_label": router.DIFF_LABELS.get(a.difficulty, ""),
                  "escalated": False, "api_call": False, "status": "", "est_cost": None}
        if manual_local:
            # 2.0: 직접 고른 로컬 모델이 실패해 Cloud로 넘길 때도 개인정보 설정(민감 정보·첨부는 로컬만)을 지킨다.
            # 라우터(router.route)를 거치지 않는 길이라 예전에는 이 설정을 보지 않고 Cloud로 보냈다
            privacy_cfg = self.s.get("privacy") or {}
            keep_local = bool((privacy_cfg.get("sensitive_local_only") and a.sensitive)
                              or (privacy_cfg.get("attachments_to_cloud") is False and a.attachments))
            cloud_ok = self.cloud_available and not keep_local
            route = router.Route(provider="local", model=manual_local, policy=self.s["policy"], reason_code="manual",
                                 reason="직접 고른 로컬 모델", analysis=a.__dict__, stage="manual",
                                 escalation=bool(self.s.get("manual_fallback")) and cloud_ok,
                                 fallback_model=self.cloud_model if cloud_ok else "")
        else:
            route = self._route(a, purpose)
        record.update(provider=route.provider, model=route.model, reason=route.reason, reason_code=route.reason_code,
                      stage=route.stage, constraints=list(route.constraints), tier=route.tier or "")
        if route.economics:
            record["economics"] = route.economics
        telemetry.record("routing_decision", area=self.area_hint or purpose, purpose=purpose, task=a.task, difficulty=a.difficulty,
                         method=a.method, confidence=a.confidence, provider=route.provider,
                         model=(f"local:{route.model}" if route.provider == "local" else route.model), policy=self.s["policy"],
                         reason=route.reason_code, stage=route.stage, constraints=list(route.constraints),
                         ms=int((time.monotonic() - started) * 1000), est_tokens=a.est_tokens, tier=route.tier or "",
                         consult=bool(route.consult),
                         breakeven=_econ_row(route.economics),
                         cloud_cost_est=cloud_cost(self.cloud_model, a.est_tokens, self._rates()) if self.cloud_model else None)
        if route.provider == "none":
            telemetry.record("routing_failure", kind=route.reason_code, policy=self.s["policy"], purpose=purpose)
            record.update(status="blocked", label="보낼 곳 없음")
            self.routes.append(record)
            self._emit(kind="route", route=record)
            raise AdaptiveError(route.reason)
        if route.provider == "cloud":
            record.update(api_call=True, est_cost=route.est_cost, label=self._label("cloud", a.task), status="cloud")
            self._emit(kind="route", route=record)
            t0 = time.monotonic()
            text = self._cloud(prompt, on_delta, images, route.model, purpose=purpose, cache_prefix=self._cache_prefix)
            record["attempts"].append(self._attempt("cloud", route.model, t0))
            gate = quality_gate.check(quality_gate.area_for(a.task, purpose), text, self._gate_ctx(prompt, a, purpose))
            telemetry.record("quality_check", provider="cloud", model=route.model, task=a.task, area=quality_gate.area_for(a.task, purpose),
                             ok=gate.ok, verifiable=gate.verifiable, failures=gate.failures, purpose=purpose)
            record.update(gate=gate.to_dict(), ms=int((time.monotonic() - started) * 1000))
            self.routes.append(record)
            return text
        if route.provider == "light":
            record.update(api_call=True, est_cost=route.est_cost, chain=["light"])
            return self._run_light(prompt, purpose, a, route, record, on_delta, images, started)
        return self._run_local(prompt, purpose, a, route, record, on_delta, images, started)

    def _route(self, a, purpose="chat"):
        local, why_not = self.runtime.candidate(self.s["local"].get("default_model")) if local_ai.SUPPORTED else (None, "")
        cloud = None
        if self.cloud_available and self.cloud_model:
            cloud = router.Candidate(provider="cloud", model=self.cloud_model,
                                     cost=cloud_cost(self.cloud_model, a.est_tokens, self._rates()))
        route = router.route(a, self.s["policy"], local, cloud, self.s, router.load_stats(), self._budget_state())
        light = router.Candidate(provider="cloud", model=self.light_model, cost=cloud_cost(self.light_model, a.est_tokens, self._rates())) \
            if self.light_model else None
        route = router.tier(route, a, light, self.s, allow_consult=purpose in CONSULT_PURPOSES and self.consults < RUN_CONSULT_CAP)
        if route.provider == "light":
            route = self._economics(route, a)
        if local is None and why_not and route.provider != "local" and "local_unavailable" not in route.constraints:
            route.constraints.append("local_unavailable")
            if route.provider == "none" or route.reason_code in ("local_unavailable", "local_required_unavailable"):
                route.reason = route.reason.replace("로컬 모델 없음", why_not)
        return route

    def _economics(self, route, a):
        """규칙이 경량 모델(혼자·상담)을 고른 요청을 단가로 다시 본다(adaptive_cost). 프런티어가 더 싸면 프런티어로 바꾼다.
        품질 때문에 규칙이 프런티어로 정한 요청은 단가가 싸도 경량으로 내리지 않는다(값은 판단을 비싼 쪽으로만 바꾼다)."""
        pl, src_l = adaptive_cost.prices_for(self.light_model, self.s["prices"], self._rates())
        pf, src_f = adaptive_cost.prices_for(self.cloud_model, self.s["prices"], self._rates())
        if pl is None or pf is None or src_l != src_f:
            route.economics = {"known": False, "light_source": src_l, "frontier_source": src_f}
            return route
        rate, n = router.success_rate(router.load_stats(), self.light_model, a.task)
        p_esc = (1 - rate) if rate is not None and n >= MIN_P_ESCALATE_SAMPLES else DEFAULT_P_ESCALATE
        d = adaptive_cost.decide(pl, pf, self._cost_profile(a.est_tokens), p_esc, cache=self.s["prompt_cache"])
        d.update(known=True, source=src_l, p_escalate_samples=n)
        route.economics = d
        mode = "consult" if route.reason_code == "light_consult" else "light"
        r, be = d["ratio"], d["breakeven_" + mode]
        if d["costs"][mode] >= d["costs"]["frontier"]:
            route.provider, route.model, route.tier, route.consult = "cloud", self.cloud_model, "frontier", False
            route.reason_code = "breakeven_frontier"
            route.est_cost = cloud_cost(self.cloud_model, a.est_tokens, self._rates())
            route.reason = (f"{router.TASK_LABELS.get(a.task, a.task)} · 단가 비율 {r} ≥ 손익분기 {be} → 프런티어가 더 쌈"
                            if be is not None else f"{router.TASK_LABELS.get(a.task, a.task)} · 프런티어 직접이 더 쌈")
        elif mode == "light" and route.consult and d["costs"]["consult"] >= d["costs"]["frontier"]:
            route.consult = False   # 상담까지 하면 프런티어 직접보다 비싸다: 경량 모델 혼자, 실패하면 승격
            route.reason += " · 상담은 손익분기를 넘어 끔"
        return route

    def _cost_profile(self, est_tokens):
        """손익분기 계산의 토큰 분포: 최근 30일 서버 사용량의 평균(실측)과 이번 요청 길이. 기록은 실행마다 한 번만 읽는다."""
        if self._profile is None:
            try:
                self._profile = [e for e in telemetry.load(30) if e.get("type") == "cloud_inference" and e.get("measured")]
            except Exception:
                self._profile = []
        prof = adaptive_cost.measured_profile(self._profile, est_tokens)
        prof.R = router.estimate_tokens(CONSULT_RULE)
        return prof

    def _gate_ctx(self, prompt, a, purpose):
        return {"prompt": prompt, "korean": a.korean, "json": purpose == "memory_extract", "pages": 0}

    def _run_local(self, prompt, purpose, a, route, record, on_delta, images, started):
        area = quality_gate.area_for(a.task, purpose)
        json_format = purpose in ("memory_extract", "agent_step", "agent_convert", "code_agent_step")
        route_ctx = int(self.s["local"].get("num_ctx") or 8192)
        record.update(label=self._label("local", a.task), status="provisional")
        self._emit(kind="route", route=record)
        if on_delta:
            self._emit(kind="provisional", provider="local", model=route.model)
        attempt_prompt, retries_left = prompt, self.s["local_retries"]
        text, gate, local_error = "", None, None
        while True:
            t0 = time.monotonic()
            try:
                res = self._local(route.model, attempt_prompt, images, on_delta, json_format, route_ctx)
            except local_ai.LocalAIError as e:
                local_error = e
                record["attempts"].append({"provider": "local", "model": route.model, "ok": False, "error": e.kind,
                                           "detail": str(e)[:200], "ms": int((time.monotonic() - t0) * 1000)})
                break
            text = res.text
            if res.done_reason == "cancelled" or self.cancelled():
                record.update(status="cancelled", ms=int((time.monotonic() - started) * 1000))
                self.routes.append(record)
                return text
            ctx = self._gate_ctx(prompt, a, purpose)
            ctx["done_reason"] = res.done_reason
            gate = quality_gate.check(area, text, ctx)
            telemetry.record("quality_check", provider="local", model=f"local:{route.model}", task=a.task, area=area, ok=gate.ok,
                             verifiable=gate.verifiable, failures=gate.failures, purpose=purpose)
            router.record_outcome(f"local:{route.model}", a.task, gate.ok)
            record["attempts"].append({"provider": "local", "model": route.model, "ok": gate.ok, "detail": gate.detail,
                                       "ms": res.ms, "tokens_per_s": res.tokens_per_s,
                                       "usage": {"input_tokens": res.input_tokens or 0, "output_tokens": res.output_tokens or 0}})
            if gate.ok:
                record.update(status="verified" if gate.verifiable else "unchecked", gate=gate.to_dict(),
                              ms=int((time.monotonic() - started) * 1000))
                self.routes.append(record)
                self._emit(kind="verified", route=record)
                return text
            if gate.retryable and retries_left > 0:
                retries_left -= 1
                hint = next((RETRY_HINTS[f] for f in gate.failures if f in RETRY_HINTS), RETRY_HINTS["empty"])
                attempt_prompt = prompt + "\n\n" + hint
                self._emit(kind="retry", route=record, reason=gate.detail)
                continue
            break
        reason = gate.detail if gate is not None else (str(local_error) if local_error else "")
        can_escalate = (route.escalation and self.cloud_available and self.cloud_model
                        and self.escalations < RUN_ESCALATION_CAP and self.s["max_escalations"] > 0
                        and not self.cancelled() and not self._budget_state()["exceeded"])
        if can_escalate and self.light_model and router.light_ok_for(self.s["policy"], a):
            # 3단계: 로컬이 실패하면 경량 모델로 먼저(그것도 실패하면 _run_light가 프런티어로 올린다)
            self.escalations += 1
            telemetry.record("escalation", from_model=f"local:{route.model}", to_model=self.light_model, task=a.task, purpose=purpose,
                             reason=(gate.failures if gate is not None else [local_error.kind]), policy=self.s["policy"])
            record.update(escalated=True, provisional=text[:4000], escalation_reason=reason, api_call=True, chain=["local", "light"],
                          label=self._label("local", a.task, chain=["local", "light"]))
            self._emit(kind="escalating", route=record, reason=reason, to=self.light_model)
            light_route = router.Route(provider="light", model=self.light_model, policy=self.s["policy"], tier="light",
                                       consult=False, escalation=True)
            return self._run_light(prompt, purpose, a, light_route, record, on_delta, images, started, fallback_text=text)
        if can_escalate:
            self.escalations += 1
            telemetry.record("escalation", from_model=f"local:{route.model}", to_model=self.cloud_model, task=a.task, purpose=purpose,
                             reason=(gate.failures if gate is not None else [local_error.kind]), policy=self.s["policy"])
            provisional = text[:4000]
            record.update(escalated=True, provisional=provisional, escalation_reason=reason, label=self._label("local", a.task, True),
                          api_call=True, status="escalating", est_cost=cloud_cost(self.cloud_model, a.est_tokens, self._rates()),
                          chain=["local", "frontier"])
            self._emit(kind="escalating", route=record, reason=reason, to=self.cloud_model)
            t0 = time.monotonic()
            try:
                answer = self._cloud(prompt, on_delta, images, self.cloud_model, escalated=True, purpose=purpose,
                                     cache_prefix=self._cache_prefix)
            except Exception as e:
                record["attempts"].append({"provider": "cloud", "model": self.cloud_model, "ok": False, "error": type(e).__name__,
                                           "ms": int((time.monotonic() - t0) * 1000)})
                telemetry.record("routing_failure", kind="escalation_failed", policy=self.s["policy"], purpose=purpose)
                if text.strip():  # Cloud도 실패: 검증 못 한 로컬 답을 표시와 함께 돌려준다(조용히 버리거나 덮지 않는다)
                    record.update(status="unverified", ms=int((time.monotonic() - started) * 1000),
                                  label=self._label("local", a.task, failed=True),
                                  escalation_error=str(e)[:200])
                    self.routes.append(record)
                    return text
                raise
            record["attempts"].append(self._attempt("cloud", self.cloud_model, t0))
            cg = quality_gate.check(area, answer, self._gate_ctx(prompt, a, purpose))
            telemetry.record("quality_check", provider="cloud", model=self.cloud_model, task=a.task, area=area, ok=cg.ok,
                             verifiable=cg.verifiable, failures=cg.failures, purpose=purpose, escalated=True)
            record.update(status="escalated", gate=cg.to_dict(), model=self.cloud_model, provider="cloud",
                          ms=int((time.monotonic() - started) * 1000))
            self.routes.append(record)
            self._emit(kind="final", route=record)
            return answer
        if local_error is not None and not text:
            telemetry.record("routing_failure", kind=f"local_{local_error.kind}", policy=self.s["policy"], purpose=purpose)
            record.update(status="failed", ms=int((time.monotonic() - started) * 1000))
            self.routes.append(record)
            raise AdaptiveError(str(local_error) + ("" if route.escalation else " (Cloud 승격을 쓰지 않는 설정·정책입니다)"))
        record.update(status="unverified", gate=gate.to_dict() if gate else None, label=self._label("local", a.task, failed=True),
                      ms=int((time.monotonic() - started) * 1000))
        self.routes.append(record)
        self._emit(kind="unverified", route=record, reason=reason)
        return text

    # ---- 3단계: 경량 Cloud 모델과 프런티어 상담 ----

    def _run_light(self, prompt, purpose, a, route, record, on_delta, images, started, fallback_text=""):
        """경량 모델이 답한다. 상담을 허용했으면 '<<CONSULT>>' 한 줄로 프런티어에 짧게 물을 수 있다. 검증에 실패하면 프런티어로."""
        area = quality_gate.area_for(a.task, purpose)
        chain = record.get("chain") or ["light"]
        consult_ok = route.consult and self.s["consult_max"] > 0 and purpose in CONSULT_PURPOSES and self.consults < RUN_CONSULT_CAP
        record.update(label=self._label("light", a.task, chain=chain if len(chain) > 1 else None), status="light")
        self._emit(kind="route", route=record)
        attempt = prompt + ("\n\n" + CONSULT_RULE if consult_ok else "")

        def delta(text):  # 상담 요청 줄은 화면에 흘려보내지 않는다
            head = text.lstrip()
            if not on_delta or CONSULT_MARK.startswith(head[:len(CONSULT_MARK)]) or head.startswith(CONSULT_MARK):
                return
            on_delta(text)

        t0 = time.monotonic()
        try:
            # 프롬프트 캐싱: 요청 본문(prompt)을 캐시에 써 두면 상담 뒤 두 번째 호출은 같은 앞부분을 캐시로 읽는다
            text = self._cloud(attempt, delta if on_delta else None, images, self.light_model, tier="light", purpose=purpose,
                               cache_prefix=max(self._cache_prefix, len(prompt)) if consult_ok else self._cache_prefix)
        except Exception as e:
            record["attempts"].append({"provider": "light", "model": self.light_model, "ok": False, "error": type(e).__name__,
                                       "ms": int((time.monotonic() - t0) * 1000)})
            return self._light_to_frontier(prompt, purpose, a, record, on_delta, images, started, fallback_text,
                                           "경량 모델 호출 실패", error=e)
        record["attempts"].append(self._attempt("light", self.light_model, t0))
        if CONSULT_MARK in text:
            m = CONSULT_RE.match(text)
            req = None
            if m and consult_ok:
                try:
                    req = json.loads(m.group(1))
                except ValueError:
                    req = None
            question = str((req or {}).get("question") or "").strip() if isinstance(req, dict) else ""
            if not question:
                return self._light_to_frontier(prompt, purpose, a, record, on_delta, images, started, fallback_text,
                                               "상담 요청 형식이 맞지 않음")
            context = str(req.get("context") or "")
            try:
                answer = self._consult(question, context, a, purpose, record)
            except Exception as e:
                return self._light_to_frontier(prompt, purpose, a, record, on_delta, images, started, fallback_text,
                                               "프런티어 상담 실패", error=e)
            final_prompt = (prompt + "\n\n[상위 모델(프런티어)의 답 — 참고 자료]\n" + answer +
                            "\n\n[지침] 위 답을 바탕으로 사용자에게 최종 답을 쓰세요. 상위 모델의 결론과 다르게 말하지 말고, "
                            "상담했다는 말이나 <<CONSULT>>는 쓰지 마세요.")
            record.update(consulted=True, label=self._label("light", a.task, chain=chain if len(chain) > 1 else None, consulted=True))
            self._emit(kind="consulted", route=record)
            t0 = time.monotonic()
            text = self._cloud(final_prompt, on_delta, images, self.light_model, tier="light", purpose=purpose,
                               cache_prefix=max(self._cache_prefix, len(prompt)))
            record["attempts"].append(self._attempt("light", self.light_model, t0, after_consult=True))
            if CONSULT_MARK in text:
                return self._light_to_frontier(prompt, purpose, a, record, on_delta, images, started, fallback_text,
                                               "상담 뒤에도 답하지 못함")
        gate = quality_gate.check(area, text, self._gate_ctx(prompt, a, purpose))
        telemetry.record("quality_check", provider="light", model=self.light_model, task=a.task, area=area, ok=gate.ok,
                         verifiable=gate.verifiable, failures=gate.failures, purpose=purpose)
        router.record_outcome(self.light_model, a.task, gate.ok)
        record["attempts"][-1].update(ok=gate.ok, detail=gate.detail)
        if gate.ok:
            record.update(status="verified" if gate.verifiable else "unchecked", gate=gate.to_dict(), model=self.light_model,
                          provider="light", ms=int((time.monotonic() - started) * 1000))
            self.routes.append(record)
            self._emit(kind="final", route=record)
            return text
        return self._light_to_frontier(prompt, purpose, a, record, on_delta, images, started, text, gate.detail, gate=gate)

    def _consult(self, question, context, a, purpose, record):
        """프런티어에 짧은 질문만 보낸다(대화 전체 대신). 이 대화의 지난 상담 기록을 함께 붙여 프런티어가 앞의 결론을 잇게 한다."""
        self.consults += 1
        session = "\n".join(f"- 질문: {x.get('q', '')}\n  답: {x.get('a', '')}" for x in self.frontier_session[-6:])
        fprompt = ("[상담 요청 — 다른 AI 모델(경량 모델)이 사용자 질문에 답하다가 이 부분만 묻습니다]\n"
                   + (f"[이전 상담 기록(이 대화)]\n{session}\n\n" if session else "")
                   + "[질문]\n" + question[:MAX_CONSULT_QUESTION]
                   + ("\n\n" + connectors.wrap_untrusted(context[:MAX_CONSULT_CONTEXT], "상담에 붙인 발췌") if context.strip() else "")
                   + "\n\n[지침] 이 질문에만 정확하고 간결하게 답하세요. 근거와 불확실한 점을 밝히세요.")
        t0 = time.monotonic()
        answer = self._cloud(fprompt, None, None, self.cloud_model, tier="frontier", purpose="consult")
        tokens = router.estimate_tokens(fprompt)
        telemetry.record("consult", light_model=self.light_model, frontier_model=self.cloud_model, task=a.task, purpose=purpose,
                         full_tokens_est=a.est_tokens, consult_tokens_est=tokens, ok=True)
        self.frontier_session.append({"q": question[:500], "a": answer[:1500], "at": round(time.time())})
        self.frontier_session = self.frontier_session[-6:]
        record["attempts"].append(self._attempt("frontier", self.cloud_model, t0, consult=True))
        record["consult"] = {"question_chars": len(question), "context_chars": len(context), "frontier_tokens_est": tokens,
                             "full_tokens_est": a.est_tokens}
        return answer

    def _light_to_frontier(self, prompt, purpose, a, record, on_delta, images, started, prev_text, reason, gate=None, error=None):
        """경량 모델 답이 실패·검증 실패: 허용되면 프런티어가 전체를 다시 답한다. 아니면 경량 답을 '검증 실패'로 표시해 돌려준다."""
        area = quality_gate.area_for(a.task, purpose)
        chain = (record.get("chain") or ["light"]) + ["frontier"]
        can = (self.cloud_model and bool(self.s.get("escalation", True)) and self.escalations < RUN_ESCALATION_CAP
               and len(chain) - 1 <= self.s["max_escalations"] and not self.cancelled() and not self._budget_state()["exceeded"])
        if not can:
            if prev_text.strip():
                record.update(status="unverified", gate=gate.to_dict() if gate else None, provider="light", model=self.light_model,
                              label=self._label("light", a.task, failed=True, chain=record.get("chain") if len(record.get("chain") or []) > 1 else None),
                              ms=int((time.monotonic() - started) * 1000), escalation_reason=reason)
                self.routes.append(record)
                self._emit(kind="unverified", route=record, reason=reason)
                return prev_text
            telemetry.record("routing_failure", kind="light_failed", policy=self.s["policy"], purpose=purpose)
            record.update(status="failed", ms=int((time.monotonic() - started) * 1000))
            self.routes.append(record)
            raise AdaptiveError(f"경량 모델이 답하지 못했고 프런티어로 올릴 수 없습니다({reason}).")
        self.escalations += 1
        telemetry.record("escalation", from_model=self.light_model, to_model=self.cloud_model, task=a.task, purpose=purpose,
                         reason=(gate.failures if gate is not None else [reason[:40]]), policy=self.s["policy"])
        record.update(escalated=True, escalation_reason=reason, chain=chain, label=self._label("light", a.task, chain=chain),
                      status="escalating", provisional=(record.get("provisional") or prev_text[:4000]))
        self._emit(kind="escalating", route=record, reason=reason, to=self.cloud_model)
        t0 = time.monotonic()
        try:
            answer = self._cloud(prompt, on_delta, images, self.cloud_model, escalated=True, purpose=purpose,
                                 cache_prefix=self._cache_prefix)
        except Exception as e:
            record["attempts"].append({"provider": "frontier", "model": self.cloud_model, "ok": False, "error": type(e).__name__,
                                       "ms": int((time.monotonic() - t0) * 1000)})
            telemetry.record("routing_failure", kind="escalation_failed", policy=self.s["policy"], purpose=purpose)
            if prev_text.strip():
                record.update(status="unverified", escalation_error=str(e)[:200], ms=int((time.monotonic() - started) * 1000))
                self.routes.append(record)
                return prev_text
            raise
        record["attempts"].append(self._attempt("frontier", self.cloud_model, t0))
        cg = quality_gate.check(area, answer, self._gate_ctx(prompt, a, purpose))
        telemetry.record("quality_check", provider="cloud", model=self.cloud_model, task=a.task, area=area, ok=cg.ok,
                         verifiable=cg.verifiable, failures=cg.failures, purpose=purpose, escalated=True)
        record.update(status="escalated", gate=cg.to_dict(), provider="cloud", model=self.cloud_model,
                      ms=int((time.monotonic() - started) * 1000))
        self.routes.append(record)
        self._emit(kind="final", route=record)
        return answer

    def summary(self):
        """대화에 남길 이번 실행의 라우팅 요약(화면의 작은 표시와 펼친 이유). 프롬프트·답 내용은 없다(임시 답 앞부분만)."""
        if not self.routes:
            return None
        main = next((r for r in reversed(self.routes) if r.get("purpose") in ("chat", "agent_final", "po_note")), self.routes[-1])
        counts = {"local": 0, "light": 0, "cloud": 0, "escalated": 0, "consulted": 0}
        for r in self.routes:
            if r.get("escalated"):
                counts["escalated"] += 1
            if r.get("consulted"):
                counts["consulted"] += 1
            if r.get("provider") in counts:
                counts[r["provider"]] += 1
        keep = ("provider", "model", "label", "reason", "task", "difficulty", "task_label", "difficulty_label", "policy", "status", "ms",
                "api_call", "est_cost", "tier", "chain", "consulted", "consult", "economics", "reason_code",
                "escalated", "escalation_reason", "provisional", "attempts", "gate", "stage", "constraints", "escalation_error")
        return {**{k: main.get(k) for k in keep}, "calls": len(self.routes), "counts": counts}


def _econ_row(e):
    """telemetry에 남길 손익분기 요약(숫자만)."""
    if not e or not e.get("known"):
        return None
    return {"ratio": e.get("ratio"), "breakeven_consult": e.get("breakeven_consult"), "breakeven_light": e.get("breakeven_light"),
            "best": e.get("best"), "p_escalate": e.get("p_escalate"), "cache": e.get("cache")}


# ---- 통계(사용량·진단) ----

def _p(values, q):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def summary(days=30, now=None, config=None):
    """Adaptive AI 통계. 측정하지 않은 값은 None으로 둔다(화면은 '-'·'추정 불가'). 크레딧은 근거 있는 모델만 추정한다."""
    events = telemetry.load(days, now)
    decisions = [e for e in events if e.get("type") == "routing_decision"]
    by_provider = {"local": 0, "light": 0, "cloud": 0, "none": 0}
    saved, saved_unknown = 0.0, 0
    for e in decisions:
        by_provider[e.get("provider", "cloud")] = by_provider.get(e.get("provider", "cloud"), 0) + 1
        if e.get("provider") == "local":
            if e.get("cloud_cost_est") is not None:
                saved += float(e["cloud_cost_est"])
            else:
                saved_unknown += 1
    esc = [e for e in events if e.get("type") == "escalation"]
    # 승격된 요청은 끝내 Cloud가 답했다: 처리 비율은 Cloud로 세고, 아낀 크레딧 추정에서도 그 Cloud 호출만큼 뺀다
    esc_cloud = [e for e in events if e.get("type") == "cloud_inference" and e.get("escalated") and e.get("ok")]
    saved -= sum(float(e.get("credits_est") or 0) for e in esc_cloud)
    saved_unknown += sum(1 for e in esc_cloud if e.get("credits_est") is None)
    local_runs = [e for e in events if e.get("type") == "local_inference"]
    cloud_runs = [e for e in events if e.get("type") == "cloud_inference"]
    checks = [e for e in events if e.get("type") == "quality_check"]
    failures = [e for e in events if e.get("type") == "routing_failure"]
    fb = {"local": {"up": 0, "down": 0}, "cloud": {"up": 0, "down": 0}}
    for e in events:
        if e.get("type") == "feedback" and e.get("routed"):
            side = "local" if str(e.get("model", "")).startswith("local:") else "cloud"
            fb[side]["up" if e.get("rating", 0) > 0 else "down"] += 1
    escalated_cost = sum(float(e.get("credits_est") or 0) for e in cloud_runs if e.get("ok"))
    models = {}
    for e in local_runs + cloud_runs:
        m = models.setdefault(e.get("model") or "?", {"calls": 0, "errors": 0, "ms": []})
        m["calls"] += 1
        m["errors"] += not e.get("ok", True)
        if e.get("ms") is not None:
            m["ms"].append(e["ms"])

    def lat(rows):
        values = [r["ms"] for r in rows if r.get("ms") is not None and r.get("ok", True)]
        return {"avg": round(sum(values) / len(values)) if values else None, "p50": _p(values, 0.5), "p95": _p(values, 0.95)}

    def success(provider):
        rows = [c for c in checks if c.get("provider") == provider and c.get("verifiable")]
        return {"checked": len(rows), "ok": sum(1 for c in rows if c.get("ok")),
                "rate": round(sum(1 for c in rows if c.get("ok")) / len(rows), 3) if rows else None}

    total = len(decisions)
    esc_from_local = [e for e in esc if str(e.get("from_model", "")).startswith("local:")]
    local_done = max(0, by_provider.get("local", 0) - len(esc_from_local))
    cloud_done = max(0, total - local_done - by_provider.get("none", 0))
    # 3단계: 프런티어가 받은 입력 토큰(추정)과 '모든 요청을 프런티어로' 보냈을 때(요청 입력 토큰의 합)를 비교한다.
    baseline_tokens = sum(int(e.get("est_tokens") or 0) for e in decisions if e.get("provider") != "none")
    ok_cloud = [e for e in cloud_runs if e.get("ok")]
    frontier_tokens = sum(int(e.get("est_tokens") or 0) for e in ok_cloud if (e.get("tier") or "frontier") == "frontier")
    light_tokens = sum(int(e.get("est_tokens") or 0) for e in ok_cloud if e.get("tier") == "light")
    consults = [e for e in events if e.get("type") == "consult"]
    cloud_credit_rows = [e for e in cloud_runs if e.get("credits_est") is not None and e.get("ok")]
    # 서버가 알려 준 실제 토큰(1.17: 사용량을 돌려준 호출만). 추정(est_tokens)과 따로 보인다.
    measured = {}
    for e in ok_cloud:
        if e.get("measured"):
            m = measured.setdefault(e.get("tier") or "frontier", {"calls": 0, **{k: 0 for k in USAGE_KEYS}})
            m["calls"] += 1
            for k in USAGE_KEYS:
                m[k] += int(e.get(k) or 0)
    return {
        "measured_tokens": measured,
        "days": days, "requests": total, "local": local_done, "cloud": cloud_done, "routed_local": by_provider.get("local", 0),
        "blocked": by_provider.get("none", 0), "light": by_provider.get("light", 0),
        "light_ratio": round(by_provider.get("light", 0) / total, 3) if total else None,
        "consults": len(consults),
        "consult_tokens_est": sum(int(e.get("consult_tokens_est") or 0) for e in consults),
        "consult_full_tokens_est": sum(int(e.get("full_tokens_est") or 0) for e in consults),
        "frontier_tokens_est": frontier_tokens if baseline_tokens else None, "light_tokens_est": light_tokens if baseline_tokens else None,
        "baseline_tokens_est": baseline_tokens or None,
        "frontier_token_saving_est": round(1 - frontier_tokens / baseline_tokens, 3) if baseline_tokens else None,
        "local_ratio": round(local_done / total, 3) if total else None,
        "cloud_ratio": round(cloud_done / total, 3) if total else None,
        "escalations": len(esc),
        "escalation_ratio": round(len(esc) / (by_provider["local"] + by_provider["light"]), 3)
        if by_provider.get("local") or by_provider.get("light") else None,
        "latency_local": lat(local_runs), "latency_cloud": lat(cloud_runs),
        "success_local": success("local"), "success_cloud": success("cloud"),
        "credits_per_cloud_request": round(sum(e["credits_est"] for e in cloud_credit_rows) / len(cloud_credit_rows), 1)
        if cloud_credit_rows else None,
        "credits_spent_est": round(escalated_cost, 1) if cloud_credit_rows else None,
        # Cloud만 썼다면 로컬로 처리한 요청에 들었을 크레딧(근거 있는 모델만, 추정). 로컬 하드웨어·전력 비용은 넣지 않는다.
        "saved_credits_est": round(max(0.0, saved), 1) if local_done and saved_unknown < by_provider.get("local", 0) else None,
        "saved_unknown": saved_unknown,
        "failures": {k: sum(1 for f in failures if f.get("kind") == k) for k in sorted({f.get("kind") for f in failures})},
        "feedback": fb,
        "models": [{"model": k, "calls": v["calls"], "errors": v["errors"],
                    "error_rate": round(v["errors"] / v["calls"], 3) if v["calls"] else 0,
                    "avg_ms": round(sum(v["ms"]) / len(v["ms"])) if v["ms"] else None, "p95_ms": _p(v["ms"], 0.95)}
                   for k, v in sorted(models.items(), key=lambda kv: -kv[1]["calls"])],
    }
