# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""논문 읽기(1.14) 화면 API: main.Bridge가 상속한다. PDF 다루기는 paper.py가 맡는다.

화면(web/paper.js) → paper_*(...) 호출. 열린 논문은 에이전트도 paper_read로 읽는다(_paper_for_agent).
"""
import base64
import re
import uuid

import attachments
import connectors
import paper
import storage

ASK_PAGE = "이 쪽의 내용을 쉽게 설명해 줘. 핵심 주장과 근거를 쪽 번호와 함께 알려 줘."
ASK_SELECTION = "선택한 부분을 쉽게 설명해 줘. 앞뒤 맥락이 필요하면 짚어 줘."
ASK_FIGURE = "이 그림(표·수식)이 무엇을 보여 주는지 설명해 줘. 축·기호·단위와 핵심 결론을 짚어 줘."
ASK_SUMMARY = ("이 논문을 요약해 줘. 연구 질문, 방법, 실험 조건, 주요 결과, 한계를 나눠 쓰고 "
               "주장마다 (p. N)처럼 쪽 번호를 달아 줘.")
ASK_COMPARE = ("첨부한 논문들을 비교해 줘. 먼저 표로 정리해 줘(열: 논문, 연구 질문, 데이터·실험 조건, 방법, 주요 결과(수치), "
               "한계). 칸마다 근거 쪽을 (논문 짧은 이름 p. N)처럼 달고, 첨부에 없는 내용은 '확인 안 됨'으로 적어 줘. "
               "표 아래에 공통점·차이점과 어떤 상황에 어떤 방법이 맞는지 짧게 정리해 줘.")


class PaperApi:
    _paper_current = None   # 화면에 열린 논문의 doc id

    def _paper_call(self, fn):
        try:
            return {"ok": True, **(fn() or {})}
        except paper.PaperError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            import research_library

            if isinstance(e, (research_library.LibraryError, attachments.AttachmentError)):
                return {"ok": False, "error": str(e)}
            return {"ok": False, "error": f"논문을 다루지 못했습니다: {type(e).__name__}: {e}"}

    def _paper_attach(self, name, data, mime_text=True):
        attach_id = uuid.uuid4().hex
        raw = data.encode("utf-8") if mime_text else data
        return attachments.upload_chunk(attach_id, name, 0, base64.b64encode(raw).decode("ascii"), True)

    def _paper_opened(self, doc):
        self._paper_current = doc["id"]
        with self._lock:
            paper.remember(self._config, doc)
            storage.save_config(self._config)
        return {"doc": doc}

    # ---- 화면 ----

    def paper_state(self):
        """논문 화면 첫 상태: 최근 연 논문, 라이브러리 논문(열 수 있는 것 표시), 열린 논문."""
        import research_library

        papers = []
        for p in research_library.search("", None, None, limit=500):
            papers.append({"id": p["id"], "title": p.get("title") or "(제목 없음)", "year": p.get("year"),
                           "authors": (p.get("authors") or [])[:3], "has_pdf": bool(p.get("pdf")),
                           "arxiv": p.get("arxiv") or "", "tags": p.get("tags") or []})
        current = None
        if self._paper_current:
            try:
                current = paper.get(self._paper_current)
            except paper.PaperError:
                current = None
        return {"ok": True, "recent": paper.recent(self._config), "library": papers, "current": current,
                "research": connectors.feature_enabled(self._config, "research")}

    def paper_open(self, source):
        """source: {"pid"} 라이브러리 논문 · {"path"} 최근 문서 · {"upload_id", "name"} 화면에서 고른 파일 ·
        {"url"} PDF 주소 또는 arXiv 번호."""
        source = source or {}

        def go():
            import research_library

            if source.get("pid"):
                p = research_library.get(source["pid"])
                path = paper.library_pdf(p, workspace=self._workspace())
                return self._paper_opened(paper.register(path, title=p.get("title") or "", pid=p["id"], source="library"))
            if source.get("path"):
                known = {r["path"]: r for r in paper.recent(self._config)}
                if source["path"] not in known:  # 화면이 아무 경로나 열지 못하게: 최근 목록에 있는 것만
                    raise paper.PaperError("최근 목록에 없는 파일입니다. 'PDF 열기'로 다시 고르세요.")
                r = known[source["path"]]
                return self._paper_opened(paper.register(r["path"], title=r.get("title") or "", pid=r.get("pid"),
                                                         source="recent"))
            if source.get("upload_id"):
                part = paper.pdf_dir() / ".incoming" / f"{source['upload_id']}.part"
                if not re.fullmatch(r"[0-9a-f]{16,40}", str(source["upload_id"])) or not part.is_file():
                    raise paper.PaperError("고른 파일을 찾지 못했습니다. 다시 고르세요.")
                try:
                    path = paper.import_file(part, source.get("name") or "paper.pdf")
                finally:
                    part.unlink(missing_ok=True)
                return self._paper_opened(paper.register(path, source="file"))
            if source.get("url"):
                text = str(source["url"]).strip()
                arxiv = paper.arxiv_id(re.sub(r"^arxiv:\s*", "", text, flags=re.I))
                if arxiv:
                    url, name = paper.ARXIV_PDF.format(arxiv), f"arXiv-{arxiv}.pdf"
                else:
                    m = re.match(r"^https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", text, re.I)
                    url = paper.ARXIV_PDF.format(m.group(1)) if m else text
                    name = f"arXiv-{m.group(1)}.pdf" if m else re.sub(r"[?#].*$", "", text).rstrip("/").rsplit("/", 1)[-1]
                    if not m:
                        # 2.0: 주소의 마지막 부분만 이름으로 쓰면 openreview.net/pdf?id=AAA와 ?id=BBB가 같은 pdf.pdf가 되어
                        # 두 번째 논문을 열 때 첫 논문이 열렸다. 주소 전체의 해시를 붙인다
                        import hashlib
                        name = f"{name.removesuffix('.pdf')[:60]}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]}.pdf"
                dest = paper.pdf_dir() / paper._safe_stem(name.removesuffix(".pdf"))
                dest = dest.with_name(dest.name + ".pdf")
                if not dest.is_file():
                    paper.download(url, dest)
                return self._paper_opened(paper.register(dest, source="url"))
            raise paper.PaperError("열 논문을 고르세요.")
        return self._paper_call(go)

    def paper_upload(self, upload_id, offset, data_b64, last):
        return self._paper_call(lambda: {"done": paper.upload_chunk(upload_id, offset, data_b64, last) is not None})

    def paper_chunk(self, doc_id, offset=0):
        return self._paper_call(lambda: paper.read_chunk(doc_id, offset))

    def paper_close(self):
        self._paper_current = None
        return {"ok": True}

    def paper_attach(self, doc_id, kind="page", page=1, text=""):
        """채팅 첨부 만들기. kind: selection(화면에서 고른 글) · page(그 쪽) · paper(요약용 발췌)."""
        def go():
            doc = paper.get(doc_id)
            texts = paper.page_texts(doc["path"])
            pg = max(1, min(len(texts), int(page or 1)))
            if kind == "selection":
                sel = re.sub(r"\s+\n", "\n", str(text or "")).strip()
                if not sel:
                    raise paper.PaperError("PDF에서 선택한 글이 없습니다. 묻고 싶은 부분을 먼저 드래그하세요.")
                body = f"[p. {pg}] (선택한 부분)\n{sel[:paper.MAX_READ_CHARS]}"
                context = paper.pages_markdown(texts, [pg], 6000)
                content = f"{body}\n\n--- 같은 쪽 전체(맥락) ---\n{context}"
                pages, label, ask = [pg], "선택", ASK_SELECTION
            elif kind == "page":
                content, pages, label, ask = paper.pages_markdown(texts, [pg]), [pg], f"p{pg}", ASK_PAGE
            elif kind == "paper":
                content = paper.digest(texts, attachments.MAX_TEXT_CHARS - 500)
                pages, label, ask = None, "논문", ASK_SUMMARY
            else:
                raise paper.PaperError("알 수 없는 첨부 종류입니다.")
            head = f"# {doc['title']}\n출처: {paper.cite(doc)} · 전체 {len(texts)}쪽\n\n"
            wrapped = connectors.wrap_untrusted(head + content, paper.source_label(doc, pages))
            title = re.sub(r"\s+", " ", doc["title"])[:50]
            item = self._paper_attach(f"{label} - {title}.md", wrapped)
            return {"attachment": item, "question": ask}
        return self._paper_call(go)

    def paper_attach_image(self, doc_id, page, data_b64):
        """화면에서 잘라 낸 영역(그림·표·수식)을 PNG 첨부로 만든다."""
        def go():
            doc = paper.get(doc_id)
            raw = base64.b64decode(str(data_b64 or "").split(",", 1)[-1])
            if not raw.startswith(b"\x89PNG"):
                raise paper.PaperError("잘라 낸 영역을 이미지로 만들지 못했습니다.")
            if len(raw) > attachments.MAX_BYTES:
                raise paper.PaperError("잘라 낸 영역이 너무 큽니다. 더 작게 고르세요.")
            title = re.sub(r"\s+", " ", doc["title"])[:40]
            item = self._paper_attach(f"그림 p{int(page or 1)} - {title}.png", raw, mime_text=False)
            return {"attachment": item, "question": f"{ASK_FIGURE} (출처: {paper.cite(doc, int(page or 1))})"}
        return self._paper_call(go)

    def paper_compare(self, pids):
        """라이브러리 논문 여러 편을 비교할 첨부(논문마다 실험·결과 쪽 발췌)와 질문을 만든다."""
        def go():
            import research_library

            ids = [str(i) for i in (pids or []) if i][:paper.MAX_COMPARE]
            if len(ids) < 2:
                raise paper.PaperError("비교할 논문을 두 편 이상 고르세요.")
            budget = min(attachments.MAX_TEXT_CHARS, attachments.MAX_TOTAL_CHARS // len(ids)) - 400
            items, skipped = [], []
            for pid in ids:
                try:
                    p = research_library.get(pid)
                except research_library.LibraryError:
                    continue
                title = p.get("title") or pid
                try:
                    path = paper.library_pdf(p, workspace=self._workspace())
                    content = paper.digest(paper.page_texts(path), budget)
                    label = f"논문 PDF '{title}'"
                except paper.PaperError:
                    if not p.get("abstract"):
                        skipped.append(title)
                        continue
                    content = f"(PDF 없음 — 초록만)\n{p['abstract']}"
                    label = f"논문 초록 '{title}'"
                head = f"# {title}\n{research_library.format_paper(p)}\n\n"
                short = re.sub(r"[^\w가-힣 .-]", "", title)[:40]
                items.append(self._paper_attach(f"비교 - {short}.md", connectors.wrap_untrusted(head + content, label)))
            if len(items) < 2:
                raise paper.PaperError("PDF나 초록이 있는 논문이 두 편 이상 있어야 비교할 수 있습니다.")
            return {"attachments": items, "question": ASK_COMPARE, "skipped": skipped}
        return self._paper_call(go)

    def paper_save(self, doc_id):
        """열린 PDF를 연구 라이브러리에 더한다(PDF 정보에서 DOI·arXiv를 찾으면 메타데이터도 채운다)."""
        def go():
            import research_library
            import research_mcp

            doc = paper.get(doc_id)
            if doc.get("pid"):
                return {"pid": doc["pid"], "already": True}
            if not connectors.feature_enabled(self._config, "research"):
                return {"need_feature": "research", "saved": False}
            meta = research_library.pdf_metadata(doc["path"])
            ident = f"arXiv:{meta['arxiv']}" if meta.get("arxiv") else meta.get("doi")
            if ident:
                try:
                    meta = {**research_mcp.lookup(ident), "pdf": doc["path"]}
                except Exception:
                    pass
            meta["pdf"] = doc["path"]
            meta.setdefault("title", doc["title"])
            meta["tags"] = list(meta.get("tags") or []) + ["PDF에서"]
            saved = research_library.add(meta)[0]
            doc["pid"] = saved["id"]
            return {"pid": saved["id"], "title": saved.get("title")}
        res = self._paper_call(go)
        if res.get("ok") and res.get("need_feature"):
            return {"ok": False, "need_feature": "research",
                    "error": "연구 라이브러리가 꺼져 있습니다. 사이드바의 연구 라이브러리에서 켠 뒤 다시 시도하세요."}
        return res

    # 에이전트가 쓴다(main.Bridge._work가 Agent에 넘긴다)
    def _paper_for_agent(self):
        if not self._paper_current:
            return None
        try:
            return dict(paper.get(self._paper_current), workspace=self._workspace())
        except paper.PaperError:
            return None
