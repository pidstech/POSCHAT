# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""비밀(커넥터 토큰·API 키) 저장소.

OS 보안 저장소(keyring: Windows 자격 증명 관리자, macOS 키체인)를 먼저 쓰고, 쓸 수 없으면(안드로이드,
키링 서비스가 없는 리눅스) 데이터 폴더의 secrets.json에 소유자만 읽을 수 있게(POSIX 0600) 저장한다.
안드로이드의 데이터 폴더는 앱 전용 샌드박스라 다른 앱이 읽을 수 없다.

여기 저장한 값은 config.json·동기화·로그·관측 데이터·화면 상태(get_state)에 들어가지 않는다.
내장 MCP 서버는 하위 프로세스(같은 실행 파일, 같은 사용자)에서도 이 모듈로 값을 읽는다.
1.18.9부터 설정 창의 API 키·토큰(storage.CONFIG_SECRET_KEYS)도 여기(config:secrets, JSON 하나)에 두고 config.json에서는 뺀다.
"""
import json
import os
import threading

import storage

SERVICE = "PostechChat"
SECRETS_PATH = storage.APP_DIR / "secrets.json"
# 테스트나 진단에서 파일 저장소를 강제할 때: POSTECH_CHAT_SECRETS=file
FORCE_FILE = os.environ.get("POSTECH_CHAT_SECRETS") == "file"

_lock = threading.Lock()
_keyring = None  # None: 아직 확인 안 함, False: 쓸 수 없음, 그 밖: keyring 모듈


def _keyring_module():
    global _keyring
    if _keyring is None:
        _keyring = False
        if not FORCE_FILE:
            try:
                import keyring
                from keyring.backends import fail

                backend = keyring.get_keyring()
                usable = not isinstance(backend, fail.Keyring) and getattr(backend, "priority", 0) > 0
                # 여러 백엔드를 묶는 체인에 실제 백엔드가 하나도 없으면 쓸 수 없다
                if usable and hasattr(backend, "backends") and not backend.backends:
                    usable = False
                _keyring = keyring if usable else False
            except Exception:
                _keyring = False
    return _keyring


def backend_name():
    """화면 표시용 저장 위치."""
    kr = _keyring_module()
    if kr:
        return f"os:{type(kr.get_keyring()).__name__}"
    return "file"


def _read_file():
    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_file(data):
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SECRETS_PATH.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, SECRETS_PATH)
    try:
        os.chmod(SECRETS_PATH, 0o600)
    except OSError:
        pass


class SecretStoreError(Exception):
    """OS 보안 저장소를 읽지 못했다(잠김·접근 거부). '저장된 값 없음'과 다르다."""


def get(name, strict=False):
    """저장된 값. 없으면 "".
    strict=True(2.0): 키체인을 읽지 못했고 파일에도 없으면 ""가 아니라 SecretStoreError를 낸다.
    '없음'으로 여기고 저장하면 키체인에 있던 값을 지워 버리기 때문이다(storage.save_config)."""
    kr = _keyring_module()
    failed = False
    if kr:
        try:
            value = kr.get_password(SERVICE, name)
            if value is not None:
                return value
        except Exception:
            failed = True  # 키체인이 잠겼거나 접근 거부: 파일 쪽도 본다
    with _lock:
        value = str(_read_file().get(name) or "")
    if failed and strict and not value:
        raise SecretStoreError(name)
    return value


def set(name, value):  # noqa: A001 — 모듈 함수 이름(secret_store.set)으로만 쓴다
    value = str(value or "")
    if not value:
        return delete(name)
    kr = _keyring_module()
    if kr:
        try:
            kr.set_password(SERVICE, name, value)
            with _lock:  # 예전에 파일에 남은 같은 이름은 지운다
                data = _read_file()
                if data.pop(name, None) is not None:
                    _write_file(data)
            return "os"
        except Exception:
            pass  # 키체인에 쓰지 못하면 파일로
    with _lock:
        data = _read_file()
        data[name] = value
        _write_file(data)
    return "file"


def delete(name):
    kr = _keyring_module()
    if kr:
        try:
            kr.delete_password(SERVICE, name)
        except Exception:
            pass
    with _lock:
        data = _read_file()
        if data.pop(name, None) is not None:
            _write_file(data)


def has(name):
    return bool(get(name))


def get_json(name, strict=False):
    raw = get(name, strict=strict)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def set_json(name, value):
    return set(name, json.dumps(value, ensure_ascii=False) if value else "")


def mask(value):
    """화면·로그에 보일 때: 앞 4글자와 끝 4글자만."""
    value = str(value or "")
    if len(value) <= 10:
        return "•" * len(value)
    return f"{value[:4]}…{value[-4:]}"
