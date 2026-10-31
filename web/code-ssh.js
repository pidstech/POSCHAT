// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

/* ---------- 코드 화면의 원격(SSH) 작업 폴더(1.18) ----------
   코드 화면 위의 'SSH'로 서버에 연결하고 폴더를 고르면, 파일·Git·터미널·Code 에이전트가 그 서버에서 돈다(백엔드 ssh_api.py).
   - 연결은 뒤에서 하고 진행은 ssh_state 이벤트로 온다. 호스트 키 확인·암호·OTP·키 암호문은 ssh_prompt 이벤트로 묻는다.
   - 암호·OTP는 저장하지 않는다. 최근에 연 원격 폴더는 다시 열기 쉽게 목록으로 보인다. */

const SSH = { modal: null, target: "", pending: null, states: {}, prompts: new Map(), hidden: false, folder: null };

const sshState = (t) => (SSH.states[t] || {}).state || "closed";

async function sshOpen(prefill = "") {
  const res = await codeCall(api().code_ssh_hosts());
  if (!res) return;
  if (!res.supported) { toast("이 기기에서는 SSH 원격 작업 폴더를 쓸 수 없습니다(PC 앱에서 쓰세요)"); return; }
  for (const [t, s] of Object.entries(res.states || {})) SSH.states[t] = { ...(SSH.states[t] || {}), state: s };
  const cur = res.current;
  const input = h("input", { type: "text", id: "ssh-target", class: "code-input", list: "ssh-hosts", spellcheck: "false",
    autocomplete: "off", value: prefill || (cur && cur.target) || SSH.target || "",
    placeholder: "user@server.postech.ac.kr 또는 ~/.ssh/config의 Host 이름", "aria-label": "연결할 서버" });
  const list = h("datalist", { id: "ssh-hosts" },
    ...(res.hosts || []).map((x) => h("option", { value: x.name }, `${x.user ? x.user + "@" : ""}${x.hostname}${x.port !== 22 ? ":" + x.port : ""}`)));
  const go = h("button", { class: "btn primary", id: "ssh-connect", type: "button", onclick: () => sshConnect(input.value) }, "연결");
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); sshConnect(input.value); } });
  const recent = (res.recent || []).length ? h("div", { class: "ssh-recent" },
    h("div", { class: "ssh-sub" }, "최근에 연 원격 폴더"),
    ...res.recent.map((r) => h("div", { class: "ssh-recent-row" },
      h("button", { class: "ssh-recent-open", type: "button", title: "연결하고 이 폴더 열기", onclick: () => sshQuick(r.target, r.path) },
        h("b", {}, r.target), h("span", {}, ":" + r.path)),
      h("button", { class: "icon-btn", type: "button", title: "목록에서 빼기", "aria-label": `${r.target}:${r.path} 목록에서 빼기`, html: ICONS.close,
        onclick: async (e) => { await api().code_ssh_forget(r.target, r.path); e.target.closest(".ssh-recent-row")?.remove(); } })))) : null;
  const body = h("div", { class: "ssh-dialog" },
    h("p", { class: "muted ssh-help" }, "SSH 서버의 폴더를 코드 화면에서 엽니다. 파일·검색·Git·터미널·Code 에이전트가 모두 서버에서 돕니다. ",
      "서버에는 python3(3.6 이상)만 있으면 되고, 아무것도 설치하지 않습니다. 키·SSH 에이전트·~/.ssh/config(ProxyJump 포함)를 그대로 쓰고, ",
      "암호·OTP는 물어볼 때만 쓰고 저장하지 않습니다."),
    h("div", { class: "ssh-row" }, input, go), list,
    h("div", { class: "ssh-status", id: "ssh-status", role: "status", "aria-live": "polite" }),
    h("div", { class: "ssh-browser", id: "ssh-browser", hidden: true }),
    recent);
  const buttons = [];
  if (cur) {
    buttons.push({ label: "로컬 작업 폴더로", action: (close) => { close(); sshLocal(); } });
    if (cur.connected) buttons.push({ label: "연결 끊기", action: (close) => { close(); sshDisconnect(cur.target); } });
  }
  buttons.push({ label: "닫기", action: (close) => close() });
  SSH.modal = modal({ title: "SSH 원격 작업 폴더", wide: true, body, buttons, onClose: () => { SSH.modal = null; SSH.folder = null; } });
  const t = input.value.trim();
  if (t && sshState(t) === "connected") { SSH.target = t; sshBrowse(t, cur && cur.target === t ? cur.path : ""); }
  sshStatus();
  setTimeout(() => input.focus(), 30);
}

function sshStatus() {
  const box = $("#ssh-status");
  if (!box) return;
  const t = SSH.target;
  const st = SSH.states[t];
  if (!t || !st) { box.replaceChildren(); return; }
  const label = { connecting: "연결 중", connected: "연결됨", failed: "연결하지 못함", cancelled: "취소함", lost: "연결이 끊김", closed: "연결 끊음" }[st.state] || st.state;
  box.className = "ssh-status " + st.state;
  box.replaceChildren(...[h("b", {}, `${t} — ${label}`), st.message ? h("span", {}, " · " + st.message) : null,
    st.state === "connecting" ? h("button", { class: "btn small", type: "button", onclick: () => api().code_ssh_cancel(t) }, "취소") : null]
    .filter(Boolean));
  const btn = $("#ssh-connect");
  if (btn) btn.disabled = st.state === "connecting";
}

async function sshConnect(target, pending = null) {
  target = String(target || "").trim();
  if (!target) { toast("연결할 서버를 쓰세요"); return; }
  const r = await codeCall(api().code_ssh_connect(target));
  if (!r) return;
  SSH.target = r.target;
  SSH.pending = pending;
  SSH.states[r.target] = { ...(SSH.states[r.target] || {}), state: r.state };
  sshStatus();
  if (r.state === "connected") sshConnected(r.target);
}

function sshConnected(target) {
  const p = SSH.pending;
  SSH.pending = null;
  if (p && p.target === target) {
    if (p.reopen) { toast(`다시 연결했습니다: ${target}`); codeRefreshState(); return; }
    if (p.path) { sshOpenFolder(target, p.path); return; }
  }
  if (SSH.modal && SSH.target === target) sshBrowse(target, "");
}

/* 최근 목록: 연결돼 있으면 바로 열고, 아니면 연결한 뒤 연다 */
function sshQuick(target, path) {
  if (sshState(target) === "connected") { sshOpenFolder(target, path); return; }
  const input = $("#ssh-target");
  if (input) input.value = target;
  sshConnect(target, { target, path });
}

function sshReconnect() {
  const cur = CODE.state && CODE.state.remote;
  if (!cur) return;
  toast(`${cur.target}에 다시 연결합니다`);
  sshConnect(cur.target, { target: cur.target, reopen: true });
}

async function sshBrowse(target, path) {
  const box = $("#ssh-browser");
  if (!box) return;
  let r;
  try {
    r = await api().code_ssh_browse(target, path);
  } catch (e) {
    r = { ok: false, error: e.message || String(e) };
  }
  if (!box.isConnected) return;
  if (!r || r.ok === false) {
    // 1.19.1: 연결 직후 목록을 못 받으면 빈 칸으로 두지 않고 이유와 '다시 시도'를 보인다
    box.hidden = false;
    box.replaceChildren(h("div", { class: "ssh-row" },
      h("span", { class: "muted", style: "flex:1", role: "alert" }, `폴더 목록을 불러오지 못했습니다: ${(r && r.error) || "알 수 없는 오류"}`),
      h("button", { class: "btn", type: "button", id: "ssh-browse-retry", onclick: () => sshBrowse(target, path) }, "다시 시도")));
    return;
  }
  const f = r.folder;
  SSH.folder = f;
  const where = h("input", { type: "text", class: "code-input", value: f.path, spellcheck: "false", autocomplete: "off",
    "aria-label": "서버의 폴더 경로" });
  where.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); sshBrowse(target, where.value); } });
  const dirs = f.dirs.filter((d) => SSH.hidden || !d.hidden);
  const item = (label, path, extra = "") => h("button", { class: "ssh-dir" + extra, type: "button", role: "option",
    ondblclick: () => sshOpenFolder(target, path), onclick: () => sshBrowse(target, path) }, label);
  box.hidden = false;
  box.replaceChildren(
    h("div", { class: "ssh-sub" }, `${target}에서 열 폴더를 고르세요`),
    h("div", { class: "ssh-row" }, where,
      h("button", { class: "btn", type: "button", onclick: () => sshBrowse(target, where.value) }, "이동"),
      h("button", { class: "btn", type: "button", title: "홈 폴더", onclick: () => sshBrowse(target, "") }, "~")),
    h("div", { class: "ssh-dirs", role: "listbox", "aria-label": "하위 폴더" },
      f.parent ? item("⬆ 상위 폴더", f.parent, " up") : null,
      ...dirs.map((d) => item("📁 " + d.name + (d.link ? " ↪" : ""), (f.path === "/" ? "" : f.path) + "/" + d.name)),
      dirs.length ? null : h("div", { class: "muted ssh-empty" }, "하위 폴더가 없습니다")),
    h("div", { class: "ssh-row ssh-open-row" },
      h("label", { class: "ssh-hidden" }, h("input", { type: "checkbox", checked: SSH.hidden,
        onchange: (e) => { SSH.hidden = e.target.checked; sshBrowse(target, f.path); } }), " 숨김 폴더"),
      f.git ? h("span", { class: "ssh-git" }, "Git 저장소") : null,
      h("span", { style: "flex:1" }),
      h("button", { class: "btn primary", id: "ssh-open", type: "button", onclick: () => sshOpenFolder(target, f.path) }, "이 폴더 열기")));
}

async function sshOpenFolder(target, path) {
  const r = await codeCall(api().code_ssh_open(target, path));
  if (!r) return;
  if (SSH.modal) SSH.modal.close();
  toast(`원격 작업 폴더를 열었습니다: ${r.current.label}`);
  await codeRefreshState();
}

async function sshLocal() {
  await api().code_ssh_local();
  toast("코드 화면을 로컬 작업 폴더로 되돌렸습니다");
  codeRefreshState();
}

async function sshDisconnect(target) {
  await api().code_ssh_disconnect(target);
  codeRefreshState();
}

/* ---------- 서버가 묻는 것(호스트 키·암호·OTP·키 암호문) ---------- */

function sshPrompt(ev) {
  let answered = false;
  const answer = (value, close) => { answered = true; close(); api().code_ssh_answer(ev.id, value); };
  let m;
  if (ev.prompt === "hostkey") {
    m = modal({
      title: "처음 연결하는 서버",
      body: h("div", { class: "ssh-hostkey" },
        h("p", {}, `${ev.host}에 처음 연결합니다. 서버의 지문이 서버 관리자가 알려 준 것과 같은지 확인하세요.`),
        h("div", { class: "ssh-fp" }, h("span", { class: "muted" }, ev.keytype), h("code", {}, ev.fingerprint)),
        h("p", { class: "muted" }, "받아들이면 POSCHAT이 이 지문을 기억하고, 다음부터 지문이 바뀌면 연결하지 않습니다.")),
      buttons: [{ label: "취소", action: (close) => answer(null, close) },
        { label: "받아들이고 연결", class: "primary", action: (close) => answer({ accept: true }, close) }],
      onClose: () => { if (!answered) { answered = true; api().code_ssh_answer(ev.id, null); } },
    });
  } else {
    const inputs = (ev.fields || []).map((f, i) => h("input", { type: f.secret ? "password" : "text", class: "code-input",
      autocomplete: "off", spellcheck: "false", "aria-label": f.label, id: `ssh-field-${i}`, inputmode: /otp|code|코드|인증/i.test(f.label) ? "numeric" : null }));
    const submit = (close) => answer({ values: inputs.map((x) => x.value) }, close);
    m = modal({
      title: ev.title || "로그인",
      body: h("form", { class: "ssh-secret", onsubmit: (e) => { e.preventDefault(); submit(m.close); } },
        h("p", { class: "muted" }, `${ev.host}: ${ev.message || ""}`),
        ...inputs.map((x, i) => h("label", { class: "ssh-field" }, h("span", {}, ev.fields[i].label), x)),
        h("button", { type: "submit", hidden: true })),
      buttons: [{ label: "취소", action: (close) => answer(null, close) },
        { label: "확인", class: "primary", action: (close) => submit(close) }],
      onClose: () => { if (!answered) { answered = true; api().code_ssh_answer(ev.id, null); } },
    });
    setTimeout(() => inputs[0] && inputs[0].focus(), 30);
  }
  SSH.prompts.set(ev.id, m);
}

function sshEvent(ev) {
  if (ev.kind === "ssh_prompt") { sshPrompt(ev); return; }
  if (ev.kind === "ssh_prompt_done") {
    const m = SSH.prompts.get(ev.id);
    SSH.prompts.delete(ev.id);
    if (m && m.box.isConnected) m.close();
    return;
  }
  if (ev.kind !== "ssh_state") return;
  SSH.states[ev.target] = { state: ev.state, message: ev.message || "" };
  if (ev.target === SSH.target) sshStatus();
  if (ev.state === "connected") sshConnected(ev.target);
  else if (["failed", "cancelled"].includes(ev.state) && SSH.pending && SSH.pending.target === ev.target) {
    SSH.pending = null;
    if (!SSH.modal) toast(ev.message || "연결하지 못했습니다");
  }
  const cur = CODE.state && CODE.state.remote;
  if (cur && cur.target === ev.target && ["connected", "lost", "closed"].includes(ev.state)) {
    if (ev.state === "lost") toast(`SSH 연결이 끊겼습니다: ${ev.target}`);
    if (CODE.open) codeRefreshState();
  }
}

window.sshOpen = sshOpen;
window.sshEvent = sshEvent;
window.sshReconnect = sshReconnect;
window.sshLocal = sshLocal;
