# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""POSCHAT — pywebview 데스크톱 앱 진입점.

화면은 web/ 아래의 HTML/CSS/JS이고, JS는 window.pywebview.api.<메서드>로 Bridge를 호출한다.
Python → JS 알림은 window.onBackendEvent(event)로 보낸다.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import urlparse

import webview

import adaptive_engine
import api
import attachments
import connectors
import documents
import mcp_client
import plugins
import po_note
import storage
import stt
import telemetry
import ui_events
import updates
from adaptive_api import AdaptiveApi
from browser_api import BrowserApi
from code_agent import CodeAgentApi
from code_api import CodeApi
from lab_api import LabApi
from paper_api import PaperApi
from ssh_api import SshApi
from workspace_api import WorkspaceApi
from agent import INIT_TASK, Agent, discover_skills, load_init, resource_dir
from api import DEFAULT_MODEL, MODELS, RESPONSES_MODELS, ApiError, ApiSettings
import version
from version import APP_VERSION

APP_TITLE = "POSCHAT"
UPDATE_INTERVAL = 6 * 3600  # 시작할 때 새 버전을 확인하는 최소 간격(초)
WINDOW_MODES = ("normal", "maximized", "fullscreen")  # 1.19 설정: 앱을 열 때의 창 크기
# 2.0: 처음에는 최대화로 연다. 1.19.1의 기본값(전체 화면)은 창의 제목 표시줄(최소화·최대화·닫기 버튼)까지 숨겨
# 창을 줄이거나 닫을 방법이 F11뿐이었다. 최대화는 화면을 채우면서 그 버튼을 그대로 둔다.
DEFAULT_WINDOW_MODE = "maximized"
UPDATE_EXIT_TIMEOUT = 15  # 업데이트하려고 창을 닫은 뒤 정리가 끝나지 않아도 이 시간(초)이 지나면 프로세스를 끝낸다
PO_RESERVES = (0, 10, 20, 30, 50)  # PO노트 크레딧 예산 보호: 이번 주 한도의 몇 %를 남겨 둘지(0은 끄기)

SKILL_TEMPLATE = """---
name: {name}
description: 이 스킬을 언제 쓰는지 한 줄로 설명하세요.
---

# {name}

## 절차
1. ...
2. ...

## 출력 형식
- ...
"""


MACRO_EXTS = {".xlsm"}   # 첨부를 눌러도 기본 앱으로 열지 않는다(인터넷 표시가 없어 Office 보호 보기가 걸리지 않는다)


def open_path(path):
    """파일이나 폴더를 운영체제의 기본 앱으로 연다(안드로이드는 android_main이 os.startfile을 바꿔 끼운다)."""
    if hasattr(os, "startfile"):
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def _extend_mac_path():
    """Finder에서 연 맥 앱은 PATH가 /usr/bin:/bin 정도뿐이라 npx·ai-memory 같은 외부 MCP 실행 도구를 못 찾는다."""
    if sys.platform != "darwin":
        return
    home = os.path.expanduser("~")
    extra = ["/opt/homebrew/bin", "/usr/local/bin", f"{home}/.local/bin", f"{home}/.cargo/bin"]
    current = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join(current + [d for d in extra if d not in current])


def _installed_package_licenses():
    """설치된 Python 패키지가 함께 싣는 라이선스 파일(dist-info)."""
    from importlib import metadata
    items, seen = [], set()
    for dist in metadata.distributions():
        name = dist.metadata.get("Name") or "?"
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        for f in dist.files or []:
            if f.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")) or "licenses" in f.parts[:-1]:
                try:
                    text = Path(f.locate()).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                items.append({"name": f"python/{name}-{dist.version}/{f.name}", "text": text[:200_000]})
    return sorted(items, key=lambda x: x["name"].lower())


class Bridge(WorkspaceApi, BrowserApi, PaperApi, CodeApi, CodeAgentApi, SshApi, LabApi, AdaptiveApi):
    """JS에서 호출하는 API. 밑줄로 시작하는 이름은 JS에 노출되지 않는다. '연결·도구' 창의 API는 WorkspaceApi,
    브라우저는 BrowserApi(1.13), 논문은 PaperApi(1.14), 코드 편집기는 CodeApi(1.15),
    Code 에이전트는 CodeAgentApi(1.16), 실험 기록은 LabApi(1.16), AI 실행 정책·로컬 AI는 AdaptiveApi(1.17),
    코드 화면의 원격(SSH) 작업 폴더는 SshApi(1.18)에 있다."""

    def __init__(self):
        storage.ensure_dirs()
        self._config = storage.load_config()
        storage.migrate_config_secrets(self._config)   # 1.18.9: 평문 키를 비밀 저장소로
        if self._config.get("window_mode") == "normal" and not self._config.get("window_mode_191"):
            # 1.19.1: 기본값이 전체 화면이 됐다. 1.19.0은 설정을 저장할 때마다 고르지 않은 '기본 창'도 함께 저장했으므로
            # 그 값은 한 번 지워 새 기본값을 따르게 한다(최대화·전체 화면을 고른 값은 그대로 둔다)
            self._config.pop("window_mode", None)
            self._config["window_mode_191"] = True
            storage.save_config(self._config)
        if self._config.get("window_mode") == "fullscreen" and not self._config.get("window_mode_200"):
            # 2.0: 1.19.x는 설정을 저장할 때마다 고르지 않은 창 크기(1.19.1 기본값 '전체 화면')도 함께 저장했다.
            # 직접 고른 값과 구별할 수 없으므로 한 번 지워 새 기본값(최대화, 제목 표시줄 있음)을 따르게 한다
            self._config.pop("window_mode", None)
            self._config["window_mode_200"] = True
            storage.save_config(self._config)
        if "github_update_token" in self._config:  # 1.8.0의 업데이트 확인용 GitHub 토큰은 더 쓰지 않는다
            self._config.pop("github_update_token", None)
            storage.save_config(self._config)
        self._lock = threading.RLock()
        self._window = None
        # 1.15(B1): 화면 이벤트는 전용 스레드가 순서대로 보낸다. _push는 막지 않으므로 UI 스레드에서 불러도 된다.
        self._events = ui_events.EventPump(self._send_event)
        self._busy = False
        self._browser_owner = None  # 화면 하나를 여러 에이전트가 동시에 조작하지 않게 한다
        self._chat_runs = {}  # 대화별 실행·취소·이번 실행 허용
        self._run_id = 0
        self._cancel = threading.Event()
        self._pending = {}            # confirm id -> [Event, decision]
        self._session_allow = set()   # "edit" / "run" / "write" — 이번 실행(메시지 하나) 동안 항상 허용
        self._mcp = mcp_client.Manager()
        self._credit = None           # 응답 헤더로 받은 최근 크레딧 {"usage", "limit", "interval"}
        self._po_session = None       # 녹음 중인 stt.LiveSession
        self._po_note = None          # 녹음 중인 노트 ID
        self._po_stopping = False
        self._po_download = None      # 내려받는 중인 모델 {"key", "done", "total"}
        self._po_cancel_download = threading.Event()
        self._po_generating = None    # 노트를 만드는 중인 노트 ID
        self._po_label = ""           # 녹음 중인 인식 방식 이름
        self._updating = False        # 업데이트 파일을 내려받는 중
        api.on_usage = storage.record_usage
        api.on_credit = self._on_credit
        # 관측(사용량·진단 탭): 내용 없이 메타데이터만 이 기기에 기록한다. Langfuse 내보내기는 켰을 때만.
        telemetry.config_getter = lambda: self._config
        api.on_trace = telemetry.on_llm_call
        api.cloud_guard = self._cloud_guard  # 1.17: Local Only 정책이면 Cloud 모델 호출을 막는다
        self._local_rt = adaptive_engine.LocalRuntime(lambda: self._config)
        connectors.on_event = telemetry.on_tool_call
        telemetry.prune()
        storage.cleanup_staged()
        connectors.prune_audit()
        self._migrate_config()
        self._sync_schedule(10)  # 동기화를 켰으면 시작하고 조금 뒤 한 번
        self._export_schedule(60)

    def _migrate_config(self):
        """1.9: a1/gpt가 서버 오류만 돌려주므로 OpenAI 호환 API(POSTECH 주소 내장)로 한 번 옮긴다. 잘못된 Claude 모델 ID도 고친다."""
        changed = False
        if not self._config.get("migrated_1_9"):
            if self._config.get("api_mode", "a1") == "a1":
                self._config["api_mode"] = api.DEFAULT_MODE
            self._config["migrated_1_9"] = True
            changed = True
        model = api.normalize_model(self._config.get("model"))
        if self._config.get("model") and model != self._config["model"]:
            self._config["model"] = model
            changed = True
        if not self._config.get("migrated_1_10"):
            # 1.10은 기존 파일의 형식을 바꾸지 않지만, 처음 실행할 때 1.9의 사용자 데이터를 한 번 백업해 둔다(되돌리기용).
            backup = storage.backup_user_data("before-1.10")
            self._config["migrated_1_10"] = True
            self._config["backup_1_10"] = str(backup) if backup else ""
            changed = True
        if changed:
            storage.save_config(self._config)

    def _mode(self):
        mode = self._config.get("api_mode", api.DEFAULT_MODE)
        return mode if mode in api.MODES else api.DEFAULT_MODE

    def _on_credit(self, info):
        self._credit = info
        self._push({"type": "credit", "credit": info})

    # ---- 내부 도우미 ----

    def _push(self, event):
        """화면에 이벤트를 보낸다. 큐에 넣고 바로 돌아온다(웹페이지 뷰의 네이티브 처리기처럼 UI 스레드에서 불러도
        멈추지 않는다 — B1). 실제 evaluate_js는 ui_events.EventPump의 스레드가 부른다."""
        if getattr(self, "_window", None) is None:
            return
        self._events.push(event)

    def _send_event(self, event):
        window = getattr(self, "_window", None)
        if window is not None:
            window.evaluate_js(f"window.onBackendEvent({json.dumps(event, ensure_ascii=False)})")

    def _open_url(self, url):
        """http(s) 주소나 있는 로컬 폴더만 연다. Windows os.startfile·macOS open·안드로이드 host.openPath 모두 https 주소를
        브라우저로 연다. 그 밖의 scheme(file:·ms-*: 등)이나 네트워크 공유(\\\\host)는 프로그램을 실행할 수 있어 열지 않는다."""
        text = str(url or "").strip()
        parts = urlparse(text)
        if parts.scheme in ("http", "https") and parts.netloc:
            open_path(text)
        elif not text.startswith(("\\\\", "//")) and os.path.isdir(text):
            open_path(text)

    def _workspace(self):
        ws = self._config.get("workspace", "")
        return ws if ws and os.path.isdir(ws) else ""

    def _api_key(self):
        """지금 API 방식이 쓰는 키. 일반 AI 모델(Claude)이면 Claude(Anthropic) 키, 일반 AI 모델(GPT)이면 OpenAI 키,
        아니면(기본) POSTECH GenAI 키. 대화·에이전트·PO노트 노트 만들기·요약·평가 같은 모델 호출은 모두 이 키를 쓴다."""
        mode = self._mode()
        if mode == api.ANTHROPIC_MODE:
            return self._anthropic_key()
        if mode == api.OPENAI_MODE:
            return self._openai_key()
        return self._postech_key()

    def _postech_key(self):
        """POSTECH GenAI 키. 크레딧 확인과 PO노트의 서버 음성 인식은 API 방식과 관계없이 이 키를 쓴다."""
        return self._config.get("api_key") or os.environ.get("POSTECH_GENAI_API_KEY", "")

    def _anthropic_key(self):
        return self._config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")

    def _openai_key(self):
        return self._config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")

    def _missing_key_error(self):
        if self._mode() == api.ANTHROPIC_MODE:
            return "Claude API 키가 없습니다. 설정 → API 방식 '일반 AI 모델 (Claude)'에서 키를 입력하세요."
        if self._mode() == api.OPENAI_MODE:
            return "OpenAI API 키가 없습니다. 설정 → API 방식 '일반 AI 모델 (GPT)'에서 키를 입력하세요."
        return "API 키가 없습니다. 설정에서 입력하세요."

    def _add(self, thread_id, role, content, **extra):
        with self._lock:
            thread = storage.load_thread(thread_id)
            if thread is None:  # 작업 중 삭제됨
                return None
            msg = storage.make_message(role, content, **extra)
            thread["messages"].append(msg)
            storage.save_thread(thread)
        self._push({"type": "message", "thread_id": thread_id, "message": msg})
        return msg

    def _workspace_info(self):
        ws = self._workspace()
        return {
            "path": ws,
            "name": os.path.basename(ws.rstrip("\\/")) if ws else "",
            "has_init": bool(ws) and load_init(ws) is not None,
        }

    def _skills(self):
        # 1.19.1: 플러그인 스킬은 플러그인 화면처럼 한국어 설명(description_ko)을 함께 준다. 모델에는 원문이 간다
        return [{"name": s.name, "description": s.description, "source": s.source, "path": str(s.path),
                 "description_ko": plugins.skill_ko(s.name) if s.source.startswith("플러그인 ") else ""}
                for s in discover_skills(self._workspace()).values()]

    # ---- 상태 ----

    def get_state(self):
        key_source = "settings" if self._config.get("api_key") else ("env" if os.environ.get("POSTECH_GENAI_API_KEY") else None)
        anthropic_source = "settings" if self._config.get("anthropic_api_key") else (
            "env" if os.environ.get("ANTHROPIC_API_KEY") else None)
        openai_source = "settings" if self._config.get("openai_api_key") else ("env" if os.environ.get("OPENAI_API_KEY") else None)
        return {
            "threads": storage.list_threads(),
            "workspace": self._workspace_info(),
            "skills": self._skills(),
            "busy": self._busy,
            "running_threads": list(self._chat_runs.copy()),
            "config": {
                "agent_mode": self._config.get("agent_mode", True),
                "history_messages": self._config.get("history_messages", 20),
                "max_steps": self._config.get("max_steps", 25),
                "permission": self._config.get("permission", "ask"),
                "share_threads": self._config.get("share_threads", True),
                "key_source": key_source,
                "anthropic_key_source": anthropic_source,
                "openai_key_source": openai_source,
                "has_key": bool(self._api_key()),
                "api_mode": self._mode(),
                "responses_url": self._config.get("responses_url", ""),
                "chat_completions_url": self._config.get("chat_completions_url", ""),
                "model": self._config.get("model", DEFAULT_MODEL),
                "anthropic_model": self._config.get("anthropic_model", api.DEFAULT_ANTHROPIC_MODEL),
                "openai_model": self._config.get("openai_model", api.DEFAULT_OPENAI_MODEL),
                "stream": self._config.get("stream", True),
                "update_check": self._config.get("update_check", True),
                "developer_mode": bool(self._config.get("developer_mode")),
                "window_mode": self._window_mode(),
                "adaptive": self._adaptive_public(),
                "notion_source": "settings" if self._config.get("notion_token") else (
                    "env" if os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY") else None),
                "firecrawl_source": "settings" if self._config.get("firecrawl_key") else (
                    "env" if os.environ.get("FIRECRAWL_API_KEY") else None),
                "plms_username": self._plms_saved_username(),  # 1.18.5 저장된 PLMS 아이디(비밀번호는 화면으로 보내지 않는다)
            },
            "data_dir": str(storage.APP_DIR),
            "version": APP_VERSION, "distribution": version.distribution(),
            "models": [{"id": m, "label": label} for m, label in self._models("chat_completions")],
            "responses_models": [{"id": m, "label": label} for m, label in RESPONSES_MODELS],
            "models_source": "server" if self._config.get("server_models") else "builtin",
            "anthropic_models": [{"id": m, "label": label} for m, label in self._models(api.ANTHROPIC_MODE)],
            "anthropic_models_source": "server" if self._config.get("anthropic_server_models") else "builtin",
            "openai_models": [{"id": m, "label": label} for m, label in self._models(api.OPENAI_MODE)],
            "openai_models_source": "server" if self._config.get("openai_server_models") else "builtin",
            "memory": storage.load_memory(),
            "attach_limits": {"max_bytes": attachments.MAX_BYTES, "max_files": attachments.MAX_FILES},
            "default_chat_completions_url": api.DEFAULT_CHAT_COMPLETIONS_URL,
            "credit": self._credit,
            "po_available": stt.available()[0],
        }

    # ---- 스레드 ----

    def list_threads(self):
        return storage.list_threads()

    def load_thread(self, thread_id):
        with self._lock:
            thread = storage.load_thread(thread_id)
            if thread is not None and api.normalize_model(thread.get("model")) != thread.get("model"):
                thread["model"] = api.normalize_model(thread.get("model"))
                storage.save_thread(thread, update_timestamp=False)
            if thread is not None and thread.get("model") not in self._model_ids(self._mode()) \
                    and not self._routed_model_ok(thread.get("model")):
                thread["model"] = self._default_model()
                storage.save_thread(thread, update_timestamp=False)
            return thread

    def new_thread(self):
        with self._lock:
            thread = storage.new_thread()
            # 1.17: 자동 선택을 켰으면 새 대화는 '자동'으로 시작한다(대화 위에서 직접 고른 모델로 언제든 바꿀 수 있다)
            thread["model"] = "auto" if adaptive_engine.active(self._config) else self._default_model()
            storage.save_thread(thread)
            return thread

    def _models(self, mode):
        """mode에서 고를 수 있는 (모델 ID, 이름). OpenAI 호환 API는 서버에서 받아 둔 목록을 먼저 쓴다."""
        if mode == "responses":
            return RESPONSES_MODELS
        if mode == api.ANTHROPIC_MODE:
            server = [m for m in self._config.get("anthropic_server_models") or [] if isinstance(m, str) and m]
            return [(m, api.model_label(m)) for m in server] if server else api.ANTHROPIC_MODELS
        if mode == api.OPENAI_MODE:
            server = [m for m in self._config.get("openai_server_models") or [] if isinstance(m, str) and m]
            return [(m, api.model_label(m)) for m in server] if server else api.OPENAI_MODELS
        server = [m for m in self._config.get("server_models") or [] if isinstance(m, str) and m]
        return [(m, api.model_label(m)) for m in server] if server else MODELS

    def _model_ids(self, mode):
        return {model_id for model_id, _ in self._models(mode)}

    def _default_model(self):
        mode = self._mode()
        allowed = self._models(mode)
        configured = self._config.get(api.model_config_key(mode)) or api.default_model(mode)
        return configured if configured in {model_id for model_id, _ in allowed} else allowed[0][0]

    def rename_thread(self, thread_id, title):
        title = (title or "").strip()
        with self._lock:
            thread = storage.load_thread(thread_id)
            if thread and title:
                thread["title"] = title[:80]
                storage.save_thread(thread)
        return storage.list_threads()

    def delete_thread(self, thread_id):
        with self._lock:
            self.stop(thread_id)
            storage.delete_thread(thread_id)
        return storage.list_threads()

    def set_thread_model(self, thread_id, model):
        if model not in self._model_ids(self._mode()) and not self._routed_model_ok(model):
            return {"ok": False, "error": "지원하지 않는 모델입니다."}
        with self._lock:
            thread = storage.load_thread(thread_id)
            if thread is None:
                return {"ok": False, "error": "대화를 찾을 수 없습니다."}
            thread["model"] = model
            storage.save_thread(thread)
        return thread

    # ---- 설정 ----

    @staticmethod
    def _plms_saved_username():
        try:
            import plms
            return plms.saved_username()
        except Exception:
            return ""

    @staticmethod
    def _save_plms_account(settings):
        """1.18.5 설정의 PLMS 계정(OS 보안 저장소). 오류 글을 돌려주고, 잘 됐으면 None."""
        import plms
        try:
            if settings.get("clear_plms"):
                plms.clear_credentials()
                return None
            username = str(settings.get("plms_username") or "").strip()
            password = str(settings.get("plms_password") or "")
            if not username and not password:
                return None
            if username and not password and username == plms.saved_username():
                return None  # 아이디만 그대로: 저장된 비밀번호를 유지한다
            plms.save_credentials(username, password)
        except plms.PlmsError as e:
            return str(e)
        return None

    def plms_save_account(self, username, password):
        """1.19 PLMS 창의 '설정에 계정 저장': 설정 창의 PLMS 계정 칸과 같은 곳(OS 보안 저장소)에 저장하고 연결을 켠다."""
        username, password = str(username or "").strip(), str(password or "")
        if not username or not password:
            return {"ok": False, "error": "POSTECH 아이디와 비밀번호를 모두 입력하세요."}
        error = self._save_plms_account({"plms_username": username, "plms_password": password})
        if error:
            return {"ok": False, "error": error}
        with self._lock:
            self._config["plms_enabled"] = True
            storage.save_config(self._config)
        return {"ok": True, "plms_username": self._plms_saved_username()}

    def save_settings(self, settings):
        mode = settings.get("api_mode", self._mode())
        url = api.endpoint_url(settings.get("responses_url", self._config.get("responses_url", "")),
                               api.RESPONSES_PATH)
        compatible_url = api.endpoint_url(settings.get("chat_completions_url",
                                                       self._config.get("chat_completions_url", "")),
                                          api.CHAT_COMPLETIONS_PATH)
        if mode == "responses" and not self._valid_https_url(url):
            return {"ok": False, "error": "Responses API를 선택했다면 올바른 HTTPS 주소를 입력해야 합니다."}
        if mode == "chat_completions" and compatible_url and not self._valid_https_url(compatible_url):
            return {"ok": False, "error": "OpenAI 호환 API를 선택했다면 올바른 HTTPS Chat Completions 주소를 입력해야 합니다."}
        plms_error = self._save_plms_account(settings)
        if plms_error:
            return {"ok": False, "error": plms_error}
        with self._lock:
            before = self._sync_settings()
            if str(settings.get("plms_username") or "").strip() and settings.get("plms_password"):
                self._config["plms_enabled"] = True  # 1.18.6 계정을 저장하면 PLMS 연결도 켠다(에이전트가 바로 조회)
            if settings.get("api_key"):
                self._config["api_key"] = settings["api_key"].strip()
            if settings.get("clear_key"):
                self._config["api_key"] = ""
            if settings.get("anthropic_api_key"):
                self._config["anthropic_api_key"] = settings["anthropic_api_key"].strip()
            if settings.get("clear_anthropic_key"):
                self._config["anthropic_api_key"] = ""
            if settings.get("openai_api_key"):
                self._config["openai_api_key"] = settings["openai_api_key"].strip()
            if settings.get("clear_openai_key"):
                self._config["openai_api_key"] = ""
            if settings.get("notion_token"):
                self._config["notion_token"] = settings["notion_token"].strip()
            if settings.get("clear_notion"):
                self._config["notion_token"] = ""
            if settings.get("firecrawl_key"):
                self._config["firecrawl_key"] = settings["firecrawl_key"].strip()
            if settings.get("clear_firecrawl"):
                self._config["firecrawl_key"] = ""
            for key, lo, hi in (("history_messages", 0, 200), ("max_steps", 1, 100)):
                if key in settings:
                    try:
                        self._config[key] = max(lo, min(hi, int(settings[key])))
                    except (TypeError, ValueError):
                        pass
            if "share_threads" in settings:
                self._config["share_threads"] = bool(settings["share_threads"])
            if settings.get("permission") in ("ask", "auto_edit", "auto_all"):
                self._config["permission"] = settings["permission"]
            if settings.get("api_mode") in api.MODES:
                self._config["api_mode"] = settings["api_mode"]
            if "responses_url" in settings:
                self._config["responses_url"] = url
            if "chat_completions_url" in settings:
                if compatible_url != self._config.get("chat_completions_url", ""):
                    self._config.pop("server_models", None)  # 다른 서버의 목록은 버린다
                self._config["chat_completions_url"] = compatible_url
            # 설정 창에서 '모델 목록 불러오기'로 받은 목록은 저장을 눌러야 반영한다(취소하면 버린다).
            server_models = self._clean_models(settings.get("server_models"))
            if server_models:
                self._config["server_models"] = server_models
            anthropic_models = self._clean_models(settings.get("anthropic_server_models"))
            if anthropic_models:
                self._config["anthropic_server_models"] = anthropic_models
            openai_models = self._clean_models(settings.get("openai_server_models"))
            if openai_models:
                self._config["openai_server_models"] = openai_models
            if settings.get("model") in self._model_ids(self._mode()):
                self._config[api.model_config_key(self._mode())] = settings["model"]
            if "stream" in settings:
                self._config["stream"] = bool(settings["stream"])
            if "update_check" in settings:
                self._config["update_check"] = bool(settings["update_check"])
            if "developer_mode" in settings:  # 1.17: 라우팅·토큰·손익분기의 원자료를 화면에 보인다
                self._config["developer_mode"] = bool(settings["developer_mode"])
            mode = settings.get("window_mode")
            if mode in WINDOW_MODES and mode != self._window_mode():  # 1.19: 다음에 앱을 열 때의 창 크기
                # 2.0: 바꾼 때만 저장한다. 설정 창은 이 칸을 늘 함께 보내므로, 고르지 않은 값까지 적어 두면
                # 기본값을 바꿔도 따라가지 않는다(1.19.x에서 '전체 화면'이 그렇게 남았다)
                self._config["window_mode"] = mode
                self._config["window_mode_191"] = self._config["window_mode_200"] = True
            self._stamp_settings(before)
            storage.save_config(self._config)
        return self.get_state()

    def get_usage(self):
        return storage.usage_summary()

    @staticmethod
    def _clean_models(models):
        if not isinstance(models, list):
            return []
        out = []
        for m in models:
            m = m.strip() if isinstance(m, str) else ""
            if m and m not in out:
                out.append(m)
        return out[:500]

    def refresh_models(self, settings=None):
        """OpenAI 호환 API의 모델 목록을 서버에서 받아 돌려준다. 설정 창의 '모델 목록 불러오기'.

        여기서는 저장하지 않는다. 설정 창이 저장할 때 server_models로 함께 보낸다.
        """
        settings = settings or {}
        if settings.get("api_mode") == api.ANTHROPIC_MODE:
            key = str(settings.get("anthropic_api_key") or "").strip() or self._anthropic_key()
            if not key:
                return {"ok": False, "error": "Claude API 키를 먼저 입력하세요."}
            try:
                ids = api.list_anthropic_models(key)
            except ApiError as e:
                return {"ok": False, "error": f"모델 목록을 불러오지 못했습니다: {e}"}
            return {"ok": True, "models": [{"id": m, "label": api.model_label(m)} for m in ids]}
        if settings.get("api_mode") == api.OPENAI_MODE:
            key = str(settings.get("openai_api_key") or "").strip() or self._openai_key()
            if not key:
                return {"ok": False, "error": "OpenAI API 키를 먼저 입력하세요."}
            try:
                ids = api.list_openai_models(key)
            except ApiError as e:
                return {"ok": False, "error": f"모델 목록을 불러오지 못했습니다: {e}"}
            return {"ok": True, "models": [{"id": m, "label": api.model_label(m)} for m in ids]}
        key = str(settings.get("api_key") or "").strip() or self._postech_key()
        if not key:
            return {"ok": False, "error": "API 키를 먼저 입력하세요."}
        url = api.endpoint_url(settings.get("chat_completions_url", self._config.get("chat_completions_url", "")),
                               api.CHAT_COMPLETIONS_PATH) or api.DEFAULT_CHAT_COMPLETIONS_URL
        if not self._valid_https_url(url):
            return {"ok": False, "error": "올바른 HTTPS Chat Completions 주소를 입력하세요."}
        try:
            ids = api.list_models(key, url)
        except ApiError as e:
            return {"ok": False, "error": f"모델 목록을 불러오지 못했습니다: {e}"}
        return {"ok": True, "chat_completions_url": url,
                "models": [{"id": m, "label": api.model_label(m)} for m in ids]}

    @staticmethod
    def _valid_https_url(value):
        try:
            parsed = urlparse(value)
            return (parsed.scheme == "https" and bool(parsed.hostname) and bool(parsed.path.strip("/"))
                    and not parsed.username and not parsed.password and parsed.port != 0)
        except ValueError:
            return False

    def set_agent_mode(self, enabled):
        with self._lock:
            self._config["agent_mode"] = bool(enabled)
            storage.save_config(self._config)

    def choose_workspace(self):
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG, directory=self._workspace() or os.path.expanduser("~"))
        if result:
            path = result[0] if isinstance(result, (list, tuple)) else result
            with self._lock:
                self._config["workspace"] = os.path.normpath(path)
                storage.save_config(self._config)
        return {"workspace": self._workspace_info(), "skills": self._skills()}

    def _window_mode(self):
        mode = self._config.get("window_mode")
        return mode if mode in WINDOW_MODES else DEFAULT_WINDOW_MODE

    def _track_window(self, window, mode):
        """2.0: 창이 최대화돼 있는지와 전체 화면인지를 기억한다(F11로 전체 화면을 끌 때 돌아갈 모양)."""
        self._window = window
        self._fullscreen_lock = threading.Lock()  # F11 연타 순서만 지킨다(_lock은 잡지 않는다: UI 스레드 Invoke를 기다리므로)
        self._fullscreen = mode == "fullscreen"
        self._maximized = mode == "maximized"
        self._maximized_before_fullscreen = mode != "normal"  # 전체 화면으로 시작했으면 끌 때 최대화로 돌아간다

        def on_maximized():
            self._maximized = True

        def on_restored():
            self._maximized = False
        try:
            window.events.maximized += on_maximized
            window.events.restored += on_restored
        except Exception:
            pass  # 이벤트가 없는 pywebview: 시작할 때의 모양만 기억한다

    def toggle_fullscreen(self):
        """F11: 전체 화면을 켜고 끈다(1.19). 설정의 '시작할 때 창 크기'는 바꾸지 않는다.
        2.0: 전체 화면에서는 제목 표시줄(최소화·최대화·닫기)이 없으므로, 끌 때 최대화돼 있던 창은 최대화로 되돌린다
        (pywebview는 전체 화면을 끄면 늘 '기본 창'으로 돌아가 화면 크기만 한 테두리 없는 창처럼 보였다)."""
        window = getattr(self, "_window", None)
        lock = getattr(self, "_fullscreen_lock", None)
        if window is None or lock is None:
            return {"ok": True}
        with lock:
            if not getattr(self, "_fullscreen", False):
                self._maximized_before_fullscreen = bool(getattr(self, "_maximized", False))
                window.toggle_fullscreen()
                self._fullscreen = True
            else:
                window.toggle_fullscreen()
                self._fullscreen = False
                if getattr(self, "_maximized_before_fullscreen", False):
                    try:
                        window.maximize()
                    except Exception:
                        pass
        return {"ok": True, "fullscreen": self._fullscreen}

    def open_folder(self, which):
        targets = {
            "skills": storage.USER_SKILLS_DIR,
            "data": storage.APP_DIR,
            "workspace": self._workspace() or None,
        }
        target = targets.get(which)
        if target and os.path.isdir(target):
            open_path(target)

    def create_skill(self, name):
        name = "-".join((name or "").strip().split())
        if not name or any(c in name for c in '\\/:*?"<>|'):
            return {"ok": False, "error": "스킬 이름에 쓸 수 없는 문자가 있습니다."}
        path = storage.USER_SKILLS_DIR / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(SKILL_TEMPLATE.format(name=name), encoding="utf-8")
        open_path(path)
        return {"ok": True, "skills": self._skills()}

    # ---- 메모리 ----

    def list_memory(self):
        return storage.load_memory()

    def add_memory(self, text):
        with self._lock:
            item = storage.add_memory(text)
        return {"ok": item is not None, "memory": storage.load_memory()}

    def delete_memory(self, memory_id):
        with self._lock:
            storage.delete_memory(memory_id)
        return storage.load_memory()

    def get_skills(self):
        return self._skills()

    # ---- Markdown 노트: memory.md(메모리), USER.md(사용자 정보) ----

    def _note(self, kind):
        if kind == "memory":
            return storage.MEMORY_PATH, storage.read_memory_md, storage.save_memory_md
        if kind == "profile":
            return storage.PROFILE_PATH, storage.read_profile, storage.save_profile
        raise ValueError(f"알 수 없는 노트: {kind}")

    def read_note(self, kind):
        path, read, _ = self._note(kind)
        return {"path": str(path), "text": read(), "exists": path.exists()}

    def save_note(self, kind, text):
        _, _, save = self._note(kind)
        with self._lock:
            save(text)
        return {"ok": True, "memory": storage.load_memory()}

    def open_note(self, kind):
        path, read, save = self._note(kind)
        with self._lock:
            if not path.exists():
                save(read())
        open_path(path)

    # ---- 첨부 파일 ----

    def upload_attachment(self, attach_id, name, offset, data_b64, last):
        """화면이 파일을 조각으로 나눠 보낸다. 마지막 조각이면 첨부 정보를 돌려준다."""
        try:
            item = attachments.upload_chunk(attach_id, name, int(offset), data_b64, bool(last))
        except (attachments.AttachmentError, ValueError, OSError) as e:
            return {"ok": False, "error": str(e)}
        return {"ok": True, "attachment": item}

    def discard_attachment(self, attach_id):
        """보내기 전에 뺀 첨부 파일을 지운다(이미 메시지에 붙은 파일은 지우지 않는다)."""
        try:
            if (storage.attachment_dir(attach_id) / storage.STAGED_MARK).exists():
                storage.delete_attachment(attach_id)
        except ValueError:
            pass

    def attachment_preview(self, attach_id):
        try:
            return attachments.preview(attach_id)
        except (ValueError, OSError):
            return None

    def open_attachment(self, attach_id):
        """이미지·문서만 운영체제의 기본 앱으로 연다. 텍스트로 받은 파일(.bat·.vbs·.js·.hta·.html 등)은
        기본 앱으로 열면 실행될 수 있으므로 열지 않고 내용을 돌려준다(화면이 앱 안에서 보여 준다)."""
        path = storage.attachment_file(attach_id)
        if not path:
            return None
        suffix = path.suffix.lower()
        if suffix in attachments.IMAGE_TYPES or (suffix in documents.DOCUMENT_EXTS and suffix not in MACRO_EXTS):
            open_path(path)
            return None
        if suffix in documents.DOCUMENT_EXTS:   # 매크로가 든 문서: 실행하지 않고 읽은 글만 보여 준다
            try:
                text = documents.extract_text(path)
            except Exception:
                text = "(내용을 읽지 못했습니다)"
            return {"name": path.name, "text": "매크로가 들 수 있는 파일이라 앱에서 열지 않고 내용만 보여 줍니다.\n\n"
                    + text[:512 * 1024], "truncated": len(text) > 512 * 1024}
        limit = 512 * 1024
        with open(path, "rb") as f:
            data = f.read(limit + 1)
        return {"name": path.name, "text": data[:limit].decode("utf-8", "replace"), "truncated": len(data) > limit}

    # ---- MCP ----

    def get_mcp(self):
        status = self._mcp.status(self._config, self._workspace())
        policies = self._config.get("mcp_policy") or {}
        for server in status["servers"]:
            server["policy"] = (policies.get(server["name"]) or {}).get("mode", "")
        return status

    def connect_mcp(self):
        """켜진 MCP 서버를 지금 연결해 본다(MCP 창의 '연결' 버튼)."""
        self._mcp.ensure(self._config, self._workspace())
        return self.get_mcp()

    def set_mcp_enabled(self, name, enabled):
        name = str(name)
        with self._lock:
            # 추천 서버는 기본이 꺼짐이라 켠 것을, 나머지는 기본이 켜짐이라 끈 것을 기록한다
            external, _ = mcp_client.load_external()
            key, on = ("mcp_enabled", enabled) if name in mcp_client.preset_servers() and name not in external else ("mcp_disabled", not enabled)
            names = set(self._config.get(key, []))
            (names.add if on else names.discard)(name)
            self._config[key] = sorted(names)
            other = "mcp_disabled" if key == "mcp_enabled" else "mcp_enabled"
            self._config[other] = [n for n in self._config.get(other, []) if n != name]
            storage.save_config(self._config)
        return self.get_mcp()

    def open_mcp_config(self):
        open_path(mcp_client.ensure_config_file())

    # ---- 업데이트 ----

    def check_for_updates(self, manual=False):
        """업데이트 서버의 최신 버전. 시작할 때(manual=False)는 설정을 따르고 6시간에 한 번만, 건너뛴 버전은 알리지 않는다."""
        if not manual and (not self._config.get("update_check", True)
                           or time.time() - self._config.get("update_checked_at", 0) < UPDATE_INTERVAL):
            return {"available": False, "skipped": True}
        try:
            result = updates.check(APP_VERSION)
        except updates.UpdateError as e:
            return {"available": False, "error": str(e)}
        with self._lock:
            self._config["update_checked_at"] = time.time()
            storage.save_config(self._config)
        if not manual and result["version"] == self._config.get("update_skip"):
            result["available"] = False
        result["can_install"] = bool(result["asset"]) and self._can_self_update()
        result["current"] = APP_VERSION
        result["store"] = version.distribution() == "store"   # Store판: Store에서 업데이트하도록 안내만 한다
        return result

    @staticmethod
    def _can_self_update():
        if version.distribution() == "store":
            return False  # Store가 심사한 설치 파일만 설치되도록 스스로 받지 않는다(Store 정책 10.2.9)
        platform = updates.current_platform()
        if platform == "windows":
            return bool(getattr(sys, "frozen", False))  # 소스로 실행 중이면 설치 프로그램으로 바꿀 것이 없다
        return platform in ("macos", "android")

    def skip_update(self, version):
        with self._lock:
            self._config["update_skip"] = str(version)
            storage.save_config(self._config)

    def license_info(self):
        """설정의 라이선스 정보: 라이선스 전문, 제3자 고지, 이 버전에 대응하는 소스코드 주소."""
        root = resource_dir()

        def read(path):
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""

        third = [{"name": "THIRD_PARTY_NOTICES.md", "text": read(root / "THIRD_PARTY_NOTICES.md")}]
        licenses = root / "licenses"  # 화면 라이브러리 원문 + 데스크톱 빌드가 넣은 python/<패키지>/
        third += [{"name": f.relative_to(licenses).as_posix(), "text": read(f)}
                  for f in sorted(licenses.rglob("*")) if f.is_file()]
        if not (licenses / "python").is_dir():
            third += _installed_package_licenses()  # 안드로이드(Chaquopy)·소스 실행: 설치된 패키지 정보에서 읽는다
        tag = f"v{APP_VERSION}"
        return {
            "name": "POSCHAT", "version": APP_VERSION,
            "copyright": "Copyright © 2026 Beomjoon Kim",
            "license": "GNU Affero General Public License v3.0 only", "spdx": "AGPL-3.0-only",
            "license_text": read(root / "LICENSE"), "third_party": third,
            # 이 앱 버전과 같은 커밋(릴리스 태그)의 소스. Releases가 같은 태그로 만든 소스 아카이브도 함께 준다
            "source_url": f"https://github.com/{updates.REPOSITORY}/tree/{tag}",
            "source_archive": f"https://github.com/{updates.REPOSITORY}/archive/refs/tags/{tag}.zip",
        }

    def open_release_page(self):
        import webbrowser
        webbrowser.open(updates.RELEASES_PAGE)

    def open_store_updates(self):
        """Store판: Microsoft Store(제품 페이지 또는 다운로드 및 업데이트)를 연다."""
        try:
            open_path(updates.store_url())
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "error": f"Microsoft Store를 열지 못했습니다: {e}"}

    def download_update(self):
        """새 버전을 내려받아 설치를 시작한다. 진행은 {"type": "update"} 이벤트로 알린다."""
        if self._updating:
            return {"ok": False, "error": "이미 업데이트를 내려받고 있습니다."}
        if not self._can_self_update():
            return {"ok": False, "error": "이 실행 방식에서는 자동으로 설치할 수 없습니다. Releases 페이지에서 받으세요."}
        self._updating = True
        threading.Thread(target=self._update_work, daemon=True).start()
        return {"ok": True}

    def _update_work(self):
        last = [0.0]

        def progress(done, total):
            if time.monotonic() - last[0] >= 0.25 or done == total:
                last[0] = time.monotonic()
                self._push({"type": "update", "kind": "progress", "done": done, "total": total})

        try:
            path, version = updates.download(APP_VERSION, storage.APP_DIR / "updates", on_progress=progress)
            platform = updates.current_platform()
            if platform == "windows":
                # 설치 프로그램은 앱이 완전히 닫힐 때까지 기다렸다가 설치한다. 같은 폴더에 설치하도록 열고 앱을 닫는다.
                install_dir = Path(sys.executable).resolve().parent
                subprocess.Popen([str(path), f"--dir={install_dir}", "--update"], cwd=str(path.parent))
                self._push({"type": "update", "kind": "installing", "version": version,
                            "message": "설치 프로그램을 열었습니다. 앱이 닫히면 설치 프로그램에서 '설치'를 누르세요."})
                threading.Timer(2.0, self._close_for_update).start()
            else:
                open_path(path)
                message = ("Android 설치 화면에서 업데이트를 승인하세요." if platform == "android" else
                           "디스크 이미지를 열었습니다. 앱을 끝낸 뒤 POSCHAT을 응용 프로그램 폴더로 끌어다 놓아 바꾸세요.")
                self._push({"type": "update", "kind": "opened", "version": version, "message": message})
        except (updates.UpdateError, OSError) as e:
            self._push({"type": "update", "kind": "error", "error": str(e)})
        finally:
            self._updating = False

    def _close_for_update(self):
        """설치 프로그램이 기다리지 않도록 프로세스를 확실히 끝낸다.

        창을 닫은 뒤 run_app이 녹음 저장·MCP 서버 정리를 마치면 바로 종료하고(남은 작업 스레드를 기다리지 않는다),
        정리가 멈춰도 UPDATE_EXIT_TIMEOUT초 뒤에는 강제로 끝낸다.
        """
        self._exit_for_update = True
        timer = threading.Timer(UPDATE_EXIT_TIMEOUT, os._exit, args=(0,))
        timer.daemon = True
        timer.start()
        try:
            self._window.destroy()
        except Exception:
            os._exit(0)

    # ---- 크레딧 ----

    def get_credit(self):
        """POSTECH GenAI의 이번 주기 크레딧 사용량. 크레딧을 쓰지 않는 요청으로 확인한다."""
        key = self._postech_key()
        if not key:
            return {"ok": False, "error": "POSTECH GenAI API 키를 먼저 입력하세요."}
        url = self._config.get("chat_completions_url") or api.DEFAULT_CHAT_COMPLETIONS_URL
        if urlparse(url).hostname != urlparse(api.DEFAULT_CHAT_COMPLETIONS_URL).hostname:
            url = api.DEFAULT_CHAT_COMPLETIONS_URL  # 다른 OpenAI 호환 서버를 쓰더라도 크레딧은 POSTECH에 묻는다
        try:
            return {"ok": True, **api.credit(key, url)}
        except ApiError as e:
            return {"ok": False, "error": str(e)}

    # ---- PO노트 ----

    def _po_push(self, kind, **data):
        self._push({"type": "po", "kind": kind, **data})

    def po_state(self):
        ok, reason = stt.available()
        session = self._po_session
        return {
            "available": ok, "reason": reason,
            "engine": self._config.get("po_engine", "auto"),
            "model": self._config.get("po_model", stt.DEFAULT_MODEL),
            "language": self._config.get("po_language", "ko"),
            "device": self._config.get("po_device", ""),
            "reserve": self._po_reserve(),
            "models": stt.models_status() if ok else [],
            "languages": stt.LANGUAGES,
            "has_key": bool(self._postech_key()),
            "recording": {"note_id": self._po_note, "elapsed": session.elapsed if session else 0,
                          "engine": self._po_label if session else "", "stopping": self._po_stopping}
            if self._po_note else None,
            "download": self._po_download,
            "generating": self._po_generating,
            "credit": self._credit,
        }

    def po_devices(self):
        if not stt.available()[0]:
            return []
        try:
            return stt.input_devices()
        except Exception:
            return []

    def po_save_settings(self, settings):
        with self._lock:
            before = self._sync_settings()
            if settings.get("engine") in ("auto", "local", "server"):
                self._config["po_engine"] = settings["engine"]
            if settings.get("model") in stt.LOCAL_MODELS:
                self._config["po_model"] = settings["model"]
            if settings.get("language") in stt.LANGUAGES:
                self._config["po_language"] = settings["language"]
            if "device" in settings:
                self._config["po_device"] = settings["device"] if isinstance(settings["device"], int) else ""
            if settings.get("reserve") in PO_RESERVES:
                self._config["po_reserve"] = settings["reserve"]
            self._stamp_settings(before)
            storage.save_config(self._config)
        return self.po_state()

    def po_download_model(self, key):
        if key not in stt.LOCAL_MODELS:
            return {"ok": False, "error": "알 수 없는 모델입니다."}
        if self._po_download:
            return {"ok": False, "error": "이미 모델을 내려받고 있습니다."}
        self._po_download = {"key": key, "done": 0, "total": 0}
        self._po_cancel_download.clear()
        threading.Thread(target=self._po_download_work, args=(key,), daemon=True).start()
        return {"ok": True}

    def _po_download_work(self, key):
        last = [0.0]

        def progress(done, total):
            self._po_download = {"key": key, "done": done, "total": total}
            if time.monotonic() - last[0] >= 0.25:
                last[0] = time.monotonic()
                self._po_push("download", **self._po_download)

        try:
            stt.download(key, progress, self._po_cancel_download.is_set)
            self._po_download = None
            self._po_push("download_done", key=key, state=self.po_state())
        except stt.SttError as e:
            self._po_download = None
            self._po_push("download_error", key=key, error=str(e))

    def po_cancel_download(self):
        self._po_cancel_download.set()

    def po_delete_model(self, key):
        if self._po_session and getattr(self._po_session.engine, "key", None) == key:
            return {"ok": False, "error": "녹음에 쓰고 있는 모델은 지울 수 없습니다."}
        stt.delete_model(key)
        return {"ok": True, "state": self.po_state()}

    def _po_call(self, fn, *args):
        try:
            return {"ok": True, "result": fn(*args)}
        except (po_note.NoteError, OSError, ValueError) as e:
            return {"ok": False, "error": str(e)}

    def po_list(self):
        return po_note.list_notes()

    def po_create(self, title=None):
        return self._po_call(po_note.create, title)

    def po_load(self, note_id):
        return self._po_call(po_note.load, note_id)

    def po_rename(self, note_id, title):
        return self._po_call(po_note.rename, note_id, title)

    def po_delete(self, note_id):
        if note_id in (self._po_note, self._po_generating):
            return {"ok": False, "error": "녹음하거나 노트를 만드는 중인 강의는 지울 수 없습니다."}
        return self._po_call(po_note.delete, note_id)

    def po_save_note(self, note_id, text):
        return self._po_call(po_note.save_note, note_id, text)

    def po_save_memo(self, note_id, text):
        return self._po_call(po_note.save_memo, note_id, text)

    def po_upload_material(self, note_id, upload_id, name, offset, data_b64, last):
        return self._po_call(po_note.upload_material, note_id, upload_id, name, int(offset), data_b64, bool(last))

    def po_remove_material(self, note_id, material_id):
        return self._po_call(po_note.remove_material, note_id, material_id)

    def po_material_text(self, note_id, material_id):
        return self._po_call(po_note.material_text, note_id, material_id)

    def po_open_material(self, note_id, material_id):
        result = self._po_call(po_note.material_path, note_id, material_id)
        if result["ok"]:
            open_path(result["result"])
        return result

    def po_open_folder(self, note_id):
        result = self._po_call(po_note.export_files, note_id)
        if result["ok"]:
            open_path(result["result"])
        return result

    def _po_reserve(self):
        reserve = self._config.get("po_reserve", 30)
        return reserve if reserve in PO_RESERVES else 30

    def _po_budget_ok(self):
        """크레딧 예산 보호: 이번 주 남은 크레딧이 한도의 po_reserve% 아래면 서버를 쓰지 않는다."""
        reserve, c = self._po_reserve(), self._credit
        if not reserve or not c or not c.get("limit") or c.get("usage") is None:
            return True
        return c["limit"] - c["usage"] >= c["limit"] * reserve / 100

    def _po_engines(self, note_id):
        """{"engine", "fallback", "refiner", "label", "notice"}.

        auto: 로컬 모델이 있고 API 키가 있으면 하이브리드(로컬로 바로 받아 적고 불확실한 구간만 서버가 보정),
              모델이 없으면 이번에는 서버로 받아 적으면서 모델을 내려받기 시작한다. 키가 없으면 로컬만.
        server: 서버로 모두 받아 적고, 실패하거나 예산 아래면 로컬(있으면)로. local: 로컬만.
        """
        choice = self._config.get("po_engine", "auto")
        language = self._config.get("po_language", "ko")
        model = self._config.get("po_model", stt.DEFAULT_MODEL)
        key = self._postech_key()  # 개인 Claude API는 음성을 받지 않으므로 서버 음성 인식은 POSTECH 키로만 한다
        local = stt.LocalEngine(model, language) if stt.model_installed(model) else None
        server = None
        if key and choice != "local":
            url = self._config.get("chat_completions_url") or api.DEFAULT_CHAT_COMPLETIONS_URL
            server = stt.ServerEngine(key, url, language, hint=po_note.vocabulary(note_id))
        if choice == "local" or (choice == "auto" and server is None):
            if local is None:
                raise stt.SttError("로컬 음성 인식 모델을 먼저 내려받으세요(PO노트 → 음성 인식 설정)."
                                   + ("" if key else " API 키가 있으면 POSTECH 서버로도 받아 적을 수 있습니다."))
            return {"engine": local, "fallback": None, "refiner": None, "label": local.label, "notice": ""}
        if server is None:
            raise stt.SttError("POSTECH 서버 음성 인식에는 API 키가 필요합니다. 설정에서 키를 입력하세요.")
        if choice == "auto" and local is not None:
            return {"engine": local, "fallback": None, "refiner": server,
                    "label": f"{local.label} + POSTECH 보정", "notice": ""}
        notice = ""
        if choice == "auto" and not self._po_download:
            self.po_download_model(model)  # 다음 녹음부터 하이브리드로 크레딧을 아낀다
            notice = "로컬 AI 모델을 내려받는 동안 이번 녹음은 POSTECH 서버로 받아 적습니다."
        return {"engine": server, "fallback": local, "refiner": None, "label": server.label, "notice": notice}

    def po_start(self, note_id):
        ok, reason = stt.available()
        if not ok:
            return {"ok": False, "error": reason}
        if self._po_note:
            return {"ok": False, "error": "이미 녹음하고 있습니다."}
        try:
            meta = po_note.touch(note_id)
            if not stt.vad_installed():
                self._po_push("status", note_id=note_id, text="음성 구간 검출 모델(약 2MB)을 내려받는 중…")
                stt.download(None)
            engines = self._po_engines(note_id)
            if engines["refiner"] or isinstance(engines["engine"], stt.ServerEngine):
                try:
                    api.credit(self._postech_key(), self._config.get("chat_completions_url") or None)  # 예산 판단용(무료)
                except ApiError:
                    pass
        except (po_note.NoteError, stt.SttError) as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # 모델 파일이 깨졌거나 라이브러리를 불러오지 못했다
            return {"ok": False, "error": f"음성 인식을 시작하지 못했습니다: {type(e).__name__}: {e}"}
        last_error = [0.0]

        def on_segment(segment):
            try:
                po_note.append_segment(note_id, segment)
            except (po_note.NoteError, OSError):
                return
            self._po_push("segment", note_id=note_id, segment=segment)

        def on_refine(ids, fixed):
            try:
                items = po_note.apply_refinement(note_id, ids, fixed)
            except (po_note.NoteError, OSError):
                return
            self._po_push("transcript", note_id=note_id, transcript=items)

        def on_level(level, speaking):
            session = self._po_session
            self._po_push("level", note_id=note_id, level=round(level, 3), speaking=bool(speaking),
                          elapsed=round(meta.get("duration", 0) + (session.elapsed if session else 0), 1))

        def on_error(message):
            if time.monotonic() - last_error[0] >= 10:  # 같은 오류로 화면을 덮지 않는다
                last_error[0] = time.monotonic()
                self._po_push("error", note_id=note_id, error=message)

        device = self._config.get("po_device", "")
        session = stt.LiveSession(engines["engine"], on_segment, on_level, on_error,
                                  device=device if device != "" else None, offset=meta.get("duration", 0),
                                  fallback=engines["fallback"], refiner=engines["refiner"], on_refine=on_refine,
                                  budget_ok=self._po_budget_ok, id_base=po_note.next_segment_id(note_id))
        try:
            session.start()
        except stt.SttError as e:
            return {"ok": False, "error": str(e)}
        self._po_session, self._po_note, self._po_stopping = session, note_id, False
        self._po_label = engines["label"]
        po_note.touch(note_id, engine=engines["label"])
        return {"ok": True, "engine": engines["label"], "notice": engines["notice"], "state": self.po_state()}

    def po_stop(self):
        """녹음을 멈춘다. 남은 말 구간을 인식하는 동안 기다리지 않도록 백그라운드에서 마무리한다."""
        session, note_id = self._po_session, self._po_note
        if session is None or self._po_stopping:
            return {"ok": True}
        self._po_stopping = True
        self._po_push("stopping", note_id=note_id)

        def finish():
            elapsed = session.elapsed
            session.stop()
            try:
                meta = po_note._meta(note_id)
                po_note.touch(note_id, duration=round(meta.get("duration", 0) + elapsed, 1))
            except po_note.NoteError:
                pass
            self._po_session, self._po_note, self._po_stopping = None, None, False
            self._po_push("stopped", note_id=note_id)

        threading.Thread(target=finish, daemon=True).start()
        return {"ok": True}

    def _po_shutdown(self):
        """창을 닫을 때: 녹음을 멈추고 녹음 길이를 저장한다."""
        session, note_id = self._po_session, self._po_note
        if session is not None:
            elapsed = session.elapsed
            session.stop(timeout=20)
            try:
                po_note.touch(note_id, duration=round(po_note._meta(note_id).get("duration", 0) + elapsed, 1))
            except po_note.NoteError:
                pass
        self._po_cancel_download.set()

    def po_generate(self, note_id, model=None):
        """강의 자료·전사·메모로 필기 노트(note.md)를 만든다. 진행은 po 이벤트로 알린다.
        1.17: model이 'auto'·'local:…'이고 자동 선택이 켜져 있으면 Adaptive 엔진으로(받아 적기는 그대로 PO노트 설정을 따른다)."""
        key = self._api_key()
        routed = self._routed_model_ok(model)
        if not key and (not routed or self._api_needed(self._config, model)):
            return {"ok": False, "error": self._missing_key_error()}
        if adaptive_engine.local_only(self._config) and not routed:
            return {"ok": False, "error": "Local Only 정책이라 Cloud 모델로 노트를 만들지 않습니다. 모델을 '자동' 또는 로컬 모델로 고르세요."}
        if self._po_generating:
            return {"ok": False, "error": "다른 노트를 만들고 있습니다. 끝난 뒤 다시 시도하세요."}
        try:
            po_note.build_prompts(note_id)
        except po_note.NoteError as e:
            return {"ok": False, "error": str(e)}
        settings = ApiSettings.from_config(self._config)
        allowed = self._model_ids(settings.mode)
        if model in allowed:
            settings.model = model
        elif settings.model not in allowed:
            settings.model = self._default_model()
        self._po_generating = note_id
        routed_model = model if routed else None
        threading.Thread(target=self._po_generate_work, args=(note_id, key, settings, routed_model), daemon=True).start()
        return {"ok": True, "model": routed_model or settings.model}

    def _po_generate_work(self, note_id, key, settings, routed_model=None):
        last = [0.0]

        def on_delta(text):
            if time.monotonic() - last[0] >= 0.1:
                last[0] = time.monotonic()
                self._po_push("note_delta", note_id=note_id, text=text)

        def ask(prompt, delta):
            return api.ask(key, prompt, timeout=600, settings=settings, on_delta=delta)

        if routed_model:
            routed, _ = self._routed_ask(routed_model, key, "po_note", area="po_note")
            if routed is not None:
                ask = routed  # noqa: F811  자동·로컬 모델: 요약·노트 만들기만 엔진으로(전사는 PO노트 설정 그대로)
        try:
            text = po_note.generate(note_id, ask,
                                    on_status=lambda label: self._po_push("note_status", note_id=note_id, text=label),
                                    on_delta=on_delta)
            self._po_push("note_done", note_id=note_id, note=text)
        except (ApiError, po_note.NoteError, OSError) as e:
            self._po_push("note_error", note_id=note_id, error=str(e))
        finally:
            self._po_generating = None

    # ---- 대화 실행 ----

    def send(self, thread_id, text, agent_mode, attachment_ids=None):
        text = (text or "").strip()
        attachment_ids = [str(a) for a in attachment_ids or []]
        if not text and not attachment_ids:
            return {"ok": False, "error": "메시지가 비어 있습니다."}
        workspace = self._workspace()
        task, forced, command = text or "첨부한 파일을 살펴보고 내용을 알려 주세요.", None, None

        if text.startswith("/"):
            cmd, _, rest = text[1:].partition(" ")
            cmd, rest = cmd.lower(), rest.strip()
            if cmd == "user":
                command, task = "profile", rest
            elif cmd == "init":
                if not workspace:
                    return {"ok": False, "error": "/init 을 쓰려면 먼저 작업 폴더를 선택하세요."}
                agent_mode = True
                task = INIT_TASK + (f"\n추가 요청: {rest}" if rest else "")
            else:
                skills = discover_skills(workspace)
                if cmd not in skills:
                    return {"ok": False, "error": f"알 수 없는 명령어 또는 스킬입니다: /{cmd}"}
                forced = skills[cmd]
                task = rest or f"'{forced.name}' 스킬을 실행해 주세요."

        api_key = self._api_key()
        thread_model = (storage.load_thread(thread_id) or {}).get("model")
        if not api_key and self._api_needed(self._config, thread_model):
            return {"ok": False, "need_key": True, "error": self._missing_key_error()}
        if adaptive_engine.local_only(self._config) and not self._thread_routed(thread_model):
            return {"ok": False, "error": "Local Only 정책이라 이 대화의 Cloud 모델을 부르지 않습니다. 대화 위의 모델을 '자동' 또는 로컬 모델로 바꾸세요."}

        with self._lock:
            if thread_id in self._chat_runs:
                return {"ok": False, "error": "이 대화의 응답을 기다리는 중입니다."}
            thread = storage.load_thread(thread_id)
            if thread is None:
                return {"ok": False, "error": "대화를 찾을 수 없습니다."}
            try:
                attached = attachments.commit(attachment_ids)
            except (attachments.AttachmentError, ValueError) as e:
                return {"ok": False, "error": str(e)}
            history = list(thread["messages"])
            if not history and thread["title"] == "새 대화":
                thread["title"] = (text.splitlines()[0] if text else attached[0]["name"])[:40]
            msg = storage.make_message("user", text, **({"attachments": attached} if attached else {}))
            thread["messages"].append(msg)
            storage.save_thread(thread)
            self._busy = True
            self._run_id += 1
            run_id = self._run_id
            self._chat_runs[thread_id] = {"id": run_id, "cancel": threading.Event(), "allow": set()}

        threading.Thread(target=self._work, daemon=True,
                         args=(run_id, thread_id, history, task, bool(agent_mode), forced, api_key, workspace,
                               attached, command)).start()
        return {"ok": True, "message": msg, "title": thread["title"]}

    def _work(self, run_id, thread_id, *args):
        run = self._chat_runs[thread_id]
        run["mcp"] = mcp_client.Manager()
        try:
            self._chat_work(run_id, thread_id, *args)
        except Exception as e:
            if not run["cancel"].is_set():
                self._add(thread_id, "error", f"{type(e).__name__}: {e}")
        finally:
            run["mcp"].shutdown()
            with self._lock:
                if self._browser_owner is run:
                    self._browser_owner = None
                if self._chat_runs.get(thread_id) is run:
                    self._chat_runs.pop(thread_id)
                self._busy = bool(self._chat_runs)
            self._push({"type": "done", "thread_id": thread_id, "workspace": self._workspace_info()})

    def _chat_work(self, run_id, thread_id, history, task, agent_mode, forced, api_key, workspace, attached=(), command=None):
        run = self._chat_runs[thread_id]
        manager = run["mcp"]

        def alive():
            return self._chat_runs.get(thread_id) is run and not run["cancel"].is_set()

        def on_status(text):
            if alive():
                self._push({"type": "status", "thread_id": thread_id, "text": text})

        def on_tool(summary, detail):
            if alive():
                self._add(thread_id, "tool", summary, detail=detail)

        last_delta = [0.0]

        def on_delta(text):
            # 화면 갱신이 너무 잦지 않게 0.08초에 한 번만 보낸다. 마지막 답변은 message 이벤트로 따로 온다.
            now = time.monotonic()
            if alive() and now - last_delta[0] >= 0.08:
                last_delta[0] = now
                self._push({"type": "delta", "thread_id": thread_id, "text": text})

        def save_ai_memory_state(state):
            with self._lock:
                thread = storage.load_thread(thread_id)
                if thread is not None:
                    thread["ai_memory"] = state
                    storage.save_thread(thread)

        thread = storage.load_thread(thread_id) or {}
        # 1.17: 대화의 모델이 '자동'·로컬이면 Adaptive 엔진이 단계마다 고른다(라우팅 표시는 route 이벤트로 화면에)
        engine = self._make_engine(thread, api_key, lambda: not alive(),
                                   on_event=lambda ev: alive() and self._push({"type": "route", "thread_id": thread_id, **ev}),
                                   area="agent" if agent_mode and workspace else "chat")
        block_tools = engine is not None and adaptive_engine.local_only(self._config) and \
            adaptive_engine.settings(self._config)["local_only_tools"] == "block"
        with self._lock:
            browser = self._browser_for_agent() if self._browser_owner is None else None
            if browser is not None:
                self._browser_owner = run
        agent = Agent(
            api_key=api_key,
            workspace=workspace,
            agent_mode=agent_mode,
            max_steps=int(self._config.get("max_steps", 25)),
            history_messages=int(self._config.get("history_messages", 20)),
            on_status=on_status,
            on_tool=on_tool,
            confirm=lambda kind, title, detail: self._confirm(thread_id, kind, title, detail, alive, run["allow"]),
            cancelled=lambda: not alive(),
            thread_id=thread_id,
            share_threads=bool(self._config.get("share_threads", True)),
            mcp=(lambda: manager.ensure(self._config, workspace, on_status)) if agent_mode and workspace and not block_tools else None,
            api_settings=self._thread_api_settings(thread),
            on_delta=on_delta,
            ai_memory_state=thread.get("ai_memory"),
            on_ai_memory_state=save_ai_memory_state,
            policy=connectors.Policy(dict(self._config)),
            browser=browser,
            plms=bool(self._config.get("plms_enabled")) and not block_tools,
            # 1.18.6: 브라우저를 열지 않아도 채팅의 에이전트가 PLMS를 조회한다(숨은 웹 뷰·자동 로그인)
            plms_reader=lambda action, **kwargs: self._plms_read(action, cancelled=lambda: not alive(), **kwargs),
            paper=self._paper_for_agent(),
            # 1.15: Code 화면이 열려 있으면 파일 수정은 승인 창 대신 Code 화면의 변경 검토(덩어리별)로
            review=lambda *a: self._code_review_edit(thread_id, alive, workspace, *a, session_allow=run["allow"]),
            # 1.16 브라우저 에이전트: 진행 상황은 브라우저 막대와 채팅에, 일시정지는 브라우저 막대의 버튼
            browser_progress=lambda info: self._push({"type": "browser", "kind": "agent", "thread_id": thread_id, **info}),
            browser_paused=self._browser_pause_event(),
            engine=engine,
            prompt_cache=adaptive_engine.settings(self._config)["prompt_cache"],
            # 1.18.1: 웹 검색·읽기·논문 찾기(기능 끄기 또는 Local Only의 외부 도구 막기면 없음)
            web=connectors.feature_enabled(self._config, "web") and not block_tools,
        )
        started, outcome = time.monotonic(), "done"
        try:
            if command == "profile":
                answer = agent.update_profile(task, attached)
            else:
                answer = agent.run(history, task, forced, attached)
            self._save_frontier_session(thread_id, engine)
            if alive():
                extra = {}
                if engine is not None and engine.summary():
                    route = engine.summary()
                    extra["routing"] = route
                    model = ("local:" + route["model"]) if route.get("provider") == "local" else route.get("model")
                    if route.get("consulted") and engine.cloud_model:
                        extra["routing"]["frontier_model"] = engine.cloud_model
                else:
                    model = agent.api_settings.model
                self._add(thread_id, "assistant", answer, model=model or agent.api_settings.model, **extra)
            else:
                outcome = "cancelled"
        except ApiError as e:
            outcome = "error"
            if alive():
                self._add(thread_id, "error", str(e))
        except Exception as e:
            outcome = "error"
            if alive():
                self._add(thread_id, "error", f"{type(e).__name__}: {e}")
        finally:
            if agent.browser is not None:
                agent.browser.watch = None
            if getattr(agent, "_browser_agent", None) is not None:
                self._push({"type": "browser", "kind": "agent", "status": "finished", "thread_id": thread_id,
                            "count": agent._browser_agent.actions})
                self._browser_pause_event().clear()
            shots = getattr(agent, "screenshots", [])
            if shots and alive():
                try:
                    committed = attachments.commit([x["id"] for x in shots])
                    self._add(thread_id, "tool", f"📷 브라우저 화면 캡처 {len(committed)}장", detail="", attachments=committed)
                except (attachments.AttachmentError, ValueError):
                    pass
            telemetry.record("agent_run", mode="agent" if agent_mode and workspace else "chat",
                             model=thread.get("model") if engine is not None else agent.api_settings.model,
                             ms=int((time.monotonic() - started) * 1000),
                             outcome=outcome, steps=agent.steps, tools=len(agent.tools_run), routed=engine is not None)
            self._sync_schedule(20)  # 대화가 끝나면 잠시 뒤 동기화(켰을 때만)

    def _thread_api_settings(self, thread):
        settings = ApiSettings.from_config(self._config)
        model = thread.get("model")
        allowed = self._models(settings.mode)
        if model in {model_id for model_id, _ in allowed}:
            settings.model = model
        elif settings.model not in {model_id for model_id, _ in allowed}:
            settings.model = allowed[0][0]
        return settings

    def _confirm(self, thread_id, kind, title, detail, alive, session_allow=None):
        """kind: edit(파일 수정)·run(명령·외부 도구)·write(커넥터 쓰기)는 설정으로 자동 허용할 수 있고,
        send(전송)·destructive(삭제)·exec(코드 실행)·site(브라우저 에이전트의 사이트 승인)는 설정과 관계없이 매번 묻는다."""
        session_allow = self._session_allow if session_allow is None else session_allow
        permission = self._config.get("permission", "ask")
        always_ask = kind in connectors.ALWAYS_ASK
        if not always_ask and (permission == "auto_all" or (permission == "auto_edit" and kind == "edit")
                               or kind in session_allow):
            return True
        if not alive():
            return False
        cid = uuid.uuid4().hex
        entry = [threading.Event(), "deny", thread_id]
        self._pending[cid] = entry
        self._push({"type": "confirm", "id": cid, "thread_id": thread_id, "kind": kind, "title": title, "detail": detail,
                    "allow_session": not always_ask})
        while not entry[0].wait(0.1):
            if not alive():
                break
        self._pending.pop(cid, None)
        if entry[1] == "always":
            if not always_ask:
                session_allow.add(kind)
            return alive()
        return entry[1] == "allow" and alive()

    def resolve_confirm(self, cid, decision):
        entry = self._pending.get(cid)
        if entry:
            entry[1] = decision
            entry[0].set()

    def stop(self, thread_id=None):
        with self._lock:
            for tid, run in self._chat_runs.items():
                if thread_id is None or tid == thread_id:
                    run["cancel"].set()
            for entry in list(self._pending.values()):
                if thread_id is None or (len(entry) > 2 and entry[2] == thread_id):
                    entry[1] = "deny"
                    entry[0].set()
        return True


def selftest():
    """설치된 exe 진단용: 설정된 키로 API를 한 번 호출하고 결과를 데이터 폴더의 selftest.txt에 쓴다."""
    from api import ask
    storage.ensure_dirs()
    config = storage.load_config()
    if config.get("api_mode") == api.ANTHROPIC_MODE:
        key = config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY", "")
    elif config.get("api_mode") == api.OPENAI_MODE:
        key = config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    else:
        key = config.get("api_key") or os.environ.get("POSTECH_GENAI_API_KEY", "")
    lines = [f"version: {APP_VERSION}", f"distribution: {version.distribution()}",
             f"web: {(resource_dir() / 'web' / 'index.html').exists()}",
             f"skills: {len(discover_skills(config.get('workspace', '')))}"]
    try:
        import docx, olefile, openpyxl, pptx, pypdf  # noqa: F401,E401  문서 라이브러리가 함께 묶였는지
        lines.append("documents: OK")
    except ImportError as e:
        lines.append(f"documents: FAIL {e}")
    lines.append(f"attachments: {attachments.selfcheck()}")
    # 1.15 POSCHAT Code: 편집기 묶음과 코드 모듈이 함께 묶였는지
    import code_diff
    import code_git
    import code_runner
    bundle = resource_dir() / "web" / "vendor" / "codemirror" / "codemirror.min.js"
    ok = bundle.is_file() and bundle.stat().st_size > 100_000 and bool(code_diff.make_hunks("a\n", "b\n"))
    lines.append(f"code: {'OK' if ok else 'FAIL 편집기 묶음 없음'} (git {'있음' if code_git.available() else '없음'}, "
                 f"{code_runner.shell_name()})")
    # 1.16: Lab·Code 에이전트·브라우저 에이전트 모듈이 함께 묶였는지
    import browser_agent
    import code_agent
    import lab_results
    import lab_store
    ok = lab_results.to_number("1.5") == (1.5, "ok") and "data-poschat-id" in browser_agent.SNAPSHOT_SCRIPT \
        and lab_store.SCHEMA_VERSION >= 1 and code_agent.APPROVALS
    lines.append(f"lab-agents: {'OK' if ok else 'FAIL'}")
    # 1.17: Adaptive AI 모듈이 함께 묶였는지(로컬 AI가 없어도 라우터·검증기는 돈다)
    import adaptive_router
    import local_ai
    import quality_gate

    a = adaptive_router.analyze("이 글을 세 줄로 요약해 줘", "이 글을 세 줄로 요약해 줘")
    ok = a.task == "summarization" and quality_gate.check("general", "").failures == ["empty"] and \
        local_ai.check_endpoint("http://localhost:11434")[1]
    lines.append(f"adaptive: {'OK' if ok else 'FAIL'} (local {'지원' if local_ai.SUPPORTED else '없음'})")
    sdk = api._anthropic_sdk()  # 1.11 개인 Claude API: 데스크톱 배포본에는 공식 SDK가 함께 묶여야 한다
    lines.append(f"anthropic: OK {sdk.__version__}" if sdk else "anthropic: FAIL SDK 없음")
    import secret_store
    lines.append(f"secrets: {secret_store.backend_name()}")
    lines.append(f"stt: {stt.selfcheck()}")
    import terminal
    lines.append(f"terminal: {terminal.selfcheck()}")
    import ssh_remote   # 1.18: paramiko와 암호 라이브러리(cryptography·bcrypt·pynacl)가 묶였는지
    lines.append(f"ssh: {ssh_remote.selfcheck()}")
    import remote_client   # 1.18: 서버로 보낼 원격 도우미 소스가 설치본에 들어 있는지
    try:
        lines.append(f"remote: OK {len(remote_client.bundle())} bytes")
    except Exception as e:
        lines.append(f"remote: FAIL {type(e).__name__}: {e}")
    import tempfile
    import rag
    import sync
    lines.append(f"crypto: {sync.selfcheck()}")
    manager = mcp_client.Manager()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        lines.append(f"rag: {rag.selfcheck(tmp)}")
        try:
            servers = manager.ensure(config, tmp)
            status = manager.status(config, tmp)["servers"]
            lines.append("mcp: " + ", ".join(
                f"{s['name']} OK({len(s['tools'])})" if s["state"] == "connected" else f"{s['name']} {s['state'].upper()} {s['error']}"
                for s in status if s["enabled"]) + f" [{len(servers)} connected]")
            # 1.10 커넥터 서버가 함께 묶였는지(설정과 관계없이 켜서 띄워 본다)
            check = {"features": {k: True for k in connectors.FEATURES},
                     "connectors": {c: {"enabled": True} for c in ("github", "research", "memory", "python", "ssh")}}
            manager.ensure(check, tmp)
            status = {s["name"]: s for s in manager.status(check, tmp)["servers"]}
            lines.append("connectors: " + ", ".join(
                f"{n} OK({len(status[n]['tools'])})" if status.get(n, {}).get("state") == "connected"
                else f"{n} {status.get(n, {}).get('state', 'missing').upper()} {status.get(n, {}).get('error', '')}"
                for n in ("github", "research", "memory", "python", "ssh")))
        finally:
            manager.shutdown()  # 서버가 임시 폴더를 쓰고 있으면 지울 수 없으므로 먼저 끈다
    try:
        settings = ApiSettings.from_config(config)
        lines.append(f"api mode: {settings.mode}" + (f" ({settings.model})" if settings.mode in ("responses", api.ANTHROPIC_MODE, api.OPENAI_MODE) else ""))
        reply = ask(key, "'정상'이라고 한 단어로만 답하세요.", settings=settings) if key else "(API 키 없음)"
        lines.append(f"api: OK {reply[:80]!r}")
    except ApiError as e:
        lines.append(f"api: FAIL {e}")
    (storage.APP_DIR / "selftest.txt").write_text("\n".join(lines), encoding="utf-8")


def uninstall(quiet=False):
    """설치 프로그램이 등록한 제거 명령(PostechChat.exe --uninstall). 대화 기록·설정은 남긴다."""
    import ctypes
    import subprocess
    import winreg
    from pathlib import Path

    app_dir = Path(sys.executable).resolve().parent
    if not getattr(sys, "frozen", False) or not (app_dir / "_internal").is_dir():
        return  # 소스 실행 중에는 아무것도 지우지 않는다
    MB_YESNO, MB_ICONQUESTION, MB_ICONINFO, IDYES = 0x4, 0x20, 0x40, 6
    message = (f"{APP_TITLE}을(를) 제거할까요?\n\n대화 기록과 설정은 지우지 않고 다음 폴더에 남깁니다.\n{storage.APP_DIR}")
    if not quiet and ctypes.windll.user32.MessageBoxW(None, message, "제거", MB_YESNO | MB_ICONQUESTION) != IDYES:
        return

    def shell_folder(csidl):
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf)
        return Path(buf.value)

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\PostechChat"
    shortcuts = [shell_folder(csidl) / f"{APP_TITLE}.lnk" for csidl in (0x02, 0x10)]  # 시작 메뉴, 바탕화면
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as k:
            shortcuts += [Path(p) for p in winreg.QueryValueEx(k, "Shortcuts")[0]]  # 설치 때 실제로 만든 바로가기
    except OSError:
        pass
    for lnk in shortcuts:
        try:
            lnk.unlink(missing_ok=True)
        except OSError:
            pass
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except OSError:
        pass
    # 실행 중인 자기 자신은 지울 수 없으므로, 프로세스가 끝난 뒤 cmd가 폴더를 지운다.
    subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & rmdir /s /q "{app_dir}"',
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS, cwd=str(app_dir.parent))
    if not quiet:
        ctypes.windll.user32.MessageBoxW(None, f"{APP_TITLE}을(를) 제거했습니다.", "제거", MB_ICONINFO)


def _log_crash():
    """창 모드 exe는 오류가 화면에 안 보이므로 데이터 폴더의 error.log에 남긴다."""
    import traceback
    try:
        storage.APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(storage.APP_DIR / "error.log", "a", encoding="utf-8") as f:
            f.write(traceback.format_exc() + "\n")
    except OSError:
        pass


def main():
    _extend_mac_path()
    verify = next((a for a in sys.argv if a.startswith("--verify-install=")), None)
    if verify:
        # 설치 프로그램이 새 버전을 바꾼 뒤 부른다: 여기까지 왔으면 파이썬 DLL과 앱 코드를 모두 불러온 것이다
        Path(verify.split("=", 1)[1]).write_text(APP_VERSION, encoding="utf-8")
        return
    try:
        if "--mcp-server" in sys.argv:
            # 앱 자신을 내장 MCP 서버로 실행한다(mcp_client가 띄운다).
            import office_mcp
            i = sys.argv.index("--mcp-server")
            office_mcp.serve(sys.argv[i + 1] if i + 1 < len(sys.argv) else "")
        elif "--selftest" in sys.argv:
            selftest()
        elif "--uninstall" in sys.argv:
            uninstall(quiet="--quiet" in sys.argv)
        else:
            run_app()
    except Exception:
        _log_crash()
        raise


def _window_size(width=1240, height=840):
    """작업 표시줄을 뺀 화면 영역(논리 픽셀)의 90%를 넘지 않게 창 크기를 정한다."""
    try:
        import ctypes
        from ctypes import wintypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    try:
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
        scale = ctypes.windll.user32.GetDpiForSystem() / 96
        work_w, work_h = (rect.right - rect.left) / scale, (rect.bottom - rect.top) / scale
        return min(width, int(work_w * 0.9)), min(height, int(work_h * 0.9))
    except Exception:
        return width, height


def run_app():
    bridge = Bridge()
    index = resource_dir() / "web" / "index.html"
    width, height = _window_size()
    mode = bridge._window_mode()  # 1.19 설정 → 시작할 때 창 크기(기본 창·최대화·전체 화면)
    window = webview.create_window(
        APP_TITLE, url=str(index), js_api=bridge,
        width=width, height=height, min_size=(760, 520), text_select=True,
        maximized=mode == "maximized", fullscreen=mode == "fullscreen",
    )
    bridge._track_window(window, mode)
    try:
        webview.start(debug=os.environ.get("POSTECH_CHAT_DEBUG") == "1")
    finally:
        bridge._events.stop()  # 창이 닫혔다: 더 보내지 않는다(보내는 중인 evaluate_js를 오래 기다리지 않는다)
        bridge.stop()  # 모든 채팅의 승인 대기·실행을 취소한다
        bridge._po_shutdown()
        bridge._ca_shutdown()  # Code 에이전트 작업을 멈춘다
        bridge.adaptive_pull_cancel()  # 1.17: 받던 로컬 모델이 있으면 멈춘다(Ollama가 다음에 이어 받는다)
        bridge._code_shutdown()  # 실행 패널에서 돌던 명령을 끝낸다(프로세스가 남지 않게)
        bridge._ssh_shutdown()  # 1.18: SSH 연결을 닫는다(서버의 도우미·명령도 함께 끝난다)
        bridge._mcp.shutdown()
        if bridge._browser_obj is not None:
            bridge._browser_obj.close()
        if getattr(bridge, "_exit_for_update", False):
            os._exit(0)  # 설치 프로그램이 이 프로세스가 끝나기를 기다린다


if __name__ == "__main__":
    main()
