# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""내장 MCP 서버 paper: 논문을 찾고, 정보를 보고, 섹션별로 나눠 읽는다.

arXiv API(키 없음)로 찾고 PDF를 받으며, Semantic Scholar API(키 없이도 됨, 요청이 몰리면 잠시 거절)로
arXiv 밖의 논문·인용·한 줄 요약(TLDR)을 얻는다. SEMANTIC_SCHOLAR_API_KEY 환경 변수나 커넥터 → 연구 라이브러리에
넣은 키가 있으면 그 키를 쓴다. search의 source=crossref·openalex는 Crossref·OpenAlex(둘 다 키 없음)에서 찾고,
source=all은 네 곳의 결과를 DOI → arXiv 번호 → 정규화한 제목 순으로 같은 논문끼리 합친다.
PDF는 임시 폴더에 받아 두고 pypdf로 글자를 뽑아 섹션 제목을 찾는다. 작업 폴더에 쓰는 도구는 download뿐이다.
"""
import hashlib
import logging
import os
import re
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from office_mcp import BOOL, INT, READ_ONLY, STR, _new_file, _path, _rel, _schema
from net import ToolFailure, http

ARXIV_API = "https://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1"
CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"
S2_FIELDS = "title,authors,year,venue,abstract,citationCount,referenceCount,tldr,openAccessPdf,externalIds,url"
MAX_PDF_BYTES = 50 * 1024 * 1024
DEFAULT_CHARS = 12000
CACHE_DIR = Path(tempfile.gettempdir()) / "PostechChat-papers"
# arXiv 검색은 단어마다 AND로 묶으므로 흔한 영어 단어는 뺀다
STOPWORDS = {"a", "an", "the", "is", "are", "of", "for", "in", "on", "to", "and", "or", "with", "by", "all", "you",
             "we", "what", "how", "via", "from", "at", "as", "it", "its", "be", "do", "does", "need", "using"}
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5}(?:v\d+)?|[a-z][a-z.\-]+/\d{7}(?:v\d+)?)", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)

LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})
# 논문에서 흔한 번호 없는 섹션 제목(영어·한국어)
KNOWN_HEADINGS = (
    "abstract", "introduction", "related work", "related works", "background", "preliminaries",
    "method", "methods", "methodology", "approach", "model", "experiments", "experiment",
    "experimental setup", "experimental results", "results", "evaluation", "analysis", "discussion",
    "conclusion", "conclusions", "conclusion and future work", "limitations", "future work",
    "acknowledgments", "acknowledgements", "acknowledgment", "references", "bibliography", "appendix",
    "초록", "요약", "서론", "관련 연구", "배경", "연구 방법", "방법", "실험", "실험 결과", "결과", "논의",
    "결론", "참고문헌", "참고 문헌", "부록",
)
UNNUMBERED = {"abstract", "references", "bibliography", "appendix", "acknowledgments", "acknowledgements",
              "acknowledgment", "초록", "요약", "참고문헌", "참고 문헌", "부록"}
NUMBERED_RE = re.compile(r"^((?:\d{1,2})(?:\.\d{1,2}){0,2})\.?\s+([A-Z가-힣][^\n]{1,80})$")
ROMAN_RE = re.compile(r"^((?:X{0,1})(?:IX|IV|V?I{0,3}))\.\s+([A-Z][^\n]{1,80})$")
APPENDIX_RE = re.compile(r"^(?:Appendix\s+)?([A-H](?:\.\d{1,2})?)\.?\s+([A-Z][^\n]{2,80})$")


# ---- 논문 식별 ----

def _identify(paper):
    """사용자가 준 문자열을 ('arxiv'|'doi'|'s2'|'url'|'file', 값)으로 바꾼다."""
    text = str(paper or "").strip()
    if not text:
        raise ToolFailure("paper에 arXiv 번호, DOI, 논문 URL, 또는 작업 폴더의 PDF 경로를 주세요.")
    low = text.lower()
    if low.endswith(".pdf") and not low.startswith(("http://", "https://")):
        return "file", text
    if "arxiv.org" in low or low.startswith("arxiv:"):
        m = ARXIV_ID_RE.search(text.split("arxiv.org", 1)[-1] if "arxiv.org" in low else text[6:])
        if m:
            return "arxiv", re.sub(r"\.pdf$", "", m.group(1))
    if re.fullmatch(ARXIV_ID_RE.pattern, text, re.I):
        return "arxiv", text
    m = DOI_RE.search(text)
    if m and ("doi.org" in low or low.startswith(("10.", "doi:"))):
        doi = m.group(1).rstrip(".")
        arxiv = re.fullmatch(r"10\.48550/arxiv\.(.+)", doi, re.I)  # arXiv가 붙인 DOI
        return ("arxiv", arxiv.group(1)) if arxiv else ("doi", doi)
    if "semanticscholar.org" in low:
        m = re.search(r"([0-9a-f]{40})", low)
        if m:
            return "s2", m.group(1)
    if re.fullmatch(r"[0-9a-f]{40}", low):
        return "s2", low
    if low.startswith(("http://", "https://")):
        return "url", text
    raise ToolFailure(f"논문을 알아볼 수 없습니다: {text}. arXiv 번호(예: 1706.03762), DOI(10.xxxx/...), "
                      "URL, 작업 폴더의 .pdf 경로 중 하나를 주세요. 제목만 안다면 먼저 search로 찾으세요.")


# ---- arXiv ----

def _arxiv_entries(params):
    r = http("GET", ARXIV_API, params=params, timeout=30)
    if r.status_code != 200:
        raise ToolFailure(f"arXiv 검색에 실패했습니다(HTTP {r.status_code}). 잠시 뒤 다시 시도하세요.")
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall("a:entry", ATOM):
        link = e.findtext("a:id", "", ATOM)
        m = ARXIV_ID_RE.search(link.split("/abs/")[-1])
        title = " ".join(e.findtext("a:title", "", ATOM).split())
        if not m or not title or title == "Error":
            continue
        out.append({
            "arxiv": m.group(1),
            "title": title,
            "authors": [a.findtext("a:name", "", ATOM) for a in e.findall("a:author", ATOM)],
            "year": e.findtext("a:published", "", ATOM)[:4],
            "updated": e.findtext("a:updated", "", ATOM)[:10],
            "abstract": " ".join(e.findtext("a:summary", "", ATOM).split()),
            "category": (e.find("arxiv:primary_category", ATOM).get("term")
                         if e.find("arxiv:primary_category", ATOM) is not None else ""),
            "doi": e.findtext("arxiv:doi", "", ATOM),
            "journal": e.findtext("arxiv:journal_ref", "", ATOM),
        })
    return out


def _arxiv_query(query):
    """사람이 쓴 검색어를 arXiv 검색식으로. ti:/au:/abs:/cat: 같은 검색식은 그대로 둔다."""
    if re.search(r"\b(ti|au|abs|cat|all|co|jr|id):", query):
        return query
    words = [w for w in re.findall(r'"[^"]+"|[^\s"]+', query) if w.lower() not in STOPWORDS] or query.split()
    return " AND ".join(f"all:{w}" for w in words)


# ---- Semantic Scholar ----

def _s2(path, params=None, quiet=False):
    """Semantic Scholar GET. quiet이면 실패해도 None을 돌려준다(부가 정보에 쓸 때)."""
    headers = {}
    key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or _s2_key()
    if key:
        headers["x-api-key"] = key
    for attempt in range(3):
        try:
            r = http("GET", S2_API + path, params=params, headers=headers, timeout=20)
        except ToolFailure:
            if quiet:
                return None
            raise
        if r.status_code == 429 and attempt < 2:
            time.sleep(1.5 * (attempt + 1))  # 키 없는 요청은 모두가 함께 쓰는 한도라 자주 잠깐 막힌다
            continue
        break
    if r.status_code == 200:
        return r.json()
    if quiet:
        return None
    if r.status_code == 404:
        raise ToolFailure("Semantic Scholar에서 이 논문을 찾지 못했습니다.")
    if r.status_code == 429:
        raise ToolFailure("Semantic Scholar가 요청이 많다며 거절했습니다(429). 잠시 뒤 다시 시도하거나 "
                          "source를 arxiv로 바꾸세요. 자주 쓰면 무료 API 키를 받아 SEMANTIC_SCHOLAR_API_KEY 환경 변수로 넣으세요.")
    raise ToolFailure(f"Semantic Scholar 요청에 실패했습니다(HTTP {r.status_code}).")


def _s2_key():
    try:
        import secret_store

        return secret_store.get("connector:research:s2_key")
    except Exception:
        return ""


def _s2_id(kind, value):
    if kind == "arxiv":
        return "arXiv:" + re.sub(r"v\d+$", "", value)
    return {"doi": f"DOI:{value}", "s2": value, "url": f"URL:{value}"}[kind]


def _authors(names, limit=6):
    names = [n for n in names if n]
    return ", ".join(names[:limit]) + (f" 외 {len(names) - limit}명" if len(names) > limit else "")


def _s2_line(i, p):
    ids = p.get("externalIds") or {}
    ref = (f"arXiv:{ids['ArXiv']}" if ids.get("ArXiv") else f"DOI:{ids['DOI']}" if ids.get("DOI")
           else p.get("paperId", ""))
    head = f"{i}. {p.get('title') or '(제목 없음)'} ({p.get('year') or '연도 미상'})"
    meta = [_authors([a.get("name") for a in p.get("authors") or []], 4)]
    if p.get("venue"):
        meta.append(p["venue"])
    if p.get("citationCount") is not None:
        meta.append(f"인용 {p['citationCount']}회")
    pdf = (p.get("openAccessPdf") or {}).get("url")
    return f"{head}\n   {' · '.join(m for m in meta if m)}\n   paper: {ref}" + ("  [공개 PDF 있음]" if pdf or ids.get("ArXiv") else "")


# ---- 여러 곳의 검색 결과를 한 형식으로 ----
# {"title", "authors", "year", "venue", "doi", "arxiv", "url", "abstract", "citations", "sources"}

def _norm_title(title):
    return re.sub(r"[^0-9a-z가-힣]+", "", str(title or "").lower())


def _clean_doi(doi):
    doi = str(doi or "").strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi, flags=re.I)
    return doi.lower()


def _record(**fields):
    rec = {"title": "", "authors": [], "year": "", "venue": "", "doi": "", "arxiv": "", "url": "", "abstract": "",
           "citations": None, "sources": []}
    rec.update({k: v for k, v in fields.items() if v not in (None, "", [])})
    rec["doi"] = _clean_doi(rec["doi"])
    m = re.fullmatch(r"10\.48550/arxiv\.(.+)", rec["doi"])
    if m and not rec["arxiv"]:
        rec["arxiv"] = m.group(1)
    rec["arxiv"] = re.sub(r"v\d+$", "", str(rec["arxiv"] or ""))
    rec["year"] = str(rec["year"] or "")[:4]
    return rec


def _from_arxiv(e):
    return _record(title=e["title"], authors=e["authors"], year=e["year"], venue=e.get("journal") or "arXiv",
                   doi=e.get("doi"), arxiv=e["arxiv"], url=f"https://arxiv.org/abs/{e['arxiv']}", abstract=e["abstract"],
                   sources=["arXiv"])


def _from_s2(p):
    ids = p.get("externalIds") or {}
    return _record(title=p.get("title"), authors=[a.get("name") for a in p.get("authors") or []], year=p.get("year"),
                   venue=p.get("venue"), doi=ids.get("DOI"), arxiv=ids.get("ArXiv"), url=p.get("url"),
                   abstract=p.get("abstract"), citations=p.get("citationCount"), sources=["Semantic Scholar"])


def _from_crossref(item):
    authors = [" ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "") for a in item.get("author") or []]
    parts = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
    abstract = re.sub(r"<[^>]+>", "", item.get("abstract") or "").strip()
    return _record(title=" ".join((item.get("title") or [""])[0].split()), authors=authors,
                   year=parts[0] if parts else "", venue=(item.get("container-title") or [""])[0], doi=item.get("DOI"),
                   url=item.get("URL"), abstract=abstract, citations=item.get("is-referenced-by-count"), sources=["Crossref"])


def _openalex_abstract(index):
    if not isinstance(index, dict):
        return ""
    words = sorted((pos, word) for word, positions in index.items() for pos in positions)
    return " ".join(w for _, w in words)


def _from_openalex(w):
    arxiv = ""
    for loc in w.get("locations") or []:
        m = ARXIV_ID_RE.search(str(loc.get("landing_page_url") or "")) if "arxiv.org" in str(loc.get("landing_page_url")) else None
        if m:
            arxiv = m.group(1)
            break
    source = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    return _record(title=w.get("title") or w.get("display_name"),
                   authors=[(a.get("author") or {}).get("display_name") for a in w.get("authorships") or []],
                   year=w.get("publication_year"), venue=source, doi=w.get("doi"), arxiv=arxiv,
                   url=w.get("doi") or w.get("id"), abstract=_openalex_abstract(w.get("abstract_inverted_index")),
                   citations=w.get("cited_by_count"), sources=["OpenAlex"])


def _crossref_search(query, limit):
    r = http("GET", CROSSREF_API, params={"query.bibliographic": query, "rows": limit,
                                          "select": "DOI,title,author,issued,container-title,abstract,is-referenced-by-count,URL"},
             timeout=30)
    if r.status_code != 200:
        raise ToolFailure(f"Crossref 검색에 실패했습니다(HTTP {r.status_code}).")
    return [_from_crossref(i) for i in (r.json().get("message") or {}).get("items") or [] if i.get("title")]


def _openalex_search(query, limit):
    r = http("GET", OPENALEX_API, params={"search": query, "per-page": limit}, timeout=30)
    if r.status_code != 200:
        raise ToolFailure(f"OpenAlex 검색에 실패했습니다(HTTP {r.status_code}).")
    return [_from_openalex(w) for w in r.json().get("results") or [] if w.get("title") or w.get("display_name")]


def merge_records(records):
    """같은 논문(DOI → arXiv 번호 → 정규화한 제목 순)을 하나로 합친다. 먼저 나온 값을 지키고 빈 칸을 채운다."""
    merged, index = [], {}
    for rec in records:
        keys = [k for k in (("doi", rec["doi"]), ("arxiv", rec["arxiv"]), ("title", _norm_title(rec["title"]))) if k[1]]
        target = next((index[k] for k in keys if k in index), None)
        if target is None:
            target = dict(rec, authors=list(rec["authors"]), sources=list(rec["sources"]))
            merged.append(target)
        else:
            for field in ("title", "year", "venue", "doi", "arxiv", "url", "abstract"):
                if not target[field] and rec[field]:
                    target[field] = rec[field]
            if not target["authors"]:
                target["authors"] = list(rec["authors"])
            if rec["citations"] is not None:
                target["citations"] = max(target["citations"] or 0, rec["citations"])
            target["sources"] += [s for s in rec["sources"] if s not in target["sources"]]
        for k in (("doi", target["doi"]), ("arxiv", target["arxiv"]), ("title", _norm_title(target["title"]))):
            if k[1]:
                index[k] = target
    return merged


def _paper_ref(rec):
    return f"arXiv:{rec['arxiv']}" if rec["arxiv"] else (f"DOI:{rec['doi']}" if rec["doi"] else rec["url"])


def format_records(records, title):
    lines = [title, ""]
    for i, rec in enumerate(records, 1):
        meta = [_authors(rec["authors"], 4)]
        if rec["venue"]:
            meta.append(rec["venue"])
        if rec["citations"] is not None:
            meta.append(f"인용 {rec['citations']}회")
        lines.append(f"{i}. {rec['title'] or '(제목 없음)'} ({rec['year'] or '연도 미상'})")
        lines.append(f"   {' · '.join(m for m in meta if m)}")
        ids = [f"DOI: {rec['doi']}" if rec["doi"] else "", f"arXiv: {rec['arxiv']}" if rec["arxiv"] else ""]
        lines.append(f"   {' · '.join(x for x in ids if x) or 'ID 없음'}" + (f" · {rec['url']}" if rec["url"] else ""))
        if rec["abstract"]:
            lines.append(f"   초록: {rec['abstract'][:300]}{'…' if len(rec['abstract']) > 300 else ''}")
        lines.append(f"   출처: {', '.join(rec['sources'])} · paper: {_paper_ref(rec)}")
    lines.append("\n자세히 보려면 info, 본문은 read에 paper 값을 넘기세요.")
    return "\n".join(lines)


def search_all(query, limit):
    """arXiv·Semantic Scholar·Crossref·OpenAlex를 함께 찾아 합친다. 실패한 곳은 건너뛰고 알린다."""
    found, failed = [], []
    calls = [
        ("arXiv", lambda: [_from_arxiv(e) for e in _arxiv_entries({"search_query": _arxiv_query(query), "max_results": limit})]),
        ("Semantic Scholar", lambda: [_from_s2(p) for p in (_s2("/paper/search", {
            "query": query, "limit": limit,
            "fields": "title,authors,year,venue,abstract,citationCount,externalIds,url"}) or {}).get("data") or []]),
        ("Crossref", lambda: _crossref_search(query, limit)),
        ("OpenAlex", lambda: _openalex_search(query, limit)),
    ]
    for name, call in calls:
        try:
            found.append(call())
        except ToolFailure as e:
            failed.append(f"{name}: {e}")
    # 각 출처의 순위를 섞어 앞쪽 결과가 고루 보이게 한다
    interleaved = [rec for group in zip_longest_all(found) for rec in group]
    return merge_records(interleaved), failed


def zip_longest_all(groups):
    longest = max((len(g) for g in groups), default=0)
    for i in range(longest):
        yield [g[i] for g in groups if i < len(g)]


# ---- 도구: search / info / related ----

def search(query, limit=8, source="arxiv", sort="relevance"):
    query = str(query or "").strip()
    if not query:
        raise ToolFailure("query가 비어 있습니다.")
    limit = max(1, min(25, int(limit or 8)))
    if source == "all":
        records, failed = search_all(query, limit)
        if not records:
            return f"'{query}'에 맞는 논문이 없습니다." + (f" (실패: {'; '.join(failed)})" if failed else "")
        text = format_records(records[:limit * 2], f"통합 검색 '{query}' — {len(records)}편(중복을 합친 결과)")
        return text + (f"\n\n일부 출처는 실패했습니다: {'; '.join(failed)}" if failed else "")
    if source == "crossref":
        records = merge_records(_crossref_search(query, limit))
        return format_records(records, f"Crossref 검색 '{query}' ({len(records)}건)") if records else \
            f"Crossref에서 '{query}'에 맞는 논문이 없습니다."
    if source == "openalex":
        records = merge_records(_openalex_search(query, limit))
        return format_records(records, f"OpenAlex 검색 '{query}' ({len(records)}건)") if records else \
            f"OpenAlex에서 '{query}'에 맞는 논문이 없습니다."
    if source in ("scholar", "semantic_scholar", "s2"):
        data = _s2("/paper/search", {"query": query, "limit": limit,
                                     "fields": "title,authors,year,venue,citationCount,externalIds,openAccessPdf"})
        papers = data.get("data") or []
        if not papers:
            return f"'{query}'에 맞는 논문이 없습니다."
        return (f"Semantic Scholar 검색 '{query}' (전체 약 {data.get('total', len(papers))}건 중 {len(papers)}건)\n\n"
                + "\n".join(_s2_line(i, p) for i, p in enumerate(papers, 1))
                + "\n\n자세히 보려면 info, 본문은 read에 paper 값을 넘기세요.")
    order = {"relevance": "relevance", "date": "submittedDate", "updated": "lastUpdatedDate"}.get(sort, "relevance")
    entries = []
    if order == "relevance" and len(query.split()) >= 2 and ":" not in query and '"' not in query:
        # 제목을 그대로 넣은 경우가 많다: 제목 일치를 먼저 보이고 나머지를 단어 검색으로 채운다
        entries = _arxiv_entries({"search_query": f'ti:"{query}"', "max_results": limit})
    seen = {e["arxiv"] for e in entries}
    if len(entries) < limit:
        more = _arxiv_entries({"search_query": _arxiv_query(query), "max_results": limit,
                               "sortBy": order, "sortOrder": "descending"})
        entries += [e for e in more if e["arxiv"] not in seen][:limit - len(entries)]
    if not entries:
        return f"arXiv에서 '{query}'에 맞는 논문이 없습니다. 다른 표현이나 source=\"scholar\"로 찾아보세요."
    lines = [f"arXiv 검색 '{query}' ({len(entries)}건)\n"]
    for i, e in enumerate(entries, 1):
        abstract = e["abstract"][:280] + ("…" if len(e["abstract"]) > 280 else "")
        lines.append(f"{i}. {e['title']} ({e['year']}, {e['category']})\n   {_authors(e['authors'], 4)}\n"
                     f"   paper: {e['arxiv']}\n   {abstract}")
    lines.append("\n자세히 보려면 info, 본문은 read에 paper 값을 넘기세요.")
    return "\n".join(lines)


def info(paper):
    kind, value = _identify(paper)
    if kind == "file":
        p = _existing_pdf(value)
        pages = _pages(p)
        return (f"작업 폴더의 PDF: {_rel(p)} ({len(pages)}쪽)\n\n" + _outline_text(_sections(pages))
                + "\n\n본문은 read로 읽으세요.")
    lines = []
    ax = _arxiv_entries({"id_list": value, "max_results": 1}) if kind == "arxiv" else []
    # arXiv 정보가 있으면 Semantic Scholar(인용 수·TLDR)는 덤이다. URL은 Semantic Scholar가 아는 사이트만 된다
    s2 = _s2("/paper/" + _s2_id(kind, value), {"fields": S2_FIELDS}, quiet=bool(ax) or kind == "url")
    if not ax and not s2:
        raise ToolFailure("논문 정보를 찾지 못했습니다.")
    base = ax[0] if ax else {}
    s2 = s2 or {}
    ids = s2.get("externalIds") or {}
    title = base.get("title") or s2.get("title")
    lines.append(f"제목: {title}")
    names = base.get("authors") or [a.get("name") for a in s2.get("authors") or []]
    lines.append(f"저자: {_authors(names, 10)}")
    lines.append(f"연도: {base.get('year') or s2.get('year') or '미상'}"
                 + (f" · 게재: {s2['venue']}" if s2.get("venue") else "")
                 + (f" · {base['journal']}" if base.get("journal") else ""))
    if s2.get("citationCount") is not None:
        lines.append(f"인용: {s2['citationCount']}회 · 참고문헌: {s2.get('referenceCount', '?')}편")
    arxiv = base.get("arxiv") or ids.get("ArXiv")
    doi = base.get("doi") or ids.get("DOI")
    links = []
    if arxiv:
        links.append(f"https://arxiv.org/abs/{arxiv}")
    if doi:
        links.append(f"https://doi.org/{doi}")
    if s2.get("url"):
        links.append(s2["url"])
    lines.append("링크: " + " · ".join(links))
    pdf = _pdf_url(kind, value, s2)
    lines.append("PDF: " + (pdf or "공개 PDF를 찾지 못했습니다(학교 도서관 등에서 받아 작업 폴더에 넣으면 read로 읽을 수 있습니다)."))
    tldr = (s2.get("tldr") or {}).get("text")
    if tldr:
        lines.append(f"\n한 줄 요약(TLDR, Semantic Scholar 자동 생성): {tldr}")
    abstract = base.get("abstract") or s2.get("abstract")
    if abstract:
        lines.append(f"\n초록:\n{abstract}")
    return "\n".join(lines)


def related(paper, kind="references", limit=15):
    k, value = _identify(paper)
    if k == "file":
        raise ToolFailure("작업 폴더의 PDF는 인용 관계를 찾을 수 없습니다. arXiv 번호나 DOI를 주세요.")
    which = "citations" if kind in ("citations", "cited_by") else "references"
    limit = max(1, min(50, int(limit or 15)))
    data = _s2(f"/paper/{_s2_id(k, value)}/{which}",
               {"limit": limit, "fields": "title,authors,year,venue,citationCount,externalIds,openAccessPdf"})
    key = "citedPaper" if which == "references" else "citingPaper"
    papers = [row.get(key) or {} for row in data.get("data") or []]
    papers = [p for p in papers if p.get("title")]
    if which == "references":
        papers.sort(key=lambda p: p.get("citationCount") or 0, reverse=True)  # 많이 인용된 배경 논문부터
    if not papers:
        return "목록이 비어 있습니다(Semantic Scholar에 아직 정리되지 않았을 수 있습니다)."
    title = "이 논문이 참고한 논문(많이 인용된 순)" if which == "references" else "이 논문을 인용한 논문"
    return f"{title} {len(papers)}편\n\n" + "\n".join(_s2_line(i, p) for i, p in enumerate(papers, 1))


# ---- PDF 받기·읽기 ----

def _pdf_url(kind, value, s2=None):
    if kind == "arxiv":
        return f"https://arxiv.org/pdf/{value}"
    if kind == "url":
        m = ARXIV_ID_RE.search(value) if "arxiv.org" in value else None
        return f"https://arxiv.org/pdf/{m.group(1)}" if m else value
    if s2 is None:
        s2 = _s2("/paper/" + _s2_id(kind, value), {"fields": "externalIds,openAccessPdf"})
    ids = s2.get("externalIds") or {}
    if ids.get("ArXiv"):
        return f"https://arxiv.org/pdf/{ids['ArXiv']}"
    return (s2.get("openAccessPdf") or {}).get("url") or None


def _existing_pdf(path):
    p = _path(path, (".pdf",))
    if not p.is_file():
        raise ToolFailure(f"파일이 없습니다: {_rel(p)}")
    return p


def _get_public(url, hops=5):
    """2.0: 리디렉션을 한 번씩 따라가며 주소마다 공개 주소인지 확인한다(내부망·이 PC의 서비스로 보내지 않는다)."""
    import web_research
    from urllib.parse import urljoin

    for _ in range(hops + 1):
        try:
            url = web_research.check_url(url)
        except web_research.WebError as e:
            raise ToolFailure(str(e))
        r = http("GET", url, timeout=60, stream=True, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            url = urljoin(url, r.headers["Location"])
            r.close()
            continue
        return r
    raise ToolFailure("리디렉션이 너무 많아 PDF를 받지 않았습니다.")


def _fetch_pdf(kind, value):
    """PDF 파일 경로. 작업 폴더의 파일이면 그대로, 인터넷이면 임시 폴더에 받아 둔 것을 쓴다."""
    if kind == "file":
        return _existing_pdf(value)
    url = _pdf_url(kind, value)
    if not url:
        raise ToolFailure("공개된 PDF를 찾지 못했습니다. 학교 도서관 등에서 PDF를 받아 작업 폴더에 넣은 뒤 그 경로로 다시 시도하세요.")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".pdf")
    if cached.is_file() and cached.stat().st_size > 0:
        return cached
    r = _get_public(url)
    if r.status_code != 200:
        raise ToolFailure(f"PDF를 받지 못했습니다(HTTP {r.status_code}): {url}")
    data = bytearray()
    for chunk in r.iter_content(65536):
        data += chunk
        if len(data) > MAX_PDF_BYTES:
            raise ToolFailure("PDF가 50MB보다 커서 받지 않았습니다.")
    if not data.startswith(b"%PDF"):
        raise ToolFailure(f"받은 파일이 PDF가 아닙니다(로그인이나 구독이 필요한 페이지일 수 있습니다): {url}")
    tmp = cached.with_suffix(".part")
    tmp.write_bytes(bytes(data))
    os.replace(tmp, cached)
    return cached


_PAGES = {}  # 파일 경로 -> (수정 시각, 쪽별 글자). 같은 논문을 섹션별로 여러 번 읽으므로 기억해 둔다


def _pages(path):
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # 글꼴 경고가 많아 로그를 어지럽힌다
    key, mtime = str(path), path.stat().st_mtime
    if key in _PAGES and _PAGES[key][0] == mtime:
        return _PAGES[key][1]
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            text = re.sub(r"[ \t]{2,}", " ", text)
            text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # 줄 끝에서 끊긴 단어를 잇는다
            text = text.translate(LIGATURES)
            pages.append(text.strip())
    except Exception as e:
        raise ToolFailure(f"PDF에서 글자를 뽑지 못했습니다: {type(e).__name__}: {e}")
    if not any(pages):
        raise ToolFailure("PDF에 글자가 없습니다. 스캔한 이미지 PDF일 수 있습니다.")
    _PAGES[key] = (mtime, pages)
    return pages


def _heading(line, last_top, after_refs):
    """섹션 제목이면 (번호, 제목), 아니면 None."""
    line = line.strip()
    if not 2 < len(line) < 90 or line.endswith((".", ",", ";", ":")):
        return None
    if line.lower() in KNOWN_HEADINGS:
        # 번호를 매기는 논문에서 번호 없는 'Model' 같은 줄은 표·그림의 글자다
        return ("", line) if not last_top or line.lower() in UNNUMBERED else None
    if after_refs:
        m = APPENDIX_RE.match(line)
        return (m.group(1), m.group(2)) if m and len(m.group(2).split()) <= 10 else None
    m = NUMBERED_RE.match(line) or ROMAN_RE.match(line)
    if not m or not m.group(1):
        return None
    num, title = m.group(1), m.group(2).strip()
    words = title.split()
    if len(words) > 10 or title.endswith(".") or sum(c.isdigit() for c in title) > len(title) / 3:
        return None  # 본문 문장, 표의 숫자 줄
    if num[0].isdigit():
        top = int(num.split(".")[0])
        if top < last_top or top > last_top + 2 or top > 20:
            return None  # 번호가 거꾸로 가거나 건너뛰면 목록·표의 숫자다
    return num, title


def _sections(pages):
    """[(번호, 제목, 시작 쪽, 줄 목록)]. 제목을 못 찾으면 쪽 단위로 나눈 것 하나."""
    sections, current, last_top, after_refs = [], None, 0, False
    for page_no, text in enumerate(pages, 1):
        for line in text.split("\n"):
            found = _heading(line, last_top, after_refs)
            if found:
                num, title = found
                if num[:1].isdigit():
                    last_top = int(num.split(".")[0])
                if title.lower().startswith(("references", "bibliography", "참고")):
                    after_refs = True
                current = [num, title, page_no, []]
                sections.append(current)
                continue
            if current is None:
                current = ["", "(앞부분: 제목·저자)", page_no, []]
                sections.append(current)
            current[3].append(line)
    return sections


def _outline_text(sections):
    if len(sections) <= 1:
        return "목차: 섹션 제목을 찾지 못했습니다. pages로 쪽을 지정해 읽으세요."
    lines = ["목차 (section에 번호나 제목을 넣어 읽으세요)"]
    for num, title, page, body in sections:
        indent = "  " * (num.count(".") if num[:1].isdigit() else 0)
        size = sum(len(x) for x in body)
        lines.append(f"{indent}- {(num + ' ') if num else ''}{title}  (p.{page}, 약 {size:,}자)")
    return "\n".join(lines)


def _clip(text, max_chars, more_hint):
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n…(분량이 많아 {max_chars:,}자에서 잘랐습니다. {more_hint})"


def _parse_pages(pages, total):
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", str(pages))
    if not m:
        raise ToolFailure("pages는 \"3\" 또는 \"3-5\" 형식으로 주세요.")
    a = int(m.group(1))
    b = int(m.group(2) or a)
    if not 1 <= a <= b:
        raise ToolFailure("pages 범위가 잘못되었습니다.")
    if a > total:
        raise ToolFailure(f"이 PDF는 {total}쪽입니다.")
    return a, min(b, total)


def read(paper, section=None, pages=None, max_chars=DEFAULT_CHARS):
    kind, value = _identify(paper)
    path = _fetch_pdf(kind, value)
    pages_text = _pages(path)
    total = len(pages_text)
    max_chars = max(2000, min(40000, int(max_chars or DEFAULT_CHARS)))
    sections = _sections(pages_text)
    if pages:
        a, b = _parse_pages(pages, total)
        body = "\n\n".join(f"--- 페이지 {i} ---\n{pages_text[i - 1]}" for i in range(a, b + 1))
        nxt = f"pages=\"{b + 1}-{min(total, b + 1 + (b - a))}\"로 이어서 읽으세요." if b < total else "마지막 쪽입니다."
        return f"[{paper}] {a}–{b}쪽 / 전체 {total}쪽\n\n" + _clip(body, max_chars, "범위를 좁혀 다시 읽으세요.") + f"\n\n({nxt})"
    if section:
        want = str(section).strip().lower().rstrip(".")
        hit = None
        for i, (num, title, _, _) in enumerate(sections):
            if want == num.lower() or want == title.lower() or want == f"{num} {title}".lower().strip():
                hit = i
                break
        if hit is None:
            hit = next((i for i, (_, title, _, _) in enumerate(sections) if want in title.lower()), None)
        if hit is None:
            raise ToolFailure(f"'{section}' 섹션을 찾지 못했습니다.\n\n" + _outline_text(sections))
        num, title, page, _ = sections[hit]
        # 바로 뒤에 이어지는 하위 섹션(3 → 3.1, 3.2)까지 함께 읽는다
        parts = [sections[hit]]
        for s in sections[hit + 1:]:
            if not (num[:1].isdigit() and s[0].startswith(num + ".")):
                break
            parts.append(s)
        body = "\n\n".join(f"## {(n + ' ') if n else ''}{t} (p.{pg})\n" + "\n".join(lines).strip()
                           for n, t, pg, lines in parts)
        following = sections[hit + len(parts)] if hit + len(parts) < len(sections) else None
        nxt = f"다음 섹션: {(following[0] + ' ') if following[0] else ''}{following[1]}" if following else "마지막 섹션입니다."
        last = following[2] if following else total
        more = f"이 섹션은 {page}~{last}쪽이니 pages=\"{page}-{last}\"처럼 쪽을 나눠 읽거나 하위 섹션 번호로 읽으세요."
        return f"[{paper}] {(num + ' ') if num else ''}{title}\n\n" + _clip(body, max_chars, more) + f"\n\n({nxt})"
    # 처음 읽을 때: 목차와 앞부분(초록·서론)
    head = []
    for num, title, page, lines in sections:
        head.append(f"## {(num + ' ') if num else ''}{title} (p.{page})\n" + "\n".join(lines).strip())
        if sum(len(h) for h in head) > max_chars:
            break
    source = _rel(path) if kind == "file" else f"{kind}:{value}"
    return (f"[{source}] 전체 {total}쪽\n\n{_outline_text(sections)}\n\n--- 앞부분 ---\n"
            + _clip("\n\n".join(head), max_chars, "section이나 pages로 이어서 읽으세요."))


def download(paper, path=None, overwrite=False):
    kind, value = _identify(paper)
    if kind == "file":
        raise ToolFailure("이미 작업 폴더에 있는 PDF입니다.")
    src = _fetch_pdf(kind, value)
    if not path:
        name = re.sub(r"[^\w.\-]+", "_", value.split("/")[-1] if kind != "arxiv" else value.replace("/", "_"))[:80]
        path = f"papers/{name}.pdf"
    p = _new_file(path, (".pdf",), overwrite)
    p.write_bytes(src.read_bytes())
    return f"{_rel(p)}에 저장했습니다 ({p.stat().st_size / 1024 / 1024:.1f}MB, {len(_pages(p))}쪽)."


PAPER_HELP = "paper: arXiv 번호(예: 1706.03762)·arXiv/DOI/논문 URL·DOI(10.xxxx/...)·작업 폴더의 .pdf 경로"

TOOLS = {
    "search": (search, "논문을 찾습니다. source: arxiv(기본, 최신 프리프린트) | scholar(Semantic Scholar, 학회·저널 논문 포함, "
                       "인용 수) | crossref | openalex | all(네 곳을 함께 찾아 DOI·arXiv 번호·제목으로 중복을 합침). "
                       "sort(arxiv만): relevance|date. 결과의 paper 값을 다른 도구에 넘기세요.",
               _schema({"query": STR, "limit": INT, "source": STR, "sort": STR}, ["query"]), READ_ONLY),
    "info": (info, "논문의 제목·저자·게재처·인용 수·링크·한 줄 요약(TLDR)·초록을 봅니다. 읽기 전에 개요를 잡을 때 쓰세요. " + PAPER_HELP,
             _schema({"paper": STR}, ["paper"]), READ_ONLY),
    "read": (read, "논문 PDF 본문을 읽습니다. 처음에는 section·pages 없이 불러 목차와 앞부분(초록·서론)을 보고, "
                   "그다음 section(번호나 제목, 예: \"3\", \"Method\")이나 pages(\"4-6\")로 나눠 읽으세요. "
                   "max_chars 기본 12000. " + PAPER_HELP,
             _schema({"paper": STR, "section": STR, "pages": STR, "max_chars": INT}, ["paper"]), READ_ONLY),
    "related": (related, "kind=references(이 논문이 참고한 논문, 배경 지식용) | citations(이 논문을 인용한 후속 연구). "
                         "arXiv 번호나 DOI가 필요합니다.",
                _schema({"paper": STR, "kind": STR, "limit": INT}, ["paper"]), READ_ONLY),
    "download": (download, "논문 PDF를 작업 폴더에 저장합니다(기본 papers/<번호>.pdf). " + PAPER_HELP,
                 _schema({"paper": STR, "path": STR, "overwrite": BOOL}, ["paper"])),
}
