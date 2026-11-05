// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

/* ---------- 브라우저(1.13): 채팅 옆 웹페이지 ----------
   웹페이지는 앱 창 오른쪽의 네이티브 웹 뷰가 그리고(browser.py), 여기에는 AI 연결 버튼만 둔다. 주소 칸·이동 버튼은
   1.19.1부터 웹페이지 위 네이티브 막대에 있고, 막대를 못 만들었을 때(도킹·안드로이드)만 여기 주소 줄을 보인다.
   웹페이지 쪽에는 POSCHAT API가 없다. 이 화면이 browser_* 를 불러 페이지를 읽고 채팅 첨부로 만든다. */

const BR = { open: false, available: true, url: "", title: "", loading: false, can_back: false, can_forward: false,
  mode: "", busy: "", agent: null, toolbar: false };  // agent: 1.16 브라우저 에이전트 진행 {action, status, count, limit, elapsed, summary, paused}
const BR_ACTION = { snapshot: "페이지 살펴보기", click: "누르기", type: "입력", select: "고르기", scroll: "스크롤", wait: "기다리기",
  extract: "글 읽기", screenshot: "화면 캡처", open: "주소 열기", back: "뒤로", forward: "앞으로", refresh: "새로 고침" };
const BR_STATUS = { running: "하는 중", done: "완료", denied: "거부됨", error: "실패", paused: "일시정지" };

function browserBar() {
  let bar = $("#browser-bar");
  if (bar) return bar;
  const btn = (icon, label, onclick, extra = {}) => h("button", { class: "icon-btn", title: label, "aria-label": label,
    html: ICONS[icon], onclick, ...extra });
  const address = h("input", { id: "browser-address", type: "text", inputmode: "url", autocomplete: "off", spellcheck: "false",
    placeholder: "주소 또는 검색어", "aria-label": "주소 또는 검색어" });
  const form = h("form", { class: "browser-address", role: "search", onsubmit: (e) => {
    e.preventDefault();
    browserOpen(address.value);
  } }, address);
  const action = (id, label, title, onclick) => h("button", { class: "btn browser-action", id, title, onclick }, label);
  bar = h("section", { id: "browser-bar", "aria-label": "브라우저", hidden: true },
    // 1.19.1: 웹페이지 위에 네이티브 막대(주소 칸·이동·기본 브라우저로 열기·닫기)가 있으면 이 주소 줄 전체를 숨긴다
    h("div", { class: "browser-row", id: "browser-nav-row" },
      btn("back", "뒤로", () => browserNav("back"), { id: "browser-back" }),
      btn("forward", "앞으로", () => browserNav("forward"), { id: "browser-forward" }),
      btn("retry", "새로 고침", () => browserNav(BR.loading ? "stop" : "reload"), { id: "browser-reload" }),
      form,
      btn("external", "기본 브라우저로 열기", () => browserCall(api().browser_external()), { id: "browser-external" }),
      btn("close", "브라우저 닫기", () => browserClose(), { id: "browser-close" })),
    h("div", { class: "browser-row browser-actions" },
      action("browser-ask-page", "이 페이지에 대해 묻기", "지금 보는 페이지의 글을 채팅에 첨부합니다", () => browserAttach("page")),
      action("browser-ask-selection", "선택한 부분 묻기", "페이지에서 드래그한 글만 첨부합니다", () => browserAttach("selection")),
      action("browser-save-paper", "연구 라이브러리에 저장", "arXiv·DOI 논문 페이지를 라이브러리에 더합니다", () => browserSavePaper()),
      h("span", { class: "browser-status", id: "browser-status", role: "status", "aria-live": "polite" })),
    // 1.16: 에이전트가 이 브라우저를 조작하는 동안의 진행 표시
    h("div", { class: "browser-row browser-agent", id: "browser-agent", hidden: true, role: "status", "aria-live": "polite" },
      h("span", { class: "browser-agent-dot", "aria-hidden": "true" }),
      h("span", { class: "browser-agent-text", id: "browser-agent-text" }),
      h("button", { class: "btn browser-action", id: "browser-agent-pause", onclick: () => browserAgentPause() }, "일시정지"),
      h("button", { class: "btn browser-action danger", id: "browser-agent-stop", title: "에이전트 작업을 멈춥니다(채팅의 중지와 같음)",
        onclick: () => { api().stop(); toast("에이전트를 멈췄습니다"); } }, "멈춤")));
  $("#topbar").after(bar);
  return bar;
}

function renderBrowserBar() {
  const bar = browserBar();
  // PO노트·도구 화면에서는 막대를 숨긴다(웹페이지 뷰는 오른쪽에 그대로 남는다)
  bar.hidden = !BR.open || (typeof PO !== "undefined" && PO.open) || (typeof PAGE !== "undefined" && !!PAGE.id);
  $("#btn-browser")?.classList.toggle("active", BR.open);
  $("#btn-browser")?.setAttribute("aria-pressed", String(BR.open));
  const address = $("#browser-address");
  if (address && document.activeElement !== address) address.value = BR.url || "";
  $("#browser-nav-row").hidden = !!BR.toolbar;
  $("#browser-back").disabled = !BR.can_back;
  $("#browser-forward").disabled = !BR.can_forward;
  const reload = $("#browser-reload");
  reload.innerHTML = BR.loading ? ICONS.close : ICONS.retry;
  reload.title = BR.loading ? "멈추기" : "새로 고침";
  reload.setAttribute("aria-label", reload.title);
  for (const id of ["browser-ask-page", "browser-ask-selection", "browser-save-paper"]) $(`#${id}`).disabled = !BR.url || !!BR.busy;
  const ag = BR.agent;
  const strip = $("#browser-agent");
  strip.hidden = !ag;
  if (ag) {
    const what = `${BR_ACTION[ag.action] || ag.action || "준비"}${ag.summary ? ` · ${ag.summary}` : ag.target ? ` · ${ag.target}` : ""}`;
    $("#browser-agent-text").textContent = `에이전트 조작 중 — ${what} (${BR_STATUS[ag.paused ? "paused" : ag.status] || ag.status || ""}) · ` +
      `${ag.count || 0}/${ag.limit || 40}번 · ${Math.round(ag.elapsed || 0)}초`;
    strip.classList.toggle("paused", !!ag.paused);
    strip.classList.toggle("error", ag.status === "error" || ag.status === "denied");
    $("#browser-agent-pause").textContent = ag.paused ? "계속" : "일시정지";
  }
  const status = $("#browser-status");
  status.textContent = BR.busy || (BR.loading ? "불러오는 중…" : (BR.title || ""));
  status.title = BR.title || "";
}

async function browserCall(promise) {
  const res = await promise;
  if (res && res.ok === false) {
    toast(res.error || "브라우저 오류");
    return null;
  }
  return res;
}

async function browserToggle() {
  if (BR.open) return browserClose();
  leaveViews();
  if (window.paperLeave) paperLeave();  // 오른쪽 화면은 하나만(1.14 논문 화면)
  if (window.codeLeave) codeLeave();  // 1.15 코드 화면(열린 탭은 그대로 남는다)
  if (!BR.available) return toast("이 실행 방식에서는 브라우저를 쓸 수 없습니다.");
  BR.open = true;
  renderBrowserBar();
  const res = await browserCall(api().browser_show());
  if (!res) {
    BR.open = false;
    renderBrowserBar();
    return;
  }
  setCollapsed(true);
  if (BR.toolbar) api().browser_focus_address?.();  // 1.19.1 주소 칸은 웹페이지 위 막대에 있다
  else setTimeout(() => $("#browser-address")?.focus(), 50);
}

async function browserOpen(text) {
  if (!String(text || "").trim()) return;
  BR.open = true;
  const res = await browserCall(api().browser_open(text));
  if (res) {
    BR.url = res.url;
    BR.loading = true;
    const address = $("#browser-address");
    if (address) address.value = res.url;  // 입력한 글 대신 실제로 연 주소(검색이면 검색 주소)
  }
  renderBrowserBar();
}

function browserNav(action) {
  browserCall(api().browser_nav(action));
}

async function browserClose() {
  BR.open = false;
  renderBrowserBar();
  await browserCall(api().browser_hide());
}

async function browserAttach(kind) {
  if (S.attach.length >= S.attachLimits.max_files) return toast(`파일은 한 번에 ${S.attachLimits.max_files}개까지 첨부할 수 있습니다`);
  BR.busy = kind === "selection" ? "선택한 부분을 읽는 중…" : "페이지를 읽는 중…";
  renderBrowserBar();
  try {
    const res = await browserCall(api().browser_attach(kind));
    if (!res) return;
    const a = res.attachment;
    S.attach.push({ id: a.id, name: a.name, size: a.size, kind: a.kind, status: "ready", progress: 1 });
    renderTray();
    updateSend();
    const input = $("#input");
    if (!input.value.trim()) {
      input.value = kind === "selection" ? "선택한 부분을 쉽게 설명해 줘." : "이 페이지의 핵심을 요약해 줘.";
      autoresize();
      updateSend();
    }
    input.focus();
    input.select();
    toast(kind === "selection" ? "선택한 부분을 첨부했습니다. 질문을 고쳐 보내세요" : "페이지를 첨부했습니다. 질문을 고쳐 보내세요");
  } finally {
    BR.busy = "";
    renderBrowserBar();
  }
}

async function browserSavePaper() {
  BR.busy = "논문 정보를 찾는 중…";
  renderBrowserBar();
  try {
    const res = await api().browser_save_paper();
    if (res.ok === false) {
      if (res.need_feature === "research") {
        if (confirm(res.error + "\n\n지금 연구 라이브러리를 열까요?")) pageOpen("research");
        return;
      }
      return toast(res.error);
    }
    toast(`연구 라이브러리에 더했습니다: ${res.paper}`);
  } finally {
    BR.busy = "";
    renderBrowserBar();
  }
}

async function browserAgentPause() {
  const paused = !(BR.agent && BR.agent.paused);
  await api().browser_agent_pause(paused);
}

function browserEvent(ev) {
  if (ev.kind === "blocked") return toast(`${ev.reason} (${ev.url.slice(0, 80)})`);
  if (ev.kind === "agent") {
    if (ev.status === "finished") BR.agent = null;
    else if (ev.status === "paused" || ev.status === "resumed") { if (BR.agent) BR.agent.paused = ev.status === "paused"; }
    else BR.agent = { ...(BR.agent || {}), ...ev, paused: ev.status === "paused" ? true : (BR.agent ? BR.agent.paused : false) };
    if (ev.url) BR.url = ev.url;
    return renderBrowserBar();
  }
  for (const k of ["url", "title", "loading", "can_back", "can_forward", "mode", "toolbar"]) if (k in ev) BR[k] = ev[k];
  if ("visible" in ev) BR.open = ev.visible;
  renderBrowserBar();
}

async function browserInit() {
  const st = await api().browser_state();
  BR.available = !!st.available;
  $("#btn-browser").hidden = !BR.available;
  browserEvent(st);
}

$("#btn-browser").addEventListener("click", browserToggle);
if (window.pywebview && window.pywebview.api) browserInit();
else window.addEventListener("pywebviewready", browserInit, { once: true });
