// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

/* ---------- POSCHAT Code(1.15): 코드 편집기 ----------
   하나의 전체 화면(1.17.2)에 왼쪽 패널(파일 · Git · 변경 검토, 1.18) + 편집기(CodeMirror 6, web/vendor/codemirror) +
   아래 패널(터미널, 1.18 — web/code-term.js)을 둔다. 작업 폴더는 로컬 폴더 또는 SSH 서버의 폴더(1.18 — web/code-ssh.js). 파일 읽기·쓰기·Git·터미널은 모두 Python(code_api.py)이 한다.
   화면을 닫거나 다른 화면으로 바꿔도 열린 탭·저장하지 않은 내용·터미널은 그대로 남는다(숨기기만 한다).
   v1.16 Lab이 다시 쓸 수 있게 편집기(codeEditorTab)를 나눠 둔다. */

Object.assign(ICONS, {
  code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/><path d="m14 4-4 16"/></svg>',
  expand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5"/><path d="M20 9V4h-5"/><path d="M4 15v5h5"/><path d="M20 15v5h-5"/></svg>',
  save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M8 3v5h7V3"/><rect x="7" y="13" width="10" height="6" rx="1"/></svg>',
  undo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/></svg>',
  redo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m15 14 5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  wrap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M3 12h15a3 3 0 0 1 0 6h-4"/><path d="m16 16-2 2 2 2"/><path d="M3 18h7"/></svg>',
  folderplus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M12 10v6M9 13h6"/></svg>',
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>',
  play: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M7 5v14l12-7Z"/></svg>',
  files: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7Z"/><path d="M15 3v4h4"/><path d="M4 7v12a2 2 0 0 0 2 2h9"/></svg>',
});

const CODE = {
  open: false, state: null, tabs: [], active: null, seq: 0, tree: new Map(), expanded: new Set([""]),
  side: "files", bottomOpen: true, git: null, gitBusy: false, gitPick: new Set(), runs: [],
  filesOpen: true, search: null, dark: false, ready: false, loadingTree: false,
};
const CODE_PRESETS = [
  ["explain", "코드 설명"], ["bug", "오류 분석"], ["perf", "성능 개선"], ["refactor", "리팩터링 제안"],
  ["comment", "주석 생성"], ["test", "테스트 코드 제안"], ["rtl", "RTL 로직 검토"],
];
const CODE_STATUS = { pending: "검토 대기", applied: "적용함", partial: "일부 적용", edited: "고쳐서 적용", rejected: "거부함",
  cancelled: "끝남(적용 안 함)", conflict: "충돌", auto: "자동 적용" };
const CODE_DRAFTS = "poschat.code.drafts";

/* ---------- 공용 ---------- */

async function codeCall(promise, quiet = false) {
  let res;
  try {
    res = await promise;
  } catch (e) {
    if (!quiet) toast(e.message || String(e));
    return null;
  }
  if (res && res.ok === false) {
    if (!quiet && !res.conflict) toast(res.error || "코드 오류");
    return res.conflict ? res : null;
  }
  return res;
}

function codeAskText(title, value = "", placeholder = "") {
  return new Promise((resolve) => {
    const input = h("input", { type: "text", class: "code-input", value, placeholder, "aria-label": title,
      spellcheck: "false", autocomplete: "off" });
    let done = false;
    const finish = (v, close) => { done = true; close(); resolve(v); };
    const m = modal({
      title, body: h("div", {}, input),
      buttons: [{ label: "취소", action: (close) => finish(null, close) },
        { label: "확인", class: "primary", action: (close) => finish(input.value.trim(), close) }],
      onClose: () => { if (!done) resolve(null); },
    });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); finish(input.value.trim(), m.close); } });
    setTimeout(() => { input.focus(); input.select(); }, 30);
  });
}

function codeChoose(title, body, buttons) {
  return new Promise((resolve) => {
    let done = false;
    modal({
      title, wide: true, body,
      buttons: buttons.map((b) => ({ label: b.label, class: b.class, action: (close) => { done = true; close(); resolve(b.value); } })),
      onClose: () => { if (!done) resolve(null); },
    });
  });
}

const codeBase = (p) => String(p || "").split("/").pop();
const codeDir = (p) => { const i = String(p || "").lastIndexOf("/"); return i < 0 ? "" : p.slice(0, i); };
const codeFeature = (name) => !!(CODE.state && CODE.state.features && CODE.state.features[name]);

/* ---------- 창 ---------- */

function codePane() {
  let pane = $("#code-pane");
  if (pane) return pane;
  // 1.17.2: 코드는 채팅 옆에 나누어 띄우지 않고 하나의 화면(섹션)으로 전체를 쓴다. 채팅으로는 사이드바나 닫기(×)로 돌아간다
  pane = h("section", { id: "code-pane", "aria-label": "POSCHAT Code", hidden: true });
  $("#app").append(pane);
  try {
    const b = Number(localStorage.getItem("poschat.codeBottom"));
    if (b) document.documentElement.style.setProperty("--code-bottom-h", b + "px");
  } catch { /* 기본 너비 */ }
  codeBuild(pane);
  return pane;
}

function codeBuild(pane) {
  const btn = (icon, label, onclick, extra = {}) => h("button", { class: "icon-btn", title: label, "aria-label": label,
    html: ICONS[icon], onclick, ...extra });
  const bottomResizer = h("div", { class: "code-hresizer", role: "separator", "aria-orientation": "horizontal", tabindex: "0",
    "aria-label": "아래 패널 높이 조절 (위·아래 화살표)", title: "끌어서 높이 조절" });
  bottomResizer.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    bottomResizer.setPointerCapture(e.pointerId);
    const rect = pane.getBoundingClientRect();
    const move = (ev) => codeSetBottom(rect.bottom - ev.clientY);
    const up = () => { bottomResizer.removeEventListener("pointermove", move); bottomResizer.removeEventListener("pointerup", up); };
    bottomResizer.addEventListener("pointermove", move);
    bottomResizer.addEventListener("pointerup", up);
  });
  bottomResizer.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    e.preventDefault();
    codeSetBottom($(".code-bottom").getBoundingClientRect().height + (e.key === "ArrowUp" ? 30 : -30));
  });
  pane.append(
    h("div", { class: "code-head" },
      btn("sidebar", "사이드바 열기", () => setCollapsed(false), { id: "code-sidebar-open" }),
      btn("files", "파일 목록 보이기·숨기기", () => codeToggleFiles(), { id: "code-files-toggle", "aria-pressed": "true" }),
      h("h2", { class: "code-title", id: "code-title" }, "코드"),
      h("small", { class: "code-ws", id: "code-ws" }, ""),
      // 1.18: SSH 서버의 폴더를 작업 폴더로(web/code-ssh.js)
      h("button", { class: "btn small code-ssh-btn", id: "code-ssh", type: "button", hidden: true,
        title: "SSH 서버의 폴더를 코드 화면에서 엽니다", onclick: () => window.sshOpen && sshOpen() }, "SSH"),
      btn("close", "코드 화면 닫고 채팅으로", () => codeLeave())),
    h("div", { class: "code-body", id: "code-body" },
      h("aside", { class: "code-files", id: "code-files", "aria-label": "파일" }),
      h("div", { class: "code-main" },
        h("div", { class: "code-tabs", id: "code-tabs", role: "tablist", "aria-label": "열린 파일" }),
        h("div", { class: "code-toolbar", id: "code-toolbar" }),
        h("div", { class: "code-notice", id: "code-notice", role: "status", "aria-live": "polite", hidden: true }),
        h("div", { class: "code-stack", id: "code-stack" }),
        h("div", { class: "code-statusbar", id: "code-statusbar" }))),
    bottomResizer,
    // 1.18: 아래 패널은 터미널(web/code-term.js). 변경 검토·Git은 왼쪽 패널의 탭으로 옮겼다
    h("div", { class: "code-bottom", id: "code-bottom" },
      h("div", { class: "code-bottom-tabs", role: "tablist", "aria-label": "터미널" },
        h("button", { class: "code-bottom-title", type: "button", title: "터미널 열기·접기 (Ctrl+`)", onclick: () => codeBottom("terminal", true) }, "터미널"),
        h("div", { class: "code-term-tabs", id: "code-term-tabs" }),
        btn("plus", "새 터미널", () => window.termNew && termNew(), { id: "code-term-new" }),
        h("button", { class: "btn small", id: "code-term-ask", type: "button", title: "고른 출력(없으면 끝부분)을 채팅에 첨부합니다",
          onclick: () => window.termAsk && termAsk() }, "AI에게 묻기"),
        h("span", { style: "flex:1" }),
        btn("minus", "아래 패널 접기·펴기 (Ctrl+`)", () => codeBottom("terminal", true), { id: "code-bottom-toggle" })),
      h("div", { class: "code-bottom-body", id: "code-bottom-body" })));
}

function codeSetBottom(px) {
  const h0 = Math.round(Math.min(window.innerHeight * 0.7, Math.max(90, px)));
  document.documentElement.style.setProperty("--code-bottom-h", h0 + "px");
  if (window.termFit) requestAnimationFrame(() => termFit());
  try { localStorage.setItem("poschat.codeBottom", String(h0)); } catch { /* 무시 */ }
}

function codeToggleFiles(on = !CODE.filesOpen) {
  CODE.filesOpen = on;
  $("#code-files").hidden = !on;
  $("#code-files-toggle").setAttribute("aria-pressed", String(on));
}

async function codeToggle() {
  if (CODE.open) return codeLeave();
  return codeShow();
}

async function codeShow() {
  if (window.BR && BR.open && window.browserClose) await browserClose();  // 코드 화면은 채팅·옆 화면을 모두 가린다
  if (window.paperLeave) paperLeave();
  if (window.pageLeave) pageLeave();
  if (window.poLeave) poLeave();
  CODE.open = true;
  const pane = codePane();
  pane.hidden = false;
  $("#app").classList.add("code-open");
  document.querySelectorAll(".thread.active").forEach((t) => t.classList.remove("active"));  // 다른 화면처럼 대화 선택을 뺀다
  $("#btn-code")?.classList.add("active");
  $("#btn-code")?.setAttribute("aria-pressed", "true");
  setCollapsed(true);
  if (isNarrow() && CODE.tabs.length) codeToggleFiles(false);
  if (!window.CM) {
    $("#code-stack").replaceChildren(h("p", { class: "muted code-empty" }, "편집기 모듈(CodeMirror)을 불러오지 못했습니다."));
    return;
  }
  await codeRefreshState();
  api().code_set_active(true);
  // 1.16: '작업'(Code 에이전트) 탭. 열린 파일이 없으면 작업 탭을 보인다
  if (window.caOpen) await caOpen(!CODE.tabs.some((t) => t.kind !== "agent"));
  codeRenderActive();
  codeCheckDisk();
  codeGitRefresh(true);  // 파일 트리에 Git 상태 표시
}

function codeLeave() {
  if (!CODE.open) return;
  CODE.open = false;
  $("#code-pane").hidden = true;
  $("#app").classList.remove("code-open");
  if (typeof renderSidebar === "function") renderSidebar();  // 채팅으로 돌아오면 지금 대화를 다시 표시
  $("#btn-code")?.classList.remove("active");
  $("#btn-code")?.setAttribute("aria-pressed", "false");
  // 닫혀 있으면 에이전트 수정은 예전 승인 창으로 묻는다(대기 중인 제안도 넘긴다)
  api().code_set_active(false).then((r) => { if (r && r.moved) toast("검토 중이던 변경을 승인 창으로 넘겼습니다"); });
}

async function codeRefreshState() {
  const st = await codeCall(api().code_state());
  if (!st) return;
  const changed = CODE.state && codeWsKey(CODE.state) !== codeWsKey(st);   // 2.0: 같은 경로라도 SSH 대상이 바뀌면 다른 작업 폴더
  CODE.state = st;
  CODE.runs = st.runs || [];
  const remote = st.remote;
  const ws = $("#code-ws");
  ws.textContent = remote ? `· SSH ${remote.label}` : st.workspace.name ? `· ${st.workspace.name}` : "";
  ws.title = remote ? `${remote.label} (${remote.connected ? "연결됨" : "연결 안 됨"})` : st.workspace.path || "";
  ws.classList.toggle("remote", !!remote);
  ws.classList.toggle("offline", !!remote && !remote.connected);
  $("#code-ssh").hidden = !codeFeature("ssh");
  $("#code-ssh").classList.toggle("active", !!remote);
  if (CODE.side !== "files" && !codeFeature(CODE.side)) CODE.side = "files";
  if (changed) {
    // 2.0: 저장하지 않은 파일 탭만 남긴다(그 탭은 예전 폴더에 묶여 저장·다시 열기를 막는다)
    const keep = CODE.tabs.some((t) => t.kind === "file" && t.editor.isDirty() && !codeTabHere(t));
    for (const t of [...CODE.tabs]) {
      if (t.kind === "agent" || (t.kind === "file" && t.editor.isDirty())) continue;
      codeCloseTab(t, true);
    }
    if (keep) toast("작업 폴더가 바뀌었습니다. 저장하지 않은 탭은 그대로 둡니다(예전 폴더의 파일, 저장하려면 그 폴더로 돌아가세요)");
    codeRenderNotice();
    if (window.caRefresh) caRefresh();
    CODE.tree.clear();
    CODE.expanded = new Set([""]);
    CODE.git = null;
  }
  codeRenderFiles();
  if (codeWsReady() && !CODE.tree.has("")) codeLoadDir("");
  // 아래 터미널: 사용자가 접어 두었으면 그대로, 펼쳐져 있으면 터미널을 연다(이미 있으면 다시 붙인다)
  $("#code-pane").classList.toggle("bottom-closed", !CODE.bottomOpen);
  if (CODE.bottomOpen && CODE.open && window.termEnsure && (codeWsReady() || !st.remote)) termEnsure();
  codeRenderTabs();
}

/* 2.0: 작업 폴더 식별자(로컬 경로, 원격이면 SSH 대상+경로). 탭은 연 때의 값을 들고 있다 */
function codeWsKey(st = CODE.state) {
  if (!st) return "";
  return st.remote ? `ssh:${st.remote.target}:${st.workspace.path}` : `local:${st.workspace.path}`;
}

function codeWsLabel(st = CODE.state) {
  if (!st) return "";
  return st.remote ? `SSH ${st.remote.label}` : st.workspace.path;
}

/* 2.0: 탭이 지금 작업 폴더의 파일인지(작업 폴더가 바뀐 뒤 남긴 탭이면 false) */
function codeTabHere(t) {
  return !t.ws || t.ws === codeWsKey();
}

/* 2.0: 다른 작업 폴더의 탭이면 알리고 true. 저장·다시 열기가 새 폴더의 같은 경로를 덮지 않게 */
function codeTabElsewhere(t, what = "저장") {
  if (codeTabHere(t)) return false;
  toast(`이 탭은 다른 작업 폴더(${t.wsLabel || "예전 폴더"})의 파일입니다. ${what}하려면 그 폴더로 돌아가세요`);
  return true;
}

/* ---------- 파일 트리 ---------- */

/* 작업 폴더를 쓸 수 있는지(원격이면 연결돼 있어야 한다) */
function codeWsReady() {
  const st = CODE.state;
  return !!(st && st.workspace.path && (!st.remote || st.remote.connected));
}

function codeRenderFiles() {
  const box = $("#code-files");
  const st = CODE.state;
  if (st && st.remote && !st.remote.connected) {   // 1.18: 원격 작업 폴더인데 연결이 없다
    const r = st.remote;
    box.replaceChildren(h("div", { class: "code-nows" },
      h("p", {}, h("b", {}, `SSH: ${r.label}`), h("br"),
        r.state === "connecting" ? "연결 중입니다…" : "서버에 연결돼 있지 않습니다. 다시 연결하면 파일·Git·터미널을 쓸 수 있습니다."),
      r.message && r.state !== "connecting" ? h("p", { class: "muted" }, r.message) : null,
      h("button", { class: "btn primary", id: "code-ssh-reconnect", disabled: r.state === "connecting", onclick: () => sshReconnect() }, "다시 연결"),
      h("button", { class: "btn", onclick: () => sshLocal() }, "로컬 작업 폴더로")));
    return;
  }
  if (!st || !st.workspace.path) {
    box.replaceChildren(h("div", { class: "code-nows" },
      h("p", {}, "작업 폴더를 먼저 고르세요. 코드 화면은 작업 폴더 안의 파일만 열고 저장합니다."),
      h("button", { class: "btn primary", onclick: async () => { await chooseWorkspace(); codeRefreshState(); } }, "작업 폴더 고르기"),
      codeFeature("ssh") ? h("button", { class: "btn", onclick: () => sshOpen() }, "SSH 서버의 폴더 열기") : null));
    return;
  }
  const tool = (icon, label, onclick, extra = {}) => h("button", { class: "icon-btn", title: label, "aria-label": label,
    html: ICONS[icon], onclick, ...extra });
  const q = h("input", { type: "search", class: "code-search", id: "code-search", placeholder: "파일 찾기 (Enter)",
    "aria-label": "파일 이름 또는 내용 찾기", spellcheck: "false", autocomplete: "off" });
  const mode = h("select", { class: "code-search-mode", "aria-label": "찾는 방식" },
    h("option", { value: "name" }, "이름"), h("option", { value: "text" }, "내용"));
  q.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); codeSearch(q.value, mode.value); }
    if (e.key === "Escape") { q.value = ""; CODE.search = null; codeRenderTree(); }
  });
  const hidden = st.settings.show_hidden;
  const side = codeSideTabs();
  if (CODE.side !== "files") {   // 1.18: 왼쪽 패널의 Git·변경 검토
    box.replaceChildren(side, h("div", { class: "code-side-body", id: "code-side-body" }));
    if (CODE.side === "git") codeRenderGit(!CODE.git);
    else codeRenderReviewList();
    return;
  }
  box.replaceChildren(side,
    h("div", { class: "code-files-bar" },
      tool("plus", "새 파일", () => codeNew("file")),
      tool("folderplus", "새 폴더", () => codeNew("dir")),
      tool("eye", hidden ? "숨김 파일 숨기기" : "숨김 파일 보이기", () => codeSetting({ show_hidden: !hidden }),
        { "aria-pressed": String(hidden), class: "icon-btn" + (hidden ? " active" : "") }),
      tool("retry", "새로 고침", () => { CODE.tree.clear(); codeLoadDir(""); for (const d of CODE.expanded) if (d) codeLoadDir(d); codeGitRefresh(true); }),
      tool("gear", "제외할 폴더 설정", () => codeExcludes())),
    h("div", { class: "code-search-row" }, q, mode),
    h("div", { class: "code-tree", id: "code-tree", role: "tree", "aria-label": "작업 폴더 파일" }));
  codeRenderTree();
}

function codeSideTabs() {
  const n = ((CODE.state && CODE.state.proposals) || []).filter((p) => p.status === "pending").length;
  const tab = (k, label) => h("button", { class: "code-stab" + (CODE.side === k ? " active" : ""), role: "tab", id: `code-side-${k}`,
    "aria-selected": String(CODE.side === k), hidden: k !== "files" && !codeFeature(k), onclick: () => codeSide(k) }, label);
  return h("div", { class: "code-side-tabs", role: "tablist", "aria-label": "왼쪽 패널" },
    tab("files", "파일"), tab("git", "Git"), tab("review", n ? `변경 검토 (${n})` : "변경 검토"));
}

/* 왼쪽 패널: 파일 · Git · 변경 검토 */
function codeSide(k) {
  CODE.side = k;
  if (!CODE.filesOpen) codeToggleFiles(true);
  codeRenderFiles();
}

async function codeLoadDir(path) {
  const res = await codeCall(api().code_list(path), true);
  if (!res) {
    CODE.tree.set(path, { items: [], error: true });
  } else {
    CODE.tree.set(path, res);
  }
  codeRenderTree();
}

function codeGitMark(path) {
  if (!CODE.git || !CODE.git.files) return null;
  const f = CODE.git.files.find((x) => x.path === path);
  if (!f) return null;
  const letter = f.conflict ? "U" : f.untracked ? "?" : (f.y !== "." ? f.y : f.x);
  return h("span", { class: `code-git-mark git-${f.conflict ? "u" : f.untracked ? "n" : f.staged && !f.unstaged ? "s" : "m"}`,
    title: f.label + (f.staged ? " (스테이지됨)" : "") }, letter);
}

function codeRenderTree() {
  const box = $("#code-tree");
  if (!box) return;
  if (CODE.search) return codeRenderSearch(box);
  const recent = ((CODE.state && CODE.state.recent) || []).slice(0, 6);
  const out = [];
  if (recent.length) {
    out.push(h("details", { class: "code-recent", open: true },
      h("summary", {}, "최근 파일"),
      ...recent.map((p) => h("button", { class: "code-row file", title: p, onclick: () => codeOpenFile(p) },
        h("span", { class: "code-row-name" }, codeBase(p)), h("small", {}, codeDir(p))))));
  }
  const walk = (dir, depth) => {
    const node = CODE.tree.get(dir);
    if (!node) {
      out.push(h("div", { class: "code-row muted", style: `--d:${depth}` }, "불러오는 중…"));
      return;
    }
    if (node.error) {
      out.push(h("div", { class: "code-row muted", style: `--d:${depth}` }, "읽지 못했습니다"));
      return;
    }
    for (const it of node.items) {
      const open = it.dir && CODE.expanded.has(it.path);
      const active = CODE.tabs.find((t) => t.id === CODE.active);
      const row = h("div", { class: "code-row" + (it.dir ? " dir" : " file") + (active && active.path === it.path ? " current" : ""),
        role: "treeitem", "aria-expanded": it.dir ? String(open) : null, tabindex: "0", style: `--d:${depth}`,
        title: it.path + (it.link ? " (링크: 따라가지 않습니다)" : ""), "data-path": it.path },
        h("span", { class: "code-caret" }, it.dir ? (open ? "▾" : "▸") : ""),
        h("span", { class: "code-row-name" }, it.name + (it.link ? " ↪" : "")),
        it.dir ? null : codeGitMark(it.path),
        h("span", { class: "code-row-tools" },
          h("button", { class: "icon-btn", title: "이름 바꾸기", "aria-label": `${it.name} 이름 바꾸기`, html: ICONS.pencil,
            onclick: (e) => { e.stopPropagation(); codeRename(it); } }),
          h("button", { class: "icon-btn", title: "지우기", "aria-label": `${it.name} 지우기`, html: ICONS.trash,
            onclick: (e) => { e.stopPropagation(); codeDelete(it); } })));
      const act = () => {
        if (it.link) return toast("링크는 따라가지 않습니다. 링크가 가리키는 파일을 작업 폴더 안에서 여세요");
        if (it.dir) {
          if (open) CODE.expanded.delete(it.path); else { CODE.expanded.add(it.path); if (!CODE.tree.has(it.path)) codeLoadDir(it.path); }
          codeRenderTree();
        } else codeOpenFile(it.path);
      };
      row.addEventListener("click", act);
      row.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); } });
      out.push(row);
      if (open) walk(it.path, depth + 1);
    }
    if (node.more) out.push(h("div", { class: "code-row muted", style: `--d:${depth}` }, `… ${node.more}개 더 있음(찾기로 여세요)`));
    if (!dir && !node.items.length) out.push(h("p", { class: "muted code-empty" }, "빈 폴더입니다. '새 파일'로 만들어 보세요."));
  };
  walk("", 0);
  box.replaceChildren(...out);
}

async function codeSearch(query, mode) {
  if (!String(query || "").trim()) { CODE.search = null; return codeRenderTree(); }
  CODE.search = { query, mode, busy: true, results: [] };
  codeRenderTree();
  const res = await codeCall(api().code_search(query, mode, false, false));
  CODE.search = { query, mode, busy: false, results: res ? res.results : [], truncated: res && res.truncated };
  codeRenderTree();
}

function codeRenderSearch(box) {
  const s = CODE.search;
  box.replaceChildren(
    h("div", { class: "code-search-head" },
      h("span", {}, s.busy ? "찾는 중…" : `'${s.query}' ${s.results.length}개${s.truncated ? "+" : ""}`),
      h("button", { class: "btn", onclick: () => { CODE.search = null; $("#code-search").value = ""; codeRenderTree(); } }, "트리로")),
    ...s.results.map((r) => h("button", { class: "code-row file", title: r.path, onclick: () => codeOpenFile(r.path, r.line, r.col) },
      h("span", { class: "code-row-name" }, r.line ? `${codeBase(r.path)}:${r.line}` : codeBase(r.path)),
      h("small", {}, r.text || codeDir(r.path)))),
    !s.busy && !s.results.length ? h("p", { class: "muted code-empty" }, "찾지 못했습니다.") : null);
}

async function codeNew(kind) {
  const active = CODE.tabs.find((t) => t.id === CODE.active);
  const base = active && active.path ? codeDir(active.path) : "";
  const name = await codeAskText(kind === "dir" ? "새 폴더" : "새 파일", base ? base + "/" : "",
    "작업 폴더 기준 경로 (예: rtl/top.sv)");
  if (!name) return;
  const res = await codeCall(api().code_create(name, kind));
  if (!res) return;
  const dir = codeDir(res.created.path);
  CODE.expanded.add(dir);
  await codeLoadDir(dir);
  if (kind !== "dir") codeOpenFile(res.created.path);
}

async function codeRename(it) {
  const name = await codeAskText("이름 바꾸기", it.path);
  if (!name || name === it.path) return;
  const res = await codeCall(api().code_rename(it.path, name));
  if (!res) return;
  for (const t of CODE.tabs) if (t.kind === "file" && t.path === it.path && codeTabHere(t)) { t.path = res.renamed.path; t.title = codeBase(t.path); }
  await codeLoadDir(codeDir(it.path));
  if (codeDir(res.renamed.path) !== codeDir(it.path)) await codeLoadDir(codeDir(res.renamed.path));
  codeRenderTabs();
}

async function codeDelete(it) {
  const ok = await codeChoose(`지우기: ${it.name}`,
    h("p", {}, it.dir ? "빈 폴더만 지울 수 있습니다." : "파일을 POSCHAT 데이터 폴더의 휴지통(code-trash)으로 옮깁니다. 필요하면 거기서 되살릴 수 있습니다."),
    [{ label: "취소", value: false }, { label: "지우기", class: "danger", value: true }]);
  if (!ok) return;
  const res = await codeCall(api().code_delete(it.path));
  if (!res) return;
  for (const t of [...CODE.tabs]) if (t.kind === "file" && t.path === it.path && codeTabHere(t)) codeCloseTab(t, true);
  await codeLoadDir(codeDir(it.path));
  toast(res.deleted.trash ? "휴지통으로 옮겼습니다" : "지웠습니다");
}

async function codeSetting(s) {
  const res = await codeCall(api().code_save_settings(s));
  if (!res) return;
  CODE.state.settings = res.settings;
  if ("show_hidden" in s || "exclude" in s) { CODE.tree.clear(); codeRenderFiles(); codeLoadDir(""); for (const d of CODE.expanded) if (d) codeLoadDir(d); }
  if ("wrap" in s) for (const t of CODE.tabs) if (t.editor) t.editor.setWrap(res.settings.wrap);
  if ("wrap" in s || "review" in s) codeRenderToolbar();
}

async function codeExcludes() {
  const st = CODE.state.settings;
  const area = h("textarea", { class: "code-input", rows: "4", "aria-label": "제외할 폴더·파일 이름(쉼표로 구분)" }, st.exclude.join(", "));
  const review = h("select", { "aria-label": "에이전트 수정 검토" },
    h("option", { value: "auto", selected: st.review === "auto" }, "Code 화면이 열려 있으면 여기서 덩어리별로 검토"),
    h("option", { value: "off", selected: st.review === "off" }, "항상 예전 승인 창으로"));
  const timeout = h("input", { type: "number", min: "10", max: "3600", value: String(st.timeout), class: "code-input", "aria-label": "명령 실행 제한 시간(초)" });
  const ok = await codeChoose("코드 화면 설정", h("div", { class: "code-settings" },
    h("label", {}, "파일 트리·찾기에서 뺄 이름(쉼표로 구분)"), area,
    h("p", { class: "muted" }, "기본값: .git, node_modules, .venv, __pycache__, dist, build 같은 큰 폴더. 비우면 모두 보입니다."),
    h("label", {}, "에이전트가 파일을 고칠 때"), review,
    h("p", { class: "muted" }, `승인이 필요한지는 설정 → 권한(지금: ${CODE.state.permission})이 정합니다. 자동 허용이면 바로 적용하고 검토 목록에 '자동 적용'으로 남깁니다.`),
    h("label", {}, "실행 패널 명령 제한 시간(초)"), timeout),
  [{ label: "취소", value: false }, { label: "저장", class: "primary", value: true }]);
  if (!ok) return;
  codeSetting({ exclude: area.value.split(",").map((x) => x.trim()).filter(Boolean), review: review.value,
    timeout: Number(timeout.value) || 600 });
}

/* ---------- 탭·편집기 ---------- */

function codeNewTab(t) {
  t.id = "t" + (++CODE.seq);
  t.el = h("div", { class: "code-tabpane" + (t.kind === "agent" ? " agent" : ""), role: "tabpanel", "data-tab": t.id, hidden: true });
  $("#code-stack").append(t.el);
  CODE.tabs.push(t);
  return t;
}

async function codeOpenFile(path, line, col) {
  if (!CODE.open) await codeShow();
  const existing = CODE.tabs.find((t) => t.kind === "file" && t.path === path && codeTabHere(t));
  if (existing) {
    codeActivate(existing.id);
    if (line) existing.editor.gotoLine(line, col);
    return existing;
  }
  const res = await codeCall(api().code_open(path));
  if (!res) return null;
  const f = res.file;
  if (f.binary) { toast(f.reason); return null; }
  const t = codeNewTab({ kind: "file", path: f.path, title: f.name, file: f,
    ws: codeWsKey(), wsLabel: codeWsLabel(), wsPath: CODE.state ? CODE.state.workspace.path : "" });  // 2.0: 연 작업 폴더를 기억
  t.editor = codeEditorTab(t.el, f.text, f.language, f.readonly, (ed) => codeOnChange(t), () => codeSave(t));
  if (isNarrow() && CODE.filesOpen) codeToggleFiles(false);
  codeActivate(t.id);
  if (line) t.editor.gotoLine(line, col);
  codeOfferDraft(t);
  if (CODE.state) {
    CODE.state.recent = [f.path, ...(CODE.state.recent || []).filter((p) => p !== f.path)].slice(0, 15);
  }
  return t;
}

/* 편집기 하나(v1.16 Lab에서도 쓴다): CM.createEditor를 앱 테마·설정에 맞춰 감싼다 */
function codeEditorTab(parent, text, lang, readOnly, onChange, onSave) {
  return CM.createEditor({
    parent, doc: text, lang, readOnly, dark: CODE.dark, wrap: !!(CODE.state && CODE.state.settings.wrap),
    label: "코드 편집기", onChange, onSave, onCursor: () => codeRenderStatus(),
  });
}

function codeActivate(id) {
  CODE.active = id;
  for (const t of CODE.tabs) t.el.hidden = t.id !== id;
  codeRenderTabs();
  codeRenderActive();
  const t = CODE.tabs.find((x) => x.id === id);
  if (t && t.kind === "agent" && window.caFocus) setTimeout(() => caFocus(), 0);  // 1.17.2: 작업 탭(터미널)을 열면 바로 입력
}

function codeRenderActive() {
  codeRenderToolbar();
  codeRenderNotice();
  codeRenderStatus();
  const t = CODE.tabs.find((x) => x.id === CODE.active);
  if (!CODE.tabs.length) {
    const stack = $("#code-stack");
    if (!stack.querySelector(".code-welcome")) stack.append(codeWelcome());
  } else $("#code-stack .code-welcome")?.remove();
  if (t && t.kind === "file") setTimeout(() => t.editor.focus(), 0);
  document.querySelectorAll("#code-tree .code-row.current").forEach((el) => el.classList.remove("current"));
  if (t && t.path) document.querySelector(`#code-tree .code-row[data-path="${CSS.escape(t.path)}"]`)?.classList.add("current");
}

function codeWelcome() {
  const st = CODE.state;
  return h("div", { class: "code-welcome" },
    h("h3", {}, "POSCHAT Code"),
    h("p", {}, "맨 앞 '작업' 탭에서 할 일을 맡기면 에이전트가 코드를 읽고·고치고·실행해 확인합니다. " +
      "직접 고치려면 왼쪽에서 파일을 열고 저장하세요(Ctrl+S). 코드를 선택해 'AI에게 묻기'로 채팅에 보낼 수도 있습니다."),
    h("ul", {},
      h("li", {}, "에이전트가 파일을 고치면 아래 '변경 검토'에 뜨고, 덩어리마다 받아들이거나 거부합니다."),
      codeFeature("git") ? h("li", {}, "Git: 바뀐 파일·차이 보기, 고른 파일만 스테이지, 커밋 메시지 제안.") : null,
      codeFeature("run") ? h("li", {}, `실행: 작업 폴더에서 명령을 실행합니다(${st ? st.shell : ""}, 매번 승인). Verilator·Icarus Verilog 같은 도구는 설치돼 있으면 씁니다.`) : null,
      st && st.platform === "android" ? h("li", {}, "안드로이드에서는 열기·강조·찾기·묻기·간단한 편집만 됩니다(명령 실행·Git·덩어리 적용은 PC 앱).") : null));
}

function codeRenderTabs() {
  const bar = $("#code-tabs");
  if (!bar) return;
  bar.replaceChildren(...CODE.tabs.map((t) => {
    const dirty = t.kind === "file" && t.editor.isDirty();
    const label = t.kind === "review" ? `검토: ${codeBase(t.path)}` : t.kind === "diff" ? `diff: ${codeBase(t.path)}` : t.title;
    const agent = t.kind === "agent";  // 1.16: Code 에이전트 '작업' 탭은 맨 앞에 고정(닫지 않음)
    return h("div", { class: "code-tab" + (t.id === CODE.active ? " active" : "") + (dirty ? " dirty" : "") + (agent ? " agent" : ""), role: "tab",
      "aria-selected": String(t.id === CODE.active), title: agent ? "Code 에이전트: 작업을 맡기고 진행을 봅니다" : t.path || label },
      h("button", { class: "code-tab-name", id: agent ? "code-tab-agent" : null, onclick: () => codeActivate(t.id) },
        t.kind === "review" ? h("span", { class: "code-tab-kind" }, "±") : null,
        agent ? h("span", { class: "code-tab-kind" }, "✦") : null, label,
        dirty ? h("span", { class: "code-dirty", "aria-label": "저장하지 않음" }, "●") : null),
      agent ? null : h("button", { class: "code-tab-close", title: "탭 닫기", "aria-label": `${label} 탭 닫기`, html: ICONS.close,
        onclick: () => codeCloseTab(t) }));
  }));
}

async function codeCloseTab(t, force = false) {
  if (!force && t.kind === "file" && t.editor.isDirty()) {
    const v = await codeChoose(`${t.title}: 저장하지 않은 변경`, h("p", {}, "저장하지 않은 변경이 있습니다. 어떻게 할까요?"),
      [{ label: "취소", value: null }, { label: "버리고 닫기", class: "danger", value: "drop" }, { label: "저장하고 닫기", class: "primary", value: "save" }]);
    if (!v) return;
    if (v === "save" && !(await codeSave(t))) return;
  }
  if (t.editor) t.editor.destroy();
  t.el.remove();
  if (t.kind === "file") codeDraftDrop(t.path, t.wsPath);   // 2.0: 탭을 연 폴더의 임시 보관을 지운다
  const i = CODE.tabs.indexOf(t);
  CODE.tabs.splice(i, 1);
  if (CODE.active === t.id) CODE.active = CODE.tabs.length ? CODE.tabs[Math.max(0, i - 1)].id : null;
  if (CODE.active) codeActivate(CODE.active); else { codeRenderTabs(); codeRenderActive(); }
}

function codeOnChange(t) {
  const wasDirty = t._dirty;
  t._dirty = t.editor.isDirty();
  if (wasDirty !== t._dirty) codeRenderTabs();
  clearTimeout(t._draftTimer);
  t._draftTimer = setTimeout(() => codeDraftSave(t), 1500);
}

function codeRenderToolbar() {
  const bar = $("#code-toolbar");
  const t = CODE.tabs.find((x) => x.id === CODE.active);
  if (!bar) return;
  if (!t || t.kind !== "file") { bar.replaceChildren(); bar.hidden = true; return; }
  bar.hidden = false;
  const btn = (icon, label, onclick, extra = {}) => h("button", { class: "icon-btn", title: label, "aria-label": label,
    html: ICONS[icon], onclick, ...extra });
  const wrap = !!CODE.state.settings.wrap;
  bar.replaceChildren(
    btn("save", "저장 (Ctrl+S)", () => codeSave(t), { id: "code-save", disabled: t.file.readonly }),
    btn("undo", "되돌리기 (Ctrl+Z)", () => t.editor.undo()),
    btn("redo", "다시 하기 (Ctrl+Y)", () => t.editor.redo()),
    btn("search", "찾기·바꾸기 (Ctrl+F)", () => t.editor.find()),
    btn("wrap", wrap ? "긴 줄 접지 않기" : "긴 줄 접어 보기", () => codeSetting({ wrap: !wrap }),
      { "aria-pressed": String(wrap), class: "icon-btn" + (wrap ? " active" : "") }),
    h("span", { style: "flex:1" }),
    h("button", { class: "btn code-ask-btn", id: "code-ask", title: "선택한 코드(없으면 현재 함수·블록)를 채팅에 첨부합니다",
      onclick: (e) => codeAskMenu(t, e.currentTarget) }, h("span", { html: ICONS.spark }), "AI에게 묻기 ▾"));
}

function codeRenderNotice() {
  const box = $("#code-notice");
  const t = CODE.tabs.find((x) => x.id === CODE.active);
  if (!box) return;
  const parts = [];
  if (t && t.kind === "file") {
    if (!codeTabHere(t)) parts.push(h("span", { class: "code-elsewhere" }, `이 탭은 다른 작업 폴더(${t.wsLabel || "예전 폴더"})의 파일입니다. 저장하려면 그 폴더로 돌아가세요. `));  // 2.0
    if (t.file.reason) parts.push(h("span", {}, t.file.reason));
    if (t.file.mixed_newlines) parts.push(h("span", {}, "이 파일은 줄 끝(LF·CRLF)이 섞여 있습니다. 저장하면 많은 쪽으로 맞춥니다."));
    if (t.diskChanged) {
      parts.push(h("span", {}, "디스크의 파일이 바뀌었습니다(다른 프로그램·에이전트). "),
        h("button", { class: "btn", onclick: () => codeReload(t) }, t.editor.isDirty() ? "내 변경 버리고 다시 열기" : "다시 열기"),
        h("button", { class: "btn", onclick: () => { t.diskChanged = false; codeRenderNotice(); } }, "그대로 두기"));
    }
    if (t.draft) {
      parts.push(h("span", {}, "지난번에 저장하지 않은 내용이 남아 있습니다. "),
        h("button", { class: "btn", onclick: () => { t.editor.setText(t.draft.text, false); t.draft = null; codeDraftDrop(t.path); codeRenderNotice(); codeRenderTabs(); } }, "되살리기"),
        h("button", { class: "btn", onclick: () => { t.draft = null; codeDraftDrop(t.path); codeRenderNotice(); } }, "버리기"));
    }
  }
  box.replaceChildren(...parts);
  box.hidden = !parts.length;
}

function codeRenderStatus() {
  const bar = $("#code-statusbar");
  const t = CODE.tabs.find((x) => x.id === CODE.active);
  if (!bar) return;
  if (!t || t.kind !== "file") { bar.textContent = ""; return; }
  const s = t.editor.selection();
  const lang = CM.LANGS[t.editor.lang] || CM.LANGS.text;
  const nl = { "\r\n": "CRLF", "\n": "LF", "\r": "CR" }[t.file.newline] || "LF";
  const sel = s.empty ? "" : ` · ${s.toLine - s.fromLine + 1}줄 선택`;
  bar.replaceChildren(...[
    h("span", {}, `줄 ${s.cursorLine}, 칸 ${s.cursorCol}${sel}`),
    h("span", { title: lang.tree ? "문법 트리: 강조·들여쓰기·접기·블록 인식" : "줄 단위 강조(키워드·주석·문자열·숫자)만, 접기·블록 인식은 줄 모양으로 짐작" },
      lang.label + (lang.tree ? "" : " (기본 강조)")),
    h("span", {}, (t.file.encoding || "utf-8").toUpperCase()), h("span", {}, nl),
    t.file.readonly ? h("span", { class: "code-ro" }, "읽기 전용") : null].filter(Boolean));
}

async function codeSave(t, opts = {}) {
  if (codeTabElsewhere(t, "저장")) return false;
  if (t.file.readonly) { toast("읽기 전용 파일입니다"); return false; }
  const text = t.editor.getText();
  const res = await codeCall(api().code_save(t.path, text, t.file.hash, opts.encoding || t.file.encoding, t.file.newline, !!opts.force));
  if (!res) {
    return false;
  }
  if (res.conflict) {
    const v = await codeChoose(`${t.title}: 저장 충돌`, h("div", {},
      h("p", {}, res.error), h("p", { class: "muted" }, "덮어쓰면 다른 곳에서 바꾼 내용은 사라집니다. 다시 열면 내 변경이 사라집니다.")),
    [{ label: "취소", value: null }, { label: "디스크 내용으로 다시 열기", value: "reload" }, { label: "내 내용으로 덮어쓰기", class: "danger", value: "force" }]);
    if (v === "force") return codeSave(t, { ...opts, force: true });
    if (v === "reload") await codeReload(t, true);
    return false;
  }
  if (!res.file) return false;
  t.file.hash = res.file.hash;
  if (opts.encoding) t.file.encoding = opts.encoding;
  t.editor.markClean();
  t._dirty = false;
  t.diskChanged = false;
  codeDraftDrop(t.path);
  codeRenderTabs();
  codeRenderNotice();
  codeRenderStatus();
  toast(`저장했습니다: ${t.path}`);
  codeGitRefresh(true);
  return true;
}

async function codeReload(t, force = false) {
  if (codeTabElsewhere(t, "다시 열려면")) return;
  if (!force && t.editor.isDirty()) {
    const ok = await codeChoose("다시 열기", h("p", {}, "저장하지 않은 내 변경이 사라집니다. 다시 열까요?"),
      [{ label: "취소", value: false }, { label: "다시 열기", class: "danger", value: true }]);
    if (!ok) return;
  }
  const res = await codeCall(api().code_open(t.path));
  if (!res) return;
  t.file = res.file;
  t.editor.setText(res.file.text);
  t.editor.setReadOnly(res.file.readonly);
  t.diskChanged = false;
  t._dirty = false;
  codeRenderTabs();
  codeRenderActive();
}

/* 창으로 돌아올 때 열린 파일이 디스크에서 바뀌었는지 본다 */
async function codeCheckDisk() {
  for (const t of CODE.tabs) {
    if (t.kind !== "file" || !codeTabHere(t)) continue;   // 2.0: 다른 작업 폴더의 탭은 새 폴더 파일과 비교하지 않는다
    const res = await codeCall(api().code_hash(t.path), true);
    if (!res || res.hash === t.file.hash) continue;
    if (!t.editor.isDirty() && res.hash !== "absent") await codeReload(t, true);
    else t.diskChanged = true;
  }
  codeRenderNotice();
}

/* ---------- 저장하지 않은 내용 임시 보관(복구용, 이 기기의 화면 저장소) ---------- */

function codeDrafts() {
  try { return JSON.parse(localStorage.getItem(CODE_DRAFTS) || "{}"); } catch { return {}; }
}

function codeDraftSave(t) {
  if (t.kind !== "file") return;
  const all = codeDrafts();
  const key = (t.wsPath != null ? t.wsPath : CODE.state ? CODE.state.workspace.path : "") + "|" + t.path;  // 2.0: 탭을 연 폴더 기준
  if (!t.editor.isDirty()) delete all[key];
  else {
    const text = t.editor.getText();
    if (text.length > 1024 * 1024) return;
    all[key] = { hash: t.file.hash, text, at: Date.now() };
  }
  try { localStorage.setItem(CODE_DRAFTS, JSON.stringify(all)); } catch { /* 저장소가 가득 참 */ }
}

function codeDraftDrop(path, wsPath) {
  const all = codeDrafts();
  delete all[(wsPath != null ? wsPath : CODE.state ? CODE.state.workspace.path : "") + "|" + path];
  try { localStorage.setItem(CODE_DRAFTS, JSON.stringify(all)); } catch { /* 무시 */ }
}

function codeOfferDraft(t) {
  const d = codeDrafts()[(CODE.state ? CODE.state.workspace.path : "") + "|" + t.path];
  if (d && d.hash === t.file.hash && d.text !== t.file.text) { t.draft = d; codeRenderNotice(); }
  else if (d) codeDraftDrop(t.path);
}

/* ---------- AI에게 묻기 ---------- */

function codeAskMenu(t, anchor) {
  document.querySelector(".code-menu")?.remove();
  const sel = t.editor.selection();
  const scope = h("select", { "aria-label": "보낼 범위", class: "code-scope" },
    h("option", { value: "selection", selected: !sel.empty, disabled: sel.empty }, sel.empty ? "선택한 부분(선택 없음)" : `선택한 부분 (${sel.fromLine}-${sel.toLine}줄)`),
    h("option", { value: "block", selected: sel.empty }, "현재 함수·블록"),
    h("option", { value: "file" }, "파일 전체"),
    h("option", { value: "files" }, "관련 파일 함께(고르기)"));
  const menu = h("div", { class: "code-menu", role: "menu" },
    h("label", { class: "code-menu-scope" }, "범위 ", scope),
    ...CODE_PRESETS.map(([k, label]) => h("button", { role: "menuitem", class: "code-menu-item", "data-preset": k,
      onclick: () => { menu.remove(); codeAsk(t, scope.value, k); } }, label)),
    h("p", { class: "muted code-menu-note" }, "보낸 코드는 지금 고른 AI 모델 API로 전송됩니다. 작업 폴더 전체를 보내지 않습니다."));
  document.body.append(menu);
  const r = anchor.getBoundingClientRect();
  menu.style.top = Math.min(window.innerHeight - menu.offsetHeight - 8, r.bottom + 4) + "px";
  menu.style.left = Math.max(8, Math.min(window.innerWidth - menu.offsetWidth - 8, r.right - menu.offsetWidth)) + "px";
  const away = (e) => { if (!menu.contains(e.target) && e.target !== anchor) { menu.remove(); document.removeEventListener("pointerdown", away, true); } };
  document.addEventListener("pointerdown", away, true);
  menu.addEventListener("keydown", (e) => { if (e.key === "Escape") { menu.remove(); anchor.focus(); } });
  (menu.querySelector(".code-menu-item") || scope).focus();
}

async function codeAsk(t, kind, preset) {
  const room = S.attachLimits.max_files - S.attach.length;
  if (room < 1) return toast(`파일은 한 번에 ${S.attachLimits.max_files}개까지 첨부할 수 있습니다`);
  const ed = t.editor;
  const req = { path: t.path, kind, preset };
  if (kind === "selection") {
    const s = ed.selection();
    if (s.empty) return toast("묻고 싶은 코드를 먼저 선택하세요");
    req.text = s.text;
    req.from_line = s.fromLine;
    req.to_line = s.toLine;
    if (s.toLine - s.fromLine < 200) {
      const from = Math.max(1, s.fromLine - 15);
      req.context = ed.lineText(from, Math.min(s.lines, s.toLine + 15));
      req.context_from = from;
    }
  } else if (kind === "block") {
    const b = ed.blockRange();
    req.text = ed.lineText(b.from, b.to);
    req.from_line = b.from;
    req.to_line = b.to;
  } else if (kind === "file") {
    req.text = ed.getText();
    req.from_line = 1;
    req.to_line = ed.selection().lines;
  } else if (kind === "files") {
    const paths = await codePickFiles(t.path, Math.min(6, room));
    if (!paths) return;
    req.paths = paths;
  }
  const res = await codeCall(api().code_ask(req));
  if (!res) return;
  for (const a of res.attachments) S.attach.push({ id: a.id, name: a.name, size: a.size, kind: a.kind, status: "ready", progress: 1 });
  renderTray();
  const input = $("#input");
  if (!input.value.trim()) input.value = res.question;
  autoresize();
  updateSend();
  codeLeave();  // 채팅으로 돌아가 묻는다(열린 탭·저장하지 않은 내용은 그대로 남고, 사이드바 '코드'로 다시 온다)
  input.focus();
  input.select();
  toast("코드를 첨부했습니다. 질문을 고쳐 보내세요");
}

async function codePickFiles(current, max) {
  const choices = [...new Set([current, ...CODE.tabs.filter((t) => t.kind === "file").map((t) => t.path), ...((CODE.state && CODE.state.recent) || [])])].slice(0, 20);
  const boxes = choices.map((p) => h("label", { class: "code-pick" },
    h("input", { type: "checkbox", value: p, checked: p === current }), " ", p));
  const ok = await codeChoose("함께 보낼 파일", h("div", {},
    h("p", { class: "muted" }, `열린 파일과 최근 파일에서 ${max}개까지 고르세요. 고른 파일만 AI에게 보냅니다.`), ...boxes),
  [{ label: "취소", value: false }, { label: "첨부", class: "primary", value: true }]);
  if (!ok) return null;
  const paths = boxes.map((b) => b.querySelector("input")).filter((i) => i.checked).map((i) => i.value).slice(0, max);
  if (!paths.length) { toast("파일을 고르세요"); return null; }
  return paths;
}

/* ---------- 아래 패널(1.18: 터미널) ---------- */

function codeBottom(k = "terminal", toggle = false) {
  if (k === "git" || k === "review") return codeSide(k);   // 예전 이름: 왼쪽 패널로 옮겼다
  CODE.bottomOpen = toggle ? !CODE.bottomOpen : true;
  $("#code-pane").classList.toggle("bottom-closed", !CODE.bottomOpen);
  // 사용자가 연 것이면(Ctrl+`·제목 누름) 터미널로 초점을 옮긴다
  if (CODE.bottomOpen && CODE.open && window.termEnsure) termEnsure().then(() => { if (toggle && window.termFocus) termFocus(); });
}

/* ---------- 변경 검토 ---------- */

function codeRenderReviewBadge() {
  const n = ((CODE.state && CODE.state.proposals) || []).filter((p) => p.status === "pending").length;
  const tab = $("#code-side-review");
  if (tab) tab.textContent = n ? `변경 검토 (${n})` : "변경 검토";
}

function codeRenderReviewList() {
  if (CODE.side !== "review") return;
  const body = $("#code-side-body");
  if (!body) return;
  const list = (CODE.state && CODE.state.proposals) || [];
  if (!codeFeature("review")) {
    body.replaceChildren(h("p", { class: "muted code-empty" }, "이 기기에서는 덩어리별 검토를 쓰지 않습니다. 에이전트 수정은 승인 창에서 전체를 받아들이거나 거부합니다."));
    return;
  }
  if (!list.length) {
    body.replaceChildren(h("p", { class: "muted code-empty" },
      "에이전트가 파일을 고치면 여기에 변경 제안이 뜹니다. 받아들이기 전에는 파일에 적용되지 않습니다. ",
      CODE.state && CODE.state.settings.review === "off" ? "(지금은 '항상 승인 창으로'로 설정돼 있습니다.)" : ""));
    return;
  }
  body.replaceChildren(h("ul", { class: "code-list" }, ...list.map((p) => h("li", {},
    h("button", { class: "code-item" + (p.status === "pending" ? " pending" : ""), onclick: () => codeOpenReview(p.id) },
      h("span", { class: `code-badge st-${p.status}` }, CODE_STATUS[p.status] || p.status),
      h("span", { class: "code-item-path" }, p.path + (p.new_file ? " (새 파일)" : "")),
      h("small", {}, `+${p.added} −${p.removed} · 덩어리 ${p.hunk_count}개${p.reason ? " · " + p.reason : ""}${p.message ? " · " + p.message : ""}`))))));
}

async function codeOpenReview(id) {
  if (!CODE.open) await codeShow();
  const res = await codeCall(api().code_proposal(id));
  if (!res) return;
  const p = res.proposal;
  let t = CODE.tabs.find((x) => x.kind === "review" && x.proposalId === id);
  if (!t) t = codeNewTab({ kind: "review", proposalId: id, path: p.path, title: codeBase(p.path) });
  t.data = p;
  if (!t.accepted || p.status !== "pending") t.accepted = new Set(p.status === "pending" ? p.hunks.map((x) => x.id) : p.accepted);
  codeRenderReview(t);
  codeActivate(t.id);
}

function codeRenderReview(t) {
  const p = t.data;
  const pending = p.status === "pending";
  const count = () => `${t.accepted.size}/${p.hunks.length}개 받아들임`;
  const counter = h("span", { class: "code-review-count" }, count());
  const hunks = p.hunks.map((hk) => {
    const box = h("input", { type: "checkbox", checked: t.accepted.has(hk.id), disabled: !pending,
      "aria-label": `덩어리 ${hk.id + 1} 받아들이기` });
    const el = h("section", { class: "code-hunk" + (t.accepted.has(hk.id) ? "" : " rejected"), "data-hunk": String(hk.id) },
      h("div", { class: "code-hunk-head" },
        h("label", {}, box, ` 덩어리 ${hk.id + 1}`),
        h("code", {}, hk.header),
        h("span", { class: "code-hunk-stat" }, `+${hk.added} −${hk.removed}`),
        pending ? h("button", { class: "btn", onclick: () => { t.accepted = new Set([hk.id]); codeRenderReview(t); } }, "이것만") : null),
      h("pre", { class: "diff code-diff" }, ...hk.lines.map((ln) => h("div", { class: ln.t === "+" ? "add" : ln.t === "-" ? "del" : "" },
        h("span", { class: "ln" }, ln.old == null ? "" : String(ln.old)), h("span", { class: "ln" }, ln.new == null ? "" : String(ln.new)),
        h("span", { class: "mk" }, ln.t), ln.text || " "))));
    box.addEventListener("change", () => {
      if (box.checked) t.accepted.add(hk.id); else t.accepted.delete(hk.id);
      el.classList.toggle("rejected", !box.checked);
      counter.textContent = count();
    });
    return el;
  });
  t.el.replaceChildren(h("div", { class: "code-review" },
    h("div", { class: "code-review-head" },
      h("div", {},
        h("strong", {}, p.path), p.new_file ? " (새 파일)" : "",
        CODE.state && p.workspace && CODE.state.workspace.path && !p.workspace.endsWith(CODE.state.workspace.name)
          ? h("span", { class: "code-warn" }, ` (다른 작업 폴더: ${p.workspace})`) : null,
        h("span", { class: `code-badge st-${p.status}` }, CODE_STATUS[p.status] || p.status),
        h("div", { class: "muted" }, [p.title, p.reason ? `이유: ${p.reason}` : "", p.source === "agent" ? "에이전트 제안" : "", p.message].filter(Boolean).join(" · "))),
      p.conflict ? h("p", { class: "code-warn" }, "검토하는 사이에 파일이 바뀌었습니다. 그대로 덮어쓰지 않습니다. '현재 파일에 맞춰 적용'은 덩어리 앞뒤 문맥이 그대로인 경우에만 됩니다.") : null),
    pending ? h("div", { class: "code-review-actions" },
      counter,
      h("button", { class: "btn primary", id: "code-apply", onclick: () => codeApply(t) }, "고른 변경 적용"),
      h("button", { class: "btn", onclick: () => { t.accepted = new Set(p.hunks.map((x) => x.id)); codeApply(t); } }, "모두 적용"),
      h("button", { class: "btn danger", id: "code-reject", onclick: () => codeReject(t) }, "모두 거부"),
      h("button", { class: "btn", onclick: () => codeEditThenApply(t) }, "고쳐서 적용")) : null,
    ...hunks));
}

async function codeApply(t, rebase = false) {
  const p = t.data;
  const ids = [...t.accepted];
  if (!ids.length) return codeReject(t);
  const pre = await codeCall(api().code_review_preview(p.id, ids));
  if (!pre) return;
  if (pre.warning) {
    const ok = await codeChoose("적용 결과 확인", h("div", {}, h("p", {}, pre.warning),
      h("p", { class: "muted" }, "일부 덩어리만 받아들이면 서로 기대는 변경이 빠져 코드가 깨질 수 있습니다.")),
    [{ label: "취소", value: false }, { label: "그래도 적용", class: "danger", value: true }]);
    if (!ok) return;
  }
  const res = await codeCall(api().code_review_apply(p.id, ids, null, rebase));
  if (!res) return;
  if (res.conflict) {
    const v = await codeChoose("파일이 바뀌었습니다", h("p", {}, res.error),
      [{ label: "취소", value: null }, { label: "거부", class: "danger", value: "reject" }, ...(rebase ? [] : [{ label: "현재 파일에 맞춰 적용", class: "primary", value: "rebase" }])]);
    if (v === "rebase") return codeApply(t, true);
    if (v === "reject") return codeReject(t);
    return;
  }
  toast(res.result.status === "partial" ? `덩어리 ${res.result.accepted.length}/${res.result.total}개를 적용했습니다` : "변경을 적용했습니다");
  await codeAfterReview(t, res.proposal);
}

async function codeReject(t) {
  const res = await codeCall(api().code_review_reject(t.data.id));
  if (!res) return;
  toast("변경을 거부했습니다. 파일은 그대로입니다");
  await codeAfterReview(t, res.proposal);
}

async function codeEditThenApply(t) {
  const p = t.data;
  const host = h("div", { class: "code-modal-editor" });
  const nl = /\r\n/.test(p.original || "") ? "\r\n" : "\n";
  let editor = null;
  let done = false;
  const finish = async (close, apply) => {
    if (!apply) { done = true; close(); editor.destroy(); return; }
    const text = editor.getText().replace(/\n/g, nl);  // 원래 줄 끝으로
    const res = await codeCall(api().code_review_apply(p.id, [], text));
    if (!res || res.conflict) { if (res) toast(res.error); return; }
    done = true;
    close();
    editor.destroy();
    toast("고친 내용으로 적용했습니다");
    await codeAfterReview(t, res.proposal);
  };
  modal({
    title: `고쳐서 적용: ${p.path}`, wide: true, body: h("div", {}, h("p", { class: "muted" }, "에이전트가 제안한 내용입니다. 고친 뒤 '이 내용으로 적용'을 누르세요."), host),
    buttons: [{ label: "취소", action: (close) => finish(close, false) }, { label: "이 내용으로 적용", class: "primary", action: (close) => finish(close, true) }],
    onClose: () => { if (!done && editor) editor.destroy(); },
  });
  editor = codeEditorTab(host, (p.proposed || "").replace(/\r\n/g, "\n"), p.language, false, () => {}, () => {});
}

async function codeAfterReview(t, proposal) {
  const list = CODE.state.proposals;
  const i = list.findIndex((x) => x.id === proposal.id);
  if (i >= 0) list[i] = proposal; else list.unshift(proposal);
  await codeOpenReview(proposal.id);
  codeRenderReviewList();
  codeRenderReviewBadge();
  const ft = CODE.tabs.find((x) => x.kind === "file" && x.path === proposal.path && codeTabHere(x));
  if (ft && !ft.editor.isDirty()) await codeReload(ft, true);
  else if (ft) { ft.diskChanged = true; codeRenderNotice(); }
  codeGitRefresh(true);
}

/* ---------- Git ---------- */

async function codeGitRefresh(quiet = false) {
  if (!codeFeature("git") || !CODE.open || CODE.gitBusy) return;
  CODE.gitBusy = true;
  try {
    const res = await codeCall(api().code_git_status(), quiet);
    CODE.git = res ? res.git : null;
  } finally {
    CODE.gitBusy = false;
  }
  codeRenderTree();
  if (CODE.side === "git") codeRenderGit(false);
}

function codeRenderGit(load) {
  const body = $("#code-side-body");
  if (!body || CODE.side !== "git") return;
  if (!codeFeature("git")) {
    body.replaceChildren(h("p", { class: "muted code-empty" }, CODE.state && CODE.state.platform === "android"
      ? "안드로이드에서는 Git 기능을 쓸 수 없습니다." : "git이 설치되어 있지 않습니다. https://git-scm.com 에서 설치하세요."));
    return;
  }
  if (load) { body.replaceChildren(h("p", { class: "muted code-empty" }, "Git 상태를 읽는 중…")); codeGitRefresh(); return; }
  const g = CODE.git;
  if (!g) { body.replaceChildren(h("p", { class: "muted code-empty" }, "Git 상태를 읽지 못했습니다.")); return; }
  if (!g.repo) {
    body.replaceChildren(h("p", { class: "muted code-empty" }, g.reason || "Git 저장소가 아닙니다.",
      " 터미널에서 git init으로 저장소를 만들거나, 저장소 폴더를 작업 폴더로 고르세요."));
    return;
  }
  const groups = [["충돌", (f) => f.conflict], ["스테이지됨", (f) => f.staged], ["바뀜(스테이지 안 됨)", (f) => f.unstaged], ["새 파일", (f) => f.untracked]];
  const row = (f, staged) => {
    const key = (staged ? "s:" : "w:") + f.path;
    const box = h("input", { type: "checkbox", checked: CODE.gitPick.has(key), "aria-label": `${f.path} 고르기`,
      onchange: () => { if (box.checked) CODE.gitPick.add(key); else CODE.gitPick.delete(key); } });
    return h("li", { class: "code-git-row" }, box,
      h("button", { class: "code-git-file", title: "차이 보기", onclick: () => codeGitDiff(f.path, staged) },
        h("span", { class: "code-git-label" }, f.label), f.path + (f.orig ? ` ← ${f.orig}` : "")),
      h("button", { class: "icon-btn", title: "파일 열기", "aria-label": `${f.path} 열기`, html: ICONS.file, onclick: () => codeOpenFile(f.path) }));
  };
  const sections = groups.map(([label, test]) => {
    const files = g.files.filter(test);
    if (!files.length) return null;
    return h("section", {}, h("h4", {}, `${label} ${files.length}`), h("ul", { class: "code-list" }, ...files.map((f) => row(f, label === "스테이지됨"))));
  }).filter(Boolean);
  const msg = h("textarea", { class: "code-input code-commit-msg", rows: "2", id: "code-commit-msg", placeholder: "커밋 메시지 (예: fix: correct ADC quantization handling)",
    "aria-label": "커밋 메시지" });
  if (CODE.commitDraft) msg.value = CODE.commitDraft;
  msg.addEventListener("input", () => { CODE.commitDraft = msg.value; });
  const picked = (staged) => [...CODE.gitPick].filter((k) => k.startsWith(staged ? "s:" : "w:")).map((k) => k.slice(2));
  body.replaceChildren(h("div", { class: "code-git" },
    h("div", { class: "code-git-head" },
      h("strong", {}, g.detached ? "(분리된 HEAD)" : `가지: ${g.branch || "?"}`),
      g.upstream ? h("small", {}, ` ${g.upstream} · 앞섬 ${g.ahead} · 뒤처짐 ${g.behind}`) : null,
      g.conflicts ? h("span", { class: "code-warn" }, ` 충돌 ${g.conflicts}개`) : null,
      h("span", { style: "flex:1" }),
      h("button", { class: "icon-btn", title: "새로 고침", "aria-label": "Git 새로 고침", html: ICONS.retry, onclick: () => codeGitRefresh() })),
    g.files.length ? null : h("p", { class: "muted" }, "바뀐 파일이 없습니다."),
    ...sections,
    g.outside ? h("p", { class: "muted" }, `작업 폴더 밖(저장소의 다른 폴더)의 변경 ${g.outside}개는 보이지 않습니다.`) : null,
    h("div", { class: "code-git-actions" },
      h("button", { class: "btn", onclick: () => codeGitStage(picked(false), true) }, "고른 파일 스테이지"),
      h("button", { class: "btn", onclick: () => codeGitStage(picked(true), false) }, "스테이지 취소"),
      h("button", { class: "btn", onclick: () => codeGitAsk("explain") }, "AI: 변경 설명"),
      h("button", { class: "btn", onclick: () => codeGitAsk("review") }, "AI: 코드 리뷰"),
      h("button", { class: "btn", onclick: () => codeGitAsk("commit") }, "AI: 커밋 메시지 제안")),
    h("div", { class: "code-commit" }, msg,
      h("button", { class: "btn primary", id: "code-commit", onclick: () => codeGitCommit(msg.value) }, "스테이지한 변경 커밋")),
    h("p", { class: "muted" }, "스테이지·커밋은 고른 파일만 합니다. 푸시·되돌리기(reset·clean·checkout)는 이 화면에 없습니다.")));
}

async function codeGitStage(paths, stage) {
  if (!paths.length) return toast(stage ? "스테이지할 파일을 고르세요(바뀜·새 파일)" : "스테이지를 취소할 파일을 고르세요(스테이지됨)");
  const res = await codeCall(stage ? api().code_git_stage(paths) : api().code_git_unstage(paths));
  if (!res) return;
  CODE.gitPick.clear();
  codeGitRefresh();
}

async function codeGitDiff(path, staged) {
  const res = await codeCall(api().code_git_diff(path, staged));
  if (!res) return;
  let t = CODE.tabs.find((x) => x.kind === "diff" && x.path === path && x.staged === staged);
  if (!t) t = codeNewTab({ kind: "diff", path, staged, title: codeBase(path) });
  const text = res.diff.diff || "(차이 없음)";
  t.el.replaceChildren(h("div", { class: "code-review" },
    h("div", { class: "code-review-head" }, h("strong", {}, path), h("span", { class: "muted" }, staged ? " · 스테이지된 차이" : " · 작업 폴더의 차이"),
      res.diff.truncated ? h("span", { class: "muted" }, " · 길어서 앞부분만") : null),
    h("div", { class: "code-review-actions" },
      h("button", { class: "btn", onclick: () => codeGitAsk("explain", path, staged) }, "AI: 이 변경 설명"),
      h("button", { class: "btn", onclick: () => codeGitAsk("review", path, staged) }, "AI: 이 변경 리뷰")),
    diffOrPre(text.startsWith("diff --git") ? text.slice(text.indexOf("--- ")) : text)));
  codeActivate(t.id);
}

async function codeGitAsk(kind, path = "", staged = false) {
  if (S.attach.length >= S.attachLimits.max_files) return toast(`파일은 한 번에 ${S.attachLimits.max_files}개까지 첨부할 수 있습니다`);
  const res = await codeCall(api().code_git_ask(kind, path, staged));
  if (!res) return;
  for (const a of res.attachments) S.attach.push({ id: a.id, name: a.name, size: a.size, kind: a.kind, status: "ready", progress: 1 });
  renderTray();
  const input = $("#input");
  if (!input.value.trim()) input.value = res.question;
  autoresize();
  updateSend();
  if (isNarrow()) codeLeave();
  input.focus();
  toast(kind === "commit" ? "스테이지한 변경을 첨부했습니다. 보내면 커밋 메시지를 제안합니다(커밋은 직접 합니다)" : "변경을 첨부했습니다. 질문을 고쳐 보내세요");
}

async function codeGitCommit(message) {
  if (!String(message || "").trim()) return toast("커밋 메시지를 입력하세요");
  const staged = (CODE.git && CODE.git.files || []).filter((f) => f.staged);
  if (!staged.length) return toast("스테이지한 변경이 없습니다");
  const hooks = (CODE.git && CODE.git.hooks) || [];
  const skip = h("input", { type: "checkbox", id: "code-no-verify" });
  const ok = await codeChoose("커밋", h("div", {},
    h("p", {}, "다음 파일의 스테이지한 변경만 커밋합니다. 푸시는 하지 않습니다."),
    h("ul", {}, ...staged.map((f) => h("li", {}, `${f.label} ${f.path}`))),
    h("pre", { class: "code-commit-preview" }, message),
    hooks.length ? h("div", { class: "code-warn" },
      h("p", {}, `이 저장소의 커밋 훅이 실행됩니다: ${hooks.join(", ")}. 훅은 저장소에 들어 있는 프로그램입니다. 믿을 수 없는 저장소라면 실행하지 마세요.`),
      h("label", {}, skip, " 이번 커밋에서 훅을 실행하지 않기(--no-verify)")) : null),
  [{ label: "취소", value: false }, { label: "커밋", class: "primary", value: true }]);
  if (!ok) return;
  const res = await codeCall(api().code_git_commit(message, skip.checked));
  if (!res) return;
  CODE.commitDraft = "";
  toast(`커밋했습니다: ${res.commit}`);
  codeGitRefresh();
}

/* ---------- 명령 실행 기록(에이전트·Lab의 실행 알림) ---------- */

function codeRunLabel(r) {
  return { running: "실행 중", stopping: "멈추는 중", done: `완료 ${r.code}`, failed: `실패 ${r.code}`, stopped: "멈춤", timeout: "시간 초과", error: "오류" }[r.status] || r.status;
}

/* ---------- 백엔드 이벤트 ---------- */

function codeEvent(ev) {
  if (window.caEvent && ev.kind && (ev.kind.startsWith("agent_") || ev.kind === "run_output")) {
    caEvent(ev);
    if (ev.kind !== "run_output") return;
  }
  if (ev.kind === "proposal") {
    if (!CODE.state) return;
    const list = CODE.state.proposals;
    const i = list.findIndex((p) => p.id === ev.proposal.id);
    if (i >= 0) list[i] = ev.proposal; else list.unshift(ev.proposal);
    codeRenderReviewBadge();
    codeRenderReviewList();
    const tab = CODE.tabs.find((t) => t.kind === "review" && t.proposalId === ev.proposal.id);
    if (tab && tab.data && tab.data.status !== ev.proposal.status) codeOpenReview(ev.proposal.id);
    if (ev.proposal.status === "pending" && ev.new !== false && CODE.open) {
      codeSide("review");
      codeOpenReview(ev.proposal.id);
      toast(`에이전트가 ${ev.proposal.path}을(를) 고치려고 합니다. 덩어리를 골라 적용하세요`);
    }
  } else if (ev.kind === "file_changed") {
    const t = CODE.tabs.find((x) => x.kind === "file" && x.path === ev.path && codeTabHere(x));
    if (t && t.file.hash !== ev.hash && ev.by !== "editor") {
      if (!t.editor.isDirty()) codeReload(t, true);
      else { t.diskChanged = true; codeRenderNotice(); }
    }
    if (CODE.open) codeGitRefresh(true);
  } else if (ev.kind === "run_start" || ev.kind === "run_exit") {
    const r = ev.run;
    const i = CODE.runs.findIndex((x) => x.id === r.id);
    if (i >= 0) CODE.runs[i] = r; else CODE.runs.unshift(r);
    if (ev.kind === "run_exit") {
      codeGitRefresh(true);
      // 1.17.2: 에이전트·! 명령의 결과는 작업 탭에 보이므로, 그 탭을 보고 있으면 알리지 않는다
      const inTerminal = String(r.purpose || "").startsWith("Code 에이전트") && window.caVisible && caVisible();
      if (!inTerminal) toast(`명령이 끝났습니다: ${codeRunLabel(r)}`);
    }
  } else if (ev.kind === "term_output" || ev.kind === "term_exit") {
    if (window.termEvent) termEvent(ev);
  } else if (ev.kind && ev.kind.startsWith("ssh_")) {
    if (window.sshEvent) sshEvent(ev);
  }
}

function codeInit() {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  CODE.dark = media.matches;
  const onTheme = () => {
    CODE.dark = media.matches;
    for (const t of CODE.tabs) if (t.editor) t.editor.setDark(CODE.dark);
    if (window.termSetTheme) termSetTheme();
  };
  if (media.addEventListener) media.addEventListener("change", onTheme);
  $("#btn-code")?.addEventListener("click", () => codeToggle());
  window.addEventListener("focus", () => { if (CODE.open) codeCheckDisk(); });
  // 1.18: Ctrl+` 터미널 열기·접기(VS Code처럼), 창 크기가 바뀌면 터미널 폭을 다시 맞춘다
  document.addEventListener("keydown", (e) => {
    if (!CODE.open || !e.ctrlKey || e.altKey || e.metaKey || e.code !== "Backquote") return;
    if (e.target && e.target.closest && e.target.closest(".code-term")) return;   // 터미널 안에서는 code-term.js가 처리
    e.preventDefault();
    codeBottom("terminal", true);
  });
  let fitTimer = null;
  window.addEventListener("resize", () => { clearTimeout(fitTimer); fitTimer = setTimeout(() => window.termFit && termFit(), 80); });
}

window.codeShow = codeShow;
window.codeLeave = codeLeave;
window.codeEvent = codeEvent;
window.codeOpenFile = codeOpenFile;
codeInit();
