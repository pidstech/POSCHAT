# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""플러그인: Anthropic의 Knowledge Work Plugins(https://github.com/anthropics/knowledge-work-plugins)를 받아 쓴다.

플러그인은 직무별 스킬(skills/<이름>/SKILL.md)과 명령(commands/<이름>.md) 묶음이며, POSCHAT 스킬과 같은 형식이다.
설치하면 데이터 폴더의 plugins/<플러그인>/에 그 파일을 풀고, 켜 둔 플러그인의 스킬·명령을 에이전트가
`플러그인:스킬` 이름으로 쓴다(/productivity:start처럼 직접 부를 수도 있다).

- 목록: 저장소 zip(codeload.github.com)을 한 번 받아 .claude-plugin/marketplace.json과 각 플러그인의 정보를 읽는다.
  받은 zip과 목록은 plugins/.catalog/에 두어 오프라인에서도 보인다.
- 설치할 수 있는 것: 이 저장소 안에 있는 플러그인(Anthropic 제작과 저장소 안의 파트너 제작). 다른 회사 저장소를
  가리키는 플러그인은 목록에만 보이고 설치하지 않는다(받을 코드를 이 앱이 검토할 수 없다).
- 플러그인의 .mcp.json(Slack·Notion 등 원격 MCP와 OAuth)은 연결하지 않는다. 필요한 커넥터 이름만 보여 주고,
  스킬은 첨부·붙여 넣은 자료와 POSCHAT 커넥터(GitHub·Google·Notion·Zotero 등)로 동작한다.
- 플러그인 파일은 실행하지 않는다. 스킬이 안내하는 스크립트는 에이전트의 명령 실행과 같이 승인을 받는다.
"""
import json
import re
import shutil
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath

import requests

import storage

MARKETPLACE = "anthropics/knowledge-work-plugins"
REPO_URL = f"https://github.com/{MARKETPLACE}"
ARCHIVE_URL = f"https://codeload.github.com/{MARKETPLACE}/zip/refs/heads/main"


# 데이터 폴더는 시험에서 바뀌므로 경로는 부를 때마다 storage.APP_DIR에서 만든다
def plugins_dir():
    return storage.APP_DIR / "plugins"


def _catalog_dir():
    return plugins_dir() / ".catalog"


def _archive():
    return _catalog_dir() / "knowledge-work-plugins.zip"


def _catalog_file():
    return _catalog_dir() / "catalog.json"


def _state_file():
    return plugins_dir() / "state.json"

MAX_ARCHIVE = 200 * 1024 * 1024
MAX_PLUGIN = 60 * 1024 * 1024
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_lock = threading.RLock()

# 한국어 한 줄 소개(목록에서 먼저 보인다). 없으면 원문 설명만 보인다.
KO_SUMMARY = {
    "productivity": "할 일·일정·하루 업무를 정리하고, 자주 쓰는 맥락을 기억해 같은 설명을 반복하지 않게 합니다.",
    "enterprise-search": "메일·채팅·문서·위키를 한 번에 찾고 요약합니다.",
    "cowork-plugin-management": "우리 조직에 맞는 플러그인을 새로 만들거나 고칩니다.",
    "sales": "고객 조사, 미팅 준비, 파이프라인 검토, 제안 메일 초안, 경쟁사 비교를 돕습니다.",
    "finance": "분개·대사·재무제표·차이 분석·결산·감사 준비를 돕습니다.",
    "data": "SQL 작성, 통계 분석, 시각화·대시보드, 결과 검증까지 데이터 작업을 돕습니다.",
    "legal": "계약서 검토, NDA 분류, 규정 준수, 위험 평가와 정형 답변 초안을 돕습니다.",
    "marketing": "콘텐츠 초안, 캠페인 계획, 브랜드 톤 유지, 경쟁사 브리핑, 성과 보고를 돕습니다.",
    "customer-support": "문의 분류, 답변 초안, 에스컬레이션 정리, 해결 사례의 지식 문서화를 돕습니다.",
    "product-management": "기획서 작성, 로드맵, 사용자 조사 정리, 이해관계자 공유, 경쟁 분석을 돕습니다.",
    "bio-research": "문헌 검색, 단일세포 RNA 분석, 연구 주제 선정 등 전임상 생명과학 연구를 돕습니다.",
    "engineering": "코드 리뷰, 설계 문서, 장애 대응, 기술 부채 정리 등 개발 업무를 돕습니다.",
    "human-resources": "채용 공고, 면접 준비, 온보딩, 평가·보상 등 인사 업무를 돕습니다.",
    "design": "디자인 리뷰, UX 문구, 접근성 점검, 디자인 시스템 정리를 돕습니다.",
    "operations": "업무 절차서, 공급업체 관리, 프로세스 개선 등 운영 업무를 돕습니다.",
    "small-business": "소상공인의 마케팅·고객 관리·리뷰 대응·세금 준비를 돕습니다.",
    "pdf-viewer": "PDF 주석·서명·양식 채우기 절차를 안내합니다(원래는 실시간 PDF 보기 화면과 함께 쓰는 플러그인이라 POSCHAT에서는 일부만 동작).",
    "brand-voice": "브랜드 말투 지침을 만들고 글이 그 톤을 지키는지 점검합니다.",
    "slack-by-salesforce": "Slack 대화를 찾고 요약하며 메시지 초안을 만듭니다.",
    "apollo": "Apollo로 잠재 고객을 찾고 연락처를 보강합니다.",
    "common-room": "Common Room의 커뮤니티 신호로 고객을 조사합니다.",
    "zoom-plugin": "Zoom 회의 기록을 요약하고 후속 조치를 정리합니다.",
}
# 학생·연구자에게 먼저 권하는 순서
RECOMMENDED = ("productivity", "bio-research", "data", "engineering", "product-management", "legal", "design",
               "marketing", "enterprise-search")


class PluginError(Exception):
    pass


# ---- 앞부분(frontmatter) ----

def frontmatter(text):
    """(메타데이터 dict, 본문). 한 줄 값과 YAML의 '>'(접기)·'|'(그대로) 여러 줄 값을 읽는다."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    lines, meta, i = text[3:end].splitlines(), {}, 0
    while i < len(lines):
        line = lines[i]
        i += 1
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        if value[:1] in (">", "|"):
            block = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1] in (" ", "\t")):
                block.append(lines[i].strip())
                i += 1
            value = (" " if value[0] == ">" else "\n").join(block).strip()
        elif len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].replace('\\"', '"')
        meta[key] = value
    return meta, text[end + 4:].lstrip("\n")


# ---- 상태 ----

def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def state():
    data = _read_json(_state_file(), {})
    return data if isinstance(data, dict) else {}


def installed():
    """{이름: {"enabled", "version", "installed_at", "display_name"}} 중 파일이 실제로 있는 것."""
    return {n: s for n, s in state().items() if isinstance(s, dict) and (plugins_dir() / n).is_dir()}


def skill_sources():
    """켜 둔 플러그인마다 (플러그인 이름, 플러그인 폴더). agent.discover_skills가 쓴다."""
    return [(n, plugins_dir() / n) for n, s in sorted(installed().items()) if s.get("enabled", True)]


def plugin_skills(name, root):
    """플러그인 폴더의 스킬·명령을 [(이름, 설명, 본문, 경로, 종류)]로. 이름은 '플러그인:스킬'."""
    root = Path(root)
    out = []
    files = [(p, "skill") for p in sorted(root.glob("skills/*/SKILL.md"))] + \
            [(p, "command") for p in sorted(root.glob("commands/*.md"))]
    for path, kind in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = frontmatter(text)
        short = meta.get("name") or (path.parent.name if kind == "skill" else path.stem)
        body = body.replace("${CLAUDE_PLUGIN_ROOT}", str(root)).replace("$CLAUDE_PLUGIN_ROOT", str(root))
        out.append((f"{name}:{short}", meta.get("description", ""), body, path, kind))
    return out


# ---- 목록 ----

def _zip_root(zf):
    names = zf.namelist()
    return names[0].split("/", 1)[0] + "/" if names else ""


def _read(zf, path):
    try:
        return zf.read(path).decode("utf-8", errors="replace")
    except KeyError:
        return None


def _safe_member(rel):
    p = PurePosixPath(rel)
    return not (p.is_absolute() or ".." in p.parts or any(":" in part for part in p.parts))


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _describe(zf, root, entry):
    name = str(entry.get("name") or "")
    source = entry.get("source")
    info = {"name": name, "display_name": entry.get("displayName") or name, "description": entry.get("description") or "",
            "summary": KO_SUMMARY.get(name, ""), "category": entry.get("category") or "", "homepage": entry.get("homepage") or "",
            "installable": False, "skills": [], "commands": [], "connectors": [], "version": "", "author": "",
            "partner": False, "path": ""}
    if not NAME_RE.match(name):
        return None
    if not (isinstance(source, str) and source.startswith("./") and _safe_member(source[2:])):
        url = source.get("url", "") if isinstance(source, dict) else ""
        info["homepage"] = info["homepage"] or url.removesuffix(".git")
        info["external"] = True
        return info
    base = root + source[2:].strip("/") + "/"
    manifest = _read(zf, base + ".claude-plugin/plugin.json")
    if manifest is None:
        return None
    try:
        manifest = json.loads(manifest)
    except ValueError:
        manifest = {}
    author = manifest.get("author")
    info.update(installable=True, external=False, path=source[2:].strip("/"), version=str(manifest.get("version") or ""),
                author=(author.get("name") if isinstance(author, dict) else str(author or "")),
                partner=source.startswith("./partner-built/"),
                homepage=info["homepage"] or f"{REPO_URL}/tree/main/{source[2:].strip('/')}")
    for member in zf.namelist():
        if not member.startswith(base):
            continue
        rel = member[len(base):]
        m = re.fullmatch(r"skills/([^/]+)/SKILL\.md", rel) or re.fullmatch(r"commands/([^/]+)\.md", rel)
        if m:
            meta, _ = frontmatter(_read(zf, member) or "")
            kind = "skills" if rel.startswith("skills/") else "commands"
            info[kind].append({"name": meta.get("name") or m.group(1),
                               "description": _clip(" ".join(meta.get("description", "").split()), 400),
                               "argument": meta.get("argument-hint", "")})
    mcp = _read(zf, base + ".mcp.json")
    if mcp:
        try:
            info["connectors"] = sorted((json.loads(mcp).get("mcpServers") or {}).keys())
        except (ValueError, AttributeError):
            pass
    readme = _read(zf, base + "README.md") or ""
    info["readme"] = readme[:20000]
    return info


def build_catalog(archive=None):
    """받아 둔 zip에서 목록을 만든다."""
    try:
        with zipfile.ZipFile(archive or _archive()) as zf:
            root = _zip_root(zf)
            market = _read(zf, root + ".claude-plugin/marketplace.json")
            if market is None:
                raise PluginError("플러그인 목록(marketplace.json)을 찾지 못했습니다.")
            entries = json.loads(market).get("plugins") or []
            plugins = [p for p in (_describe(zf, root, e) for e in entries if isinstance(e, dict)) if p]
    except (zipfile.BadZipFile, ValueError, OSError) as e:
        raise PluginError(f"플러그인 목록을 읽지 못했습니다: {e}") from e
    order = {n: i for i, n in enumerate(RECOMMENDED)}
    plugins.sort(key=lambda p: (not p["installable"], p["partner"], order.get(p["name"], 99), p["display_name"].lower()))
    return {"source": REPO_URL, "updated": time.time(), "plugins": plugins}


def download(timeout=60):
    """저장소 zip을 받아 목록을 새로 만든다."""
    _catalog_dir().mkdir(parents=True, exist_ok=True)
    part = _archive().with_suffix(".part")
    try:
        with requests.get(ARCHIVE_URL, stream=True, timeout=(15, timeout), headers={"User-Agent": "POSCHAT"}) as r:
            if r.status_code != 200:
                raise PluginError(f"플러그인 목록을 받지 못했습니다 (HTTP {r.status_code}).")
            size = 0
            with open(part, "wb") as out:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    size += len(chunk)
                    if size > MAX_ARCHIVE:
                        raise PluginError("플러그인 저장소가 너무 큽니다.")
                    out.write(chunk)
        catalog = build_catalog(part)
        part.replace(_archive())
    except requests.RequestException as e:
        raise PluginError(f"플러그인 목록을 받지 못했습니다(네트워크): {e}") from e
    finally:
        part.unlink(missing_ok=True)
    _write_json(_catalog_file(), catalog)
    return catalog


def localize(data):
    """1.19: 목록에 한국어 설명을 붙인다(plugins_ko). 받아 둔 목록 파일은 그대로 두고 돌려줄 때마다 붙인다.

    플러그인: summary(한 줄 소개)가 없으면 번역으로 채운다. 스킬·명령: description_ko. 번역이 없으면 원문만 둔다.
    """
    from plugins_ko import KO

    for p in data.get("plugins", []):
        if not isinstance(p, dict):
            continue
        name = p.get("name", "")
        if not p.get("summary") and KO.get(name):
            p["summary"] = KO[name]
        for kind, prefix in (("skills", ""), ("commands", "cmd:")):
            for item in p.get(kind) or []:
                ko = KO.get(f"{name}/{prefix}{item.get('name', '')}")
                if ko:
                    item["description_ko"] = ko
    return data


def skill_ko(full_name):
    """1.19.1: 설치한 플러그인 스킬·명령('플러그인:이름')의 한국어 설명. 스킬 목록·/ 메뉴가 쓴다. 없으면 ""."""
    from plugins_ko import KO

    plugin, sep, short = str(full_name or "").partition(":")
    if not sep:
        return ""
    return KO.get(f"{plugin}/{short}") or KO.get(f"{plugin}/cmd:{short}") or ""


def catalog(refresh=False):
    """목록(받아 둔 것이 있으면 그것). refresh면 새로 받는다. 한국어 설명을 붙여 돌려준다."""
    with _lock:
        if refresh or not _catalog_file().is_file() or not _archive().is_file():
            return localize(download())
        data = _read_json(_catalog_file(), None)
        if not isinstance(data, dict) or "plugins" not in data:
            return localize(download())
        return localize(data)


def find(name):
    for p in catalog().get("plugins", []):
        if p["name"] == name:
            return p
    raise PluginError(f"플러그인 '{name}'을(를) 목록에서 찾지 못했습니다.")


# ---- 설치·제거 ----

def install(name):
    """받아 둔 zip에서 플러그인 폴더를 데이터 폴더로 푼다(같은 이름이 있으면 바꾼다)."""
    with _lock:
        info = find(name)
        if not info["installable"]:
            raise PluginError("이 플러그인은 다른 회사 저장소에 있어 POSCHAT에서 설치하지 않습니다. 홈페이지에서 확인하세요.")
        target, tmp = plugins_dir() / name, plugins_dir() / f".{name}.installing"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            with zipfile.ZipFile(_archive()) as zf:
                base = _zip_root(zf) + info["path"] + "/"
                total = 0
                for m in zf.infolist():
                    if not m.filename.startswith(base) or m.is_dir():
                        continue
                    rel = m.filename[len(base):]
                    if not rel or not _safe_member(rel) or (m.external_attr >> 16) & 0o170000 == 0o120000:
                        continue  # 경로 밖으로 나가는 이름·심볼릭 링크는 풀지 않는다
                    total += m.file_size
                    if total > MAX_PLUGIN:
                        raise PluginError("플러그인이 너무 큽니다.")
                    out = tmp / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(m) as src, open(out, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            if not (tmp / ".claude-plugin" / "plugin.json").is_file():
                raise PluginError("플러그인 파일이 온전하지 않습니다. 목록을 새로 받은 뒤 다시 설치하세요.")
            shutil.rmtree(target, ignore_errors=True)
            tmp.replace(target)
        except (OSError, zipfile.BadZipFile) as e:
            raise PluginError(f"플러그인을 설치하지 못했습니다: {e}") from e
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        data = state()
        data[name] = {"enabled": True, "version": info["version"], "installed_at": time.time(),
                      "display_name": info["display_name"]}
        _write_json(_state_file(), data)
        return data[name]


def remove(name):
    with _lock:
        if not NAME_RE.match(str(name)):
            raise PluginError("알 수 없는 플러그인입니다.")
        shutil.rmtree(plugins_dir() / name, ignore_errors=True)
        data = state()
        data.pop(name, None)
        _write_json(_state_file(), data)


def set_enabled(name, enabled):
    with _lock:
        data = state()
        if name not in data or not (plugins_dir() / name).is_dir():
            raise PluginError("설치하지 않은 플러그인입니다.")
        data[name]["enabled"] = bool(enabled)
        _write_json(_state_file(), data)
        return data[name]
