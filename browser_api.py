# SPDX-FileCopyrightText: 2026 Beomjoon Kim
# SPDX-License-Identifier: AGPL-3.0-only
"""브라우저(1.13) 화면 API: main.Bridge가 상속한다. 웹페이지 뷰 자체는 browser.py가 다룬다.

화면(web/browser.js) → browser_*(...) 호출, 브라우저 → 화면은 {"type": "browser"} 이벤트.
"""
import base64
import sys
import uuid

import attachments
import browser
import connectors

# 안드로이드는 android_main이 이 값을 정한다(Kotlin WebView를 다루는 백엔드 만들기).
android_factory = None


class BrowserApi:
    _browser_obj = None

    def _browser(self, create=True):
        if self._browser_obj is None and create:
            factory = android_factory
            if factory is None:
                window = getattr(self, "_window", None)
                if window is None or not hasattr(window, "events"):
                    raise browser.BrowserError("이 실행 방식에서는 브라우저를 쓸 수 없습니다.")
                factory = browser.desktop_factory(window)
            ratio = float(self._config.get("browser_ratio") or browser.DEFAULT_RATIO)
            self._browser_obj = browser.Browser(factory, on_event=self._browser_event, ratio=ratio)
            self._browser_obj.opener = self._open_url
        return self._browser_obj

    def _browser_event(self, event):
        self._push({"type": "browser", **event})

    def _browser_call(self, fn):
        try:
            return {"ok": True, **(fn() or {})}
        except browser.BrowserError as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # 네이티브 뷰 오류(.NET·Objective-C)도 화면에 알린다
            return {"ok": False, "error": f"브라우저 오류: {type(e).__name__}: {e}"}

    def browser_state(self):
        b = self._browser(create=False)
        available = android_factory is not None or sys.platform in ("win32", "darwin") or b is not None
        state = {"visible": False, "url": "", "title": ""}
        if b:
            state = dict(b.state, visible=b.visible, mode=b.mode, toolbar=bool(getattr(b._backend, "toolbar", False)))
        return {"ok": True, "available": available, "ratio": b.ratio if b else
                float(self._config.get("browser_ratio") or browser.DEFAULT_RATIO), **state}

    def browser_open(self, text):
        return self._browser_call(lambda: {"url": self._browser().open(text)})

    def browser_show(self):
        return self._browser_call(lambda: self._browser().show())

    def browser_focus_address(self):
        """1.19.1: 웹페이지 위 막대의 주소 칸으로 입력 초점을 옮긴다. 막대가 없으면 focused=False."""
        b = self._browser(create=False)
        return self._browser_call(lambda: {"focused": bool(b and b.visible and b.focus_address())})

    def browser_hide(self):
        b = self._browser(create=False)
        return self._browser_call(lambda: b.hide() if b else None)

    def browser_nav(self, action):
        return self._browser_call(lambda: self._browser().nav(str(action)))

    def browser_ratio(self, ratio):
        def go():
            value = self._browser().set_ratio(ratio)
            with self._lock:
                self._config["browser_ratio"] = value
                import storage
                storage.save_config(self._config)
            return {"ratio": value}
        return self._browser_call(go)

    def browser_external(self):
        """지금 페이지를 기본 브라우저로 연다(다운로드·로그인이 필요한 사이트)."""
        def go():
            b = self._browser(create=False)
            url = b.state.get("url") if b else ""
            if not url or not browser.allowed(url):
                raise browser.BrowserError("열린 웹페이지가 없습니다.")
            self._open_url(url)
        return self._browser_call(go)

    def browser_attach(self, kind="page"):
        """지금 페이지(또는 선택한 부분)를 채팅 첨부 파일로 만든다. 내용은 '외부 데이터'로 감싼다."""
        def go():
            page = self._browser().read()
            selection = kind == "selection"
            if selection and not page["selection"].strip():
                raise browser.BrowserError("웹페이지에서 선택한 글이 없습니다. 묻고 싶은 부분을 먼저 드래그하세요.")
            if not selection and not page["text"].strip():
                raise browser.BrowserError("이 페이지에서 읽을 글을 찾지 못했습니다.")
            text = connectors.wrap_untrusted(browser.page_markdown(page, selection_only=selection), f"웹페이지 {page['url']}")
            title = (page["title"] or "웹페이지").strip()[:60]
            name = f"{'선택' if selection else '웹페이지'} - {title}.md"
            attach_id = uuid.uuid4().hex
            item = attachments.upload_chunk(attach_id, name, 0, base64.b64encode(text.encode("utf-8")).decode("ascii"), True)
            return {"attachment": item, "url": page["url"], "paper": page["paper"]}
        return self._browser_call(go)

    def browser_save_paper(self):
        """지금 페이지의 논문(arXiv·DOI)을 연구 라이브러리에 더한다."""
        try:
            page = self._browser().read()
        except browser.BrowserError as e:
            return {"ok": False, "error": str(e)}
        if not page["paper"]:
            return {"ok": False, "error": "이 페이지에서 arXiv 번호나 DOI를 찾지 못했습니다. 논문 페이지에서 다시 시도하세요."}
        if not self._config.get("features", {}).get("research"):
            return {"ok": False, "need_feature": "research",
                    "error": "연구 라이브러리가 꺼져 있습니다. 사이드바의 연구 라이브러리에서 켠 뒤 다시 시도하세요."}
        res = self.research_add(page["paper"], ["웹에서"])
        if res.get("ok"):
            res["paper"] = page["paper"]
        return res

    def _browser_pause_event(self):
        if getattr(self, "_browser_paused", None) is None:
            import threading

            self._browser_paused = threading.Event()
        return self._browser_paused

    def browser_agent_pause(self, paused):
        """브라우저 에이전트 일시정지·계속(1.16). 멈추기는 채팅의 중지(stop)를 쓴다."""
        ev = self._browser_pause_event()
        ev.set() if paused else ev.clear()
        self._push({"type": "browser", "kind": "agent", "status": "paused" if paused else "resumed"})
        return {"ok": True, "paused": bool(paused)}

    # 에이전트가 쓴다(main.Bridge._work가 Agent에 넘긴다)
    def _browser_for_agent(self):
        b = self._browser(create=False)
        return b if b is not None and b.visible else None

    # 1.18.6 PLMS는 화면에 붙이지 않은 웹 뷰에서 로그인·조회한다. 사람이 해야 하는 단계(StonePASS 등)에서만 브라우저를 보인다.
    _plms_block_until = 0.0  # 로그인이 거부·미완료면 이 시각까지 자동 로그인을 다시 시도하지 않는다(계정 잠김 방지)
    _plms_login_gen = 0

    def plms_login(self):
        """저장된 계정이 있으면 숨은 웹 뷰에서 로그인한다. 없으면 브라우저를 열어 직접 로그인하게 한다."""
        import plms
        def go():
            with self._lock:
                self._config["plms_enabled"] = True
                import storage
                storage.save_config(self._config)
            if plms.credentials() is None:
                with self._lock:
                    if self._browser_owner is not None:
                        raise plms.PlmsError("브라우저를 쓰는 에이전트를 멈춘 뒤 로그인하세요.")
                self._browser().open(plms.LOGIN)
                return {"mode": "visible", "url": plms.LOGIN}
            self._plms_block_until = 0.0  # 사용자가 직접 누른 로그인은 막지 않는다
            if self._plms_relogin(self._browser(), lambda: False, force=True):
                return {"mode": "background", "message": "PLMS에 로그인했습니다."}
            raise plms.PlmsError("PLMS 로그인에 실패했습니다.")
        return self._plms_call(go)

    def _plms_relogin(self, b, cancelled, force=False):
        """세션이 없을 때 저장된 계정으로 숨은 로그인. 성공하면 True, 저장된 계정이 없으면 False, 실패하면 PlmsError."""
        import time
        import plms
        if plms.credentials() is None:
            return False
        if not force and time.monotonic() < self._plms_block_until:
            raise plms.PlmsError("PLMS 자동 로그인이 최근에 실패했습니다. 사이드바 PLMS에서 로그인한 뒤 다시 요청하세요.")
        with self._lock:
            if self._browser_owner is not None and not force:
                return False  # 브라우저를 쓰는 에이전트가 같은 웹 뷰를 쓰는 중이라 이동시키지 않는다
            gen = self._plms_login_gen  # 연결 해제(plms_disconnect)가 세대를 올리면 진행 중인 로그인이 멈춘다
        lock = self._plms_lock()
        with lock:
            if plms.session_alive(b):
                return True  # 기다리는 사이 다른 요청이 이미 로그인했다
            was_visible = b.visible
            def stop():
                return cancelled() or gen != self._plms_login_gen or not self._config.get("plms_enabled")
            status, message = plms.background_login(
                b, stop, show=b.show,
                notify=lambda text: self._push({"type": "plms", "kind": "login", "message": text}))
            if status == "ok":
                if not was_visible and b.visible:
                    b.hide()  # 사용자 인증을 위해 보였다면 다시 숨긴다
                self._plms_block_until = 0.0
                return True
            if status != "cancelled":
                self._plms_block_until = time.monotonic() + 600
            raise plms.PlmsError(message)

    def _plms_lock(self):
        import threading
        with self._lock:
            lock = getattr(self, "_plms_login_lock", None)
            if lock is None:
                lock = self._plms_login_lock = threading.Lock()
            return lock

    def plms_account(self):
        """저장된 계정 정보(아이디만). 비밀번호는 돌려주지 않는다."""
        import plms
        return {"ok": True, "username": plms.saved_username()}

    def _plms_call(self, fn):
        import plms
        try:
            return {"ok": True, **fn()}
        except (plms.PlmsError, browser.BrowserError, ValueError) as e:
            return {"ok": False, "error": str(e)}
        except Exception:
            return {"ok": False, "error": "PLMS 자료를 읽지 못했습니다. 로그인 상태를 확인하고 다시 시도하세요."}

    def _plms_read(self, action, cancelled=lambda: False, **kwargs):
        import plms
        if not self._config.get("plms_enabled"):
            raise plms.PlmsError("PLMS 로그인·연결을 먼저 켜세요.")
        b = self._browser()
        b.ensure()  # 화면에 붙이지 않은 웹 뷰: 보이는 브라우저가 없어도 조회한다
        for attempt in (0, 1):
            client = plms.Client(b, cancelled=lambda: cancelled() or not self._config.get("plms_enabled"))
            try:
                return getattr(client, action)(**kwargs)
            except plms.PlmsLoginRequired:
                # 세션이 없거나 만료됐다: 저장된 계정이 있으면 숨은 웹 뷰에서 한 번 다시 로그인하고 같은 조회를 다시 한다
                if attempt or not self._plms_relogin(b, cancelled):
                    raise
            finally:
                client.close()

    def plms_courses(self):
        return self._plms_call(lambda: {"courses": self._plms_read("courses")})

    def plms_course(self, course_id):
        return self._plms_call(lambda: {"course": self._plms_read("course", course_id=course_id)})

    def plms_read(self, course_id, url, query="", offset=0, parent=""):
        return self._plms_call(lambda: {"document": self._plms_read("read", course_id=course_id, url=url,
                                                                  query=query, offset=offset, parent=parent)})

    def plms_preview(self, course_id, url, parent=""):
        return self._plms_call(lambda: {"preview": self._plms_read("preview", course_id=course_id, url=url, parent=parent)})

    def plms_open_presentation(self, course_id, url, parent=""):
        """사용자가 고른 PowerPoint만 임시 파일로 열고, 앱을 종료하면 정리한다."""
        def go():
            import base64
            import os
            import subprocess
            import sys
            import tempfile
            from pathlib import Path
            import plms

            preview = self._plms_read("preview", course_id=course_id, url=url, parent=parent)
            if preview["kind"] not in ("ppt", "pptx"):
                raise plms.PlmsError("PowerPoint 파일이 아닙니다.")
            folder = tempfile.TemporaryDirectory(prefix="poschat-plms-view-")
            path = Path(folder.name) / ("PLMS-강의자료." + preview["kind"])
            path.write_bytes(base64.b64decode(preview["data"], validate=True))
            try:
                if sys.platform == "win32":
                    os.startfile(str(path))
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(path)])
                else:
                    raise plms.PlmsError("PowerPoint 앱으로 열기는 Windows와 macOS에서 지원합니다.")
            except Exception:
                folder.cleanup()
                raise
            if not hasattr(self, "_plms_previews"):
                self._plms_previews = []
            self._plms_previews.append(folder)
            return {}
        return self._plms_call(go)

    def plms_disconnect(self):
        def go():
            with self._lock:
                if self._browser_owner is not None:
                    raise browser.BrowserError("브라우저를 쓰는 에이전트를 멈춘 뒤 연결을 해제하세요.")
                self._config["plms_enabled"] = False
                self._plms_login_gen += 1
                import storage
                storage.save_config(self._config)
            b = self._browser(create=False)
            if b is not None:
                b.plms_cookies(clear=True)
                b.open("https://plms.postech.ac.kr/login/index.php")
            return {}
        return self._plms_call(go)
