# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""2.3 모델 카탈로그: 제공 모델이 바뀌어도 앱을 새로 내지 않고 모델 목록을 맞춘다.

- 저장소의 `models.json`(api.py의 기본 목록에서 `tools/model_catalog.py write`로 만든다)을 앱이 하루에 한 번 받아 온다.
  POSTECH 게이트웨이는 모델 목록(GET .../models)을 알려 주지 않으므로, 게이트웨이 모델이 바뀌면 이 파일만 고쳐
  main에 올리면 설치된 앱이 따라온다.
- 받은 카탈로그는 모델 ID·이름·옛 ID→새 ID(aliases)만 담는다. 주소·키·설정은 바꾸지 못한다. 형식이 맞지 않거나
  schema가 다르면 통째로 버리고 앱에 들어 있는 기본 목록을 그대로 쓴다.
"""
import json
import re

import net

SCHEMA = 1
# 앞에서부터 시도한다. GitHub(raw)가 막힌 망이면 업데이트 서버가 같은 파일을 준다(docs/update-server.md).
SOURCES = (
    "https://raw.githubusercontent.com/pidstech/POSCHAT/main/models.json",
    "https://pidstech.com/api/models.json",
)
# 카탈로그가 다루는 API 방식. responses(게이트웨이 Responses API)는 앞으로 쓰지 않을 방식이라 앱 기본 목록만 쓴다.
MODES = ("chat_completions", "anthropic", "openai")
MAX_BYTES = 64 * 1024
MAX_MODELS = 100
MAX_ALIASES = 200
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,99}$")
MAX_LABEL = 80


class CatalogError(Exception):
    pass


def _label(value, model_id):
    text = " ".join(str(value or "").split())[:MAX_LABEL]
    return text or model_id


def validate(data):
    """받은 JSON을 앱이 쓸 꼴({"schema", "updated", "modes": {mode: [[id, label], ...]}, "aliases": {...}})로.

    하나라도 틀리면 CatalogError. 모르는 키는 버린다(새 버전 카탈로그가 키를 늘려도 옛 앱이 깨지지 않게).
    """
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise CatalogError("모델 카탈로그 형식(schema)이 이 앱과 맞지 않습니다.")
    modes = {}
    for mode in MODES:
        rows = data.get(mode)
        if rows is None:
            continue
        if not isinstance(rows, list) or not rows or len(rows) > MAX_MODELS:
            raise CatalogError(f"모델 카탈로그의 {mode} 목록이 올바르지 않습니다.")
        out, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not MODEL_ID.match(row["id"]):
                raise CatalogError(f"모델 카탈로그의 {mode} 모델 ID가 올바르지 않습니다.")
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            out.append([row["id"], _label(row.get("label"), row["id"])])
        modes[mode] = out
    aliases = data.get("aliases") or {}
    if not isinstance(aliases, dict) or len(aliases) > MAX_ALIASES:
        raise CatalogError("모델 카탈로그의 aliases가 올바르지 않습니다.")
    clean_aliases = {}
    for old, new in aliases.items():
        if not (isinstance(old, str) and isinstance(new, str) and MODEL_ID.match(old) and MODEL_ID.match(new)):
            raise CatalogError("모델 카탈로그의 aliases가 올바르지 않습니다.")
        if old != new:
            clean_aliases[old] = new
    if not modes:
        raise CatalogError("모델 카탈로그에 모델이 없습니다.")
    updated = data.get("updated")
    return {"schema": SCHEMA, "updated": updated if isinstance(updated, str) else "",
            "modes": modes, "aliases": clean_aliases}


def load(value):
    """설정에 저장해 둔 카탈로그(validate의 결과)를 다시 확인한다. 틀리면 None(기본 목록을 쓴다)."""
    if not isinstance(value, dict) or not isinstance(value.get("modes"), dict):
        return None
    raw = {"schema": value.get("schema"), "updated": value.get("updated"), "aliases": value.get("aliases")}
    for mode, rows in value["modes"].items():
        if mode in MODES and isinstance(rows, list):
            raw[mode] = [{"id": r[0], "label": r[1]} for r in rows if isinstance(r, list) and len(r) == 2]
    try:
        return validate(raw)
    except CatalogError:
        return None


def fetch(timeout=10):
    """카탈로그를 받아 validate한 결과. 모든 곳에서 실패하면 CatalogError(마지막 오류)."""
    error = "모델 카탈로그를 받지 못했습니다."
    for url in SOURCES:
        try:
            response = net.http("GET", url, timeout=timeout, headers={"Accept": "application/json"},
                                allow_redirects=False, stream=True)
        except net.ToolFailure as e:
            error = str(e)
            continue
        try:
            if response.status_code != 200:
                error = f"모델 카탈로그 서버 응답 {response.status_code}({url})"
                continue
            body = response.raw.read(MAX_BYTES + 1, decode_content=True)
        except Exception as e:  # noqa: BLE001 - 읽는 중 끊김 등은 다음 주소로
            error = f"모델 카탈로그를 읽지 못했습니다: {e}"
            continue
        finally:
            response.close()
        if len(body) > MAX_BYTES:
            error = "모델 카탈로그가 너무 큽니다."
            continue
        try:
            return validate(json.loads(body.decode("utf-8")))
        except (ValueError, UnicodeDecodeError) as e:
            error = f"모델 카탈로그 JSON 오류: {e}"
        except CatalogError as e:
            error = str(e)
    raise CatalogError(error)


def build(api_module, updated=""):
    """api.py의 기본 목록으로 카탈로그 JSON(models.json의 내용)을 만든다. tools/model_catalog.py가 쓴다."""
    def rows(models):
        return [{"id": m, "label": label} for m, label in models]

    return {
        "schema": SCHEMA,
        "updated": updated,
        "chat_completions": rows(api_module.MODELS),
        "anthropic": rows(api_module.ANTHROPIC_MODELS),
        "openai": rows(api_module.OPENAI_MODELS),
        "aliases": dict(api_module.MODEL_ALIASES),
    }
