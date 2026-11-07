# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""모델 카탈로그(models.json) 관리 도구.

    python tools/model_catalog.py write   # api.py의 기본 목록으로 models.json을 다시 만든다(내용이 바뀌면 날짜도 바꾼다)
    python tools/model_catalog.py check   # models.json이 api.py와 같은지 확인(다르면 종료 코드 1). CI tests 단계
    python tools/model_catalog.py probe   # 제공자 API에 실제 모델 목록을 물어 카탈로그와 비교(Markdown 보고서)

모델 목록을 바꾸는 순서: api.py의 MODELS·ANTHROPIC_MODELS·OPENAI_MODELS·MODEL_ALIASES를 고치고 `write` → main에 병합.
설치된 앱은 하루 안에 main의 models.json을 받아 목록을 바꾼다(앱 릴리스 불필요). 모델 이름이 바뀌었으면 MODEL_ALIASES에
옛 ID → 새 ID를 넣어 두면 그 모델로 된 대화와 설정이 새 ID로 옮겨진다.

probe는 환경 변수의 키로 묻는다(없는 제공자는 건너뛴다): ANTHROPIC_API_KEY, OPENAI_API_KEY,
POSTECH_GENAI_API_KEY(+ 선택 POSTECH_CHAT_COMPLETIONS_URL). POSTECH 게이트웨이는 GET .../models가 404라
'확인 불가'로 표시된다. 키는 출력하지 않는다.
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import api  # noqa: E402
import model_catalog  # noqa: E402

CATALOG_PATH = ROOT / "models.json"


def _without_date(data):
    return {k: v for k, v in data.items() if k != "updated"}


def _current():
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write():
    current = _current()
    built = model_catalog.build(api)
    if current is not None and _without_date(current) == _without_date(built):
        print("models.json이 이미 최신입니다.")
        return 0
    built["updated"] = datetime.date.today().isoformat()
    model_catalog.validate(built)
    CATALOG_PATH.write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"models.json을 새로 썼습니다({built['updated']}).")
    return 0


def check():
    current = _current()
    if current is None:
        print("models.json이 없거나 JSON이 아닙니다. `python tools/model_catalog.py write`를 실행하세요.")
        return 1
    try:
        model_catalog.validate(current)
    except model_catalog.CatalogError as e:
        print(f"models.json 형식 오류: {e}")
        return 1
    if _without_date(current) != _without_date(model_catalog.build(api)):
        print("models.json이 api.py의 모델 목록과 다릅니다. `python tools/model_catalog.py write`를 실행하세요.")
        return 1
    print("models.json = api.py")
    return 0


def _diff(title, catalog_ids, server_ids, note=""):
    lines = [f"### {title}"]
    if server_ids is None:
        lines.append(f"- 확인 불가: {note}")
        return lines, False
    added = [m for m in server_ids if m not in catalog_ids]
    gone = [m for m in catalog_ids if m not in server_ids]
    if not added and not gone:
        lines.append(f"- 변화 없음({len(catalog_ids)}개)")
        return lines, False
    if gone:
        lines.append("- **카탈로그에 있지만 제공자가 더 이상 알려 주지 않는 모델(종료·이름 변경 의심)**: "
                     + ", ".join(f"`{m}`" for m in gone))
    if added:
        lines.append("- 제공자에 새로 보이는 모델(카탈로그에 없음): " + ", ".join(f"`{m}`" for m in added[:40])
                     + (f" 외 {len(added) - 40}개" if len(added) > 40 else ""))
    return lines, bool(gone)


def probe(out=None):
    """제공자 목록과 비교. 카탈로그 모델이 사라졌으면 종료 코드 2(사람이 확인할 일), 새 모델만 있으면 0."""
    catalog = model_catalog.validate(model_catalog.build(api))["modes"]
    ids = {mode: [m for m, _ in rows] for mode, rows in catalog.items()}
    report = ["## 모델 목록 점검", "", f"카탈로그(api.py) 기준 {datetime.date.today().isoformat()}", ""]
    attention = False
    checks = []
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    checks.append(("개인 Claude API(Anthropic)", "anthropic", key and (lambda: api.list_anthropic_models(key))))
    okey = os.environ.get("OPENAI_API_KEY", "").strip()
    checks.append(("개인 GPT API(OpenAI)", "openai", okey and (lambda: api.list_openai_models(okey))))
    pkey = os.environ.get("POSTECH_GENAI_API_KEY", "").strip()
    url = os.environ.get("POSTECH_CHAT_COMPLETIONS_URL", "").strip() or api.DEFAULT_CHAT_COMPLETIONS_URL
    checks.append(("POSTECH GenAI(OpenAI 호환)", "chat_completions", pkey and (lambda: api.list_models(pkey, url))))
    for title, mode, call in checks:
        if not call:
            lines, flag = _diff(title, ids[mode], None, "키가 없어 건너뜀")
        else:
            try:
                lines, flag = _diff(title, ids[mode], call())
            except api.ApiError as e:
                lines, flag = _diff(title, ids[mode], None, str(e)[:300])
        report += lines + [""]
        attention = attention or flag
    if attention:
        report += ["api.py의 목록을 고친 뒤 `python tools/model_catalog.py write`로 models.json을 갱신하세요. "
                   "이름이 바뀐 모델은 MODEL_ALIASES에 옛 ID → 새 ID를 넣으세요."]
    text = "\n".join(report)
    print(text)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    return 2 if attention else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("write")
    sub.add_parser("check")
    p = sub.add_parser("probe")
    p.add_argument("--out", help="보고서(Markdown)를 쓸 파일")
    args = parser.parse_args(argv)
    if args.command == "write":
        return write()
    if args.command == "check":
        return check()
    return probe(args.out)


if __name__ == "__main__":
    sys.exit(main())
