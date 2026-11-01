// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

/* ---------- 연결·도구 창(커넥터·MCP 서버·메모리·사용량)과 도구 화면(연구 라이브러리·에이전트 자동화) ----------
   app.js의 h(), modal(), api(), toast(), renderMarkdown(), copyText()를 쓴다.
   1.11: 연구 라이브러리와 에이전트 자동화는 창의 탭 대신 PO노트처럼 사이드바에서 여는 본문 화면(#tool-view)이다. */

const HUB = { tab: "connectors", modal: null, panel: null, tabs: null, open: new Set(), seq: 0 };
const HUB_TABS = [];  // [{ id, label, render(panel) }] — 아래에서 차례로 더한다

const CONN_STATE = {
  connected: ["연결됨", "st-ok"],
  needs_auth: ["인증 필요", "st-warn"],
  error: ["연결 오류", "st-err"],
  disabled: ["비활성화", ""],
  insufficient_scope: ["사용 권한 부족", "st-warn"],
  unavailable: ["이 기기에서 사용 불가", ""],
};
const KIND_LABEL = { read: "읽기", edit: "이 기기 수정", write: "쓰기", send: "전송", destructive: "삭제", exec: "실행" };
const ALWAYS_ASK = new Set(["send", "destructive", "exec"]);

// replaceChildren은 null을 "null" 글자로 넣으므로 빈 항목을 빼고 채운다
function fill(node, ...children) {
  node.replaceChildren(...children.flat().filter((c) => c != null && c !== false));
  return node;
}

function showHub(tab) {
  if (PAGES[tab]) return pageOpen(tab);  // 1.10의 탭 이름으로 부르면 1.11의 도구 화면을 연다
  if (tab) HUB.tab = tab;
  HUB.tabs = h("div", { class: "hub-tabs", role: "tablist" });
  HUB.panel = h("div", { class: "hub-panel" });
  HUB.modal = modal({
    title: "연결·도구",
    body: h("div", {}, HUB.tabs, HUB.panel),
    wide: true,
    buttons: [{ label: "닫기", class: "primary", value: null }],
    onClose: () => { HUB.modal = null; HUB.rendered = null; if (PAGE.id) renderPage(); },
  });
  renderHub();
  return HUB.modal;
}

function renderHub() {
  if (PAGE.id) renderPage();  // 열린 도구 화면도 같은 방식으로 다시 그린다(창에서 바꾼 설정이 바로 보이게)
  if (!HUB.modal) return;
  if (!HUB_TABS.some((t) => t.id === HUB.tab)) HUB.tab = HUB_TABS[0].id;
  HUB.tabs.replaceChildren(...HUB_TABS.map((t) => h("button", {
    class: "hub-tab" + (t.id === HUB.tab ? " active" : ""), role: "tab", "aria-selected": String(t.id === HUB.tab),
    onclick: () => { HUB.tab = t.id; renderHub(); },
  }, t.label)));
  const tab = HUB_TABS.find((t) => t.id === HUB.tab);
  // 같은 탭을 다시 그릴 때는 새 내용이 올 때까지 이전 내용을 둔다(깜빡임·스크롤 위치 튐 방지)
  // 2.0: 다른 탭으로 옮기면 패널을 새로 만든다. 늦게 끝난 이전 탭의 그리기는 떼어 낸 옛 패널에만 쓴다
  if (HUB.rendered !== tab.id) {
    const panel = h("div", { class: "hub-panel" }, h("small", { class: "muted" }, "불러오는 중..."));
    HUB.panel.replaceWith(panel);
    HUB.panel = panel;
  }
  HUB.rendered = tab.id;
  const seq = ++HUB.seq, panel = HUB.panel;
  Promise.resolve(tab.render(panel)).catch((e) => {
    if (seq !== HUB.seq || panel !== HUB.panel) return;   // 2.0: 그 사이 다른 그리기가 시작됐으면 오류도 보이지 않는다
    fill(panel, h("p", { class: "mcp-error" }, `불러오지 못했습니다: ${e.message || e}`));
  });
}

// 이 화면(창의 탭 또는 본문의 도구 화면)이 지금 보이는지
function hubShowing(id) {
  return PAGE.id === id || (!!HUB.modal && HUB.tab === id);
}

/* ---------- 도구 화면: PO노트처럼 채팅 대신 본문에 연다 ---------- */

const PAGE = { id: null, rendered: null };
const PAGES = {
  research: { title: "연구 라이브러리", button: "#btn-research", render: (panel) => renderResearch(panel) },
  automation: { title: "에이전트 자동화", button: "#btn-auto", render: (panel) => renderAutomation(panel) },
  plugins: { title: "플러그인", button: "#btn-plugins", render: (panel) => renderPlugins(panel) },
};

function pageOpen(id) {
  if (!PAGES[id]) return;
  if (window.codeLeave) codeLeave();  // 코드도 하나의 화면이라 다른 화면을 열면 닫는다(탭은 그대로)
  if (window.poLeave) poLeave();
  if (PAGE.id && PAGE.id !== id) $(PAGES[PAGE.id].button)?.classList.remove("active");
  PAGE.id = id;
  for (const sel of ["#scroll", "#composer-wrap", "#thread-model-picker", "#agent-label", "#po-view"]) $(sel).hidden = true;
  $("#tool-view").hidden = false;
  $("#chat-title").textContent = PAGES[id].title;
  $(PAGES[id].button)?.classList.add("active");
  document.querySelectorAll(".thread.active").forEach((t) => t.classList.remove("active"));
  // 1.19: Lab·라이브러리·자동화·플러그인을 열어도 사이드바를 접지 않는다(다른 기능으로 바로 옮겨 갈 수 있게).
  // 휴대폰처럼 좁은 화면에서는 사이드바가 화면을 덮는 서랍이라 그대로 닫는다.
  if (isNarrow()) setCollapsed(true);
  if (window.renderBrowserBar) renderBrowserBar();
  renderPage();
}

function pageLeave() {
  if (!PAGE.id) return;
  $(PAGES[PAGE.id].button)?.classList.remove("active");
  PAGE.id = null;
  PAGE.rendered = null;
  $("#tool-view").hidden = true;
  $("#scroll").hidden = false;
  $("#composer-wrap").hidden = false;
  $("#agent-label").hidden = false;
  if (S.thread) $("#chat-title").textContent = S.thread.title;
  renderThreadModel();
  if (window.renderBrowserBar) renderBrowserBar();
}

function renderPage() {
  const view = $("#tool-view");
  if (!PAGE.id || !view) return;
  const id = PAGE.id;
  let panel = view.firstChild;
  if (PAGE.rendered !== id || !panel) {
    panel = h("div", { class: "po-wrap hub-panel tool-page" }, h("small", { class: "muted" }, "불러오는 중..."));
    view.replaceChildren(panel);
    view.scrollTop = 0;
  }
  PAGE.rendered = id;
  Promise.resolve(PAGES[id].render(panel)).catch((e) => {
    fill(panel, h("p", { class: "mcp-error" }, `불러오지 못했습니다: ${e.message || e}`));
  });
}

function pageIntro(title, text, ...actions) {
  actions = actions.filter(Boolean);
  return h("div", { class: "po-intro" }, h("div", {}, h("h1", {}, title), h("p", {}, text)),
    actions.length ? h("div", { class: "row wrap" }, actions) : null);
}

// 기능이 꺼져 있을 때: 무엇을 하는 기능인지와 켜기 버튼
function pageStart(title, text, label, enable) {
  return h("div", { class: "po-card tool-start" }, h("b", {}, title), h("p", {}, text),
    h("button", { class: "btn primary", onclick: async () => { if (await enable()) renderHub(); } }, label));
}

// tabs: [[키, 이름, 옆에 작게 붙일 값]]
function pageTabs(state, tabs) {
  if (!tabs.some(([key]) => key === state.tab)) state.tab = tabs[0][0];
  return h("div", { class: "po-tabs", role: "tablist" }, tabs.map(([key, label, extra]) =>
    h("button", { class: "po-tab" + (state.tab === key ? " active" : ""), role: "tab", "aria-selected": String(state.tab === key),
      onclick: () => { state.tab = key; renderHub(); } }, label, extra != null ? h("small", {}, ` ${extra}`) : null)));
}

function pageFooter(...extra) {
  return h("div", { class: "row wrap tool-footer" },
    h("span", { style: "flex:1" }, "커넥터(GitHub·Google·Zotero)·MCP 서버·메모리·사용량은 '연결·도구'에서 관리합니다."),
    h("button", { class: "link-btn", onclick: () => showHub() }, "연결·도구 열기"), ...extra);
}

// 이 탭이 다시 그려질 때 펼쳐 둔 항목을 유지한다
function hubDetails(key, summary, ...children) {
  const d = h("details", { class: "hub-details", open: HUB.open.has(key) }, h("summary", {}, summary), ...children);
  d.addEventListener("toggle", () => (d.open ? HUB.open.add(key) : HUB.open.delete(key)));
  return d;
}

function checkbox(checked, onchange, title) {
  const box = h("input", { type: "checkbox", class: "inline-check", title });
  box.checked = !!checked;
  box.addEventListener("change", () => onchange(box.checked, box));
  return box;
}

async function hubCall(promise, okText) {
  const res = await promise;
  if (res && res.ok === false) {
    toast(res.error || "실패했습니다");
    return null;
  }
  if (okText) toast(okText);
  if (res && res.message) toast(res.message);
  return res;
}

function featureToggle(features, name, note) {
  const f = (features || {})[name];
  if (!f) return null;
  return h("label", { class: "feature-toggle" },
    checkbox(f.enabled, async (on) => {
      await hubCall(api().set_feature(name, on), on ? `${f.label}을(를) 켰습니다` : `${f.label}을(를) 껐습니다`);
      renderHub();
    }),
    h("span", {}, h("b", {}, f.label), note ? h("small", {}, note) : null));
}

/* ---------- 커넥터 탭 ---------- */

function stateBadge(c) {
  const [label, cls] = CONN_STATE[c.state] || [c.state, ""];
  return h("span", { class: "badge " + cls }, label);
}

function secretRow(c, f) {
  const input = h("input", { type: "password", autocomplete: "off",
    placeholder: f.has ? `저장됨 ${f.masked}` : (f.placeholder || "") });
  return h("div", { class: "field" }, h("label", {}, f.label),
    h("div", { class: "row" }, input,
      h("button", { class: "btn", onclick: async () => {
        if (!input.value.trim()) return toast("값을 입력하세요");
        if (await hubCall(api().set_connector_secret(c.id, f.name, input.value.trim()), "저장했습니다")) renderHub();
      } }, "저장")),
    f.help ? h("small", {}, f.help) : null);
}

function optionRow(c, f) {
  if (f.name === "readonly") {
    return h("label", { class: "feature-toggle" },
      checkbox(String(f.value) === "true", async (on) => {
        if (await hubCall(api().set_connector_option(c.id, "readonly", on ? "true" : ""),
          on ? "읽기 전용으로 바꿨습니다. 다시 로그인하면 읽기 권한만 요청합니다." : "쓰기 권한을 쓰려면 다시 로그인하세요.")) renderHub();
      }),
      h("span", {}, f.label));
  }
  const input = h("input", { type: "text", value: f.value || "", placeholder: f.placeholder || "" });
  return h("div", { class: "field" }, h("label", {}, f.label),
    h("div", { class: "row" }, input, h("button", { class: "btn", onclick: async () => {
      if (await hubCall(api().set_connector_option(c.id, f.name, input.value.trim()), "저장했습니다")) renderHub();
    } }, "저장")), f.help ? h("small", {}, f.help) : null);
}

function toolPolicyTable(c) {
  const rows = c.tools.map((t) => {
    const sel = h("select", { class: "policy-select", title: "이 도구의 승인 정책" },
      h("option", { value: "" }, "기본"),
      h("option", { value: "allow", disabled: ALWAYS_ASK.has(t.kind) }, "묻지 않고 허용"),
      h("option", { value: "ask" }, "항상 묻기"),
      h("option", { value: "deny" }, "차단(모델에게 숨김)"));
    sel.value = t.policy || "";
    sel.addEventListener("change", async () => {
      if (await hubCall(api().set_connector_policy(c.id, t.name, sel.value))) toast("정책을 바꿨습니다");
    });
    return h("tr", {}, h("td", { class: "mono" }, t.name),
      h("td", {}, h("span", { class: `badge kind-${t.kind}` }, KIND_LABEL[t.kind] || t.kind)), h("td", {}, sel));
  });
  return h("div", {},
    h("small", { class: "muted" }, "기본: 읽기는 묻지 않고, 쓰기는 '에이전트 권한' 설정을 따르며, 전송·삭제·실행은 설정과 관계없이 매번 묻습니다."),
    h("table", { class: "help-table policy-table" }, rows));
}

async function showConnectorLog(c, box) {
  const rows = await api().connector_log(c.id, 30);
  if (!rows.length) return fill(box, h("small", { class: "muted" }, "아직 호출 기록이 없습니다."));
  fill(box, h("table", { class: "help-table log-table" }, rows.map((r) => h("tr", {},
    h("td", {}, new Date(r.ts * 1000).toLocaleString()),
    h("td", { class: "mono" }, r.tool),
    h("td", {}, r.ok ? "성공" : (r.approval === "denied" ? "거부됨" : r.approval === "blocked" ? "차단됨" : "실패")),
    h("td", {}, `${r.ms}ms`),
    h("td", { class: "muted" }, r.error || "")))),
  h("small", { class: "muted" }, "기록에는 인자 요약만 남고(비밀·긴 내용·메일 주소는 가림) 결과 내용은 남지 않습니다. 30일 보관."));
}

function connectorCard(c, data) {
  const toggle = checkbox(c.enabled, async (on, box) => {
    box.disabled = true;
    const res = await hubCall(api().set_connector_enabled(c.id, on), on ? `${c.name}을(를) 켰습니다` : `${c.name}을(를) 껐습니다`);
    if (res) renderHub();
    else box.disabled = false;
  }, c.enabled ? "끄기" : "켜기");
  if (c.state === "unavailable") toggle.disabled = true;
  const actions = h("div", { class: "row wrap" });
  const oauthReady = c.auth === "oauth" || (c.device_flow && (data.oauth_clients[c.provider] || {}).client_id);
  if (oauthReady) {
    actions.append(h("button", { class: "btn", onclick: async () => {
      if (await hubCall(api().connector_login(c.id))) toast("브라우저에서 로그인을 마치세요");
    } }, c.has_oauth_token ? "다시 로그인" : (c.auth === "oauth" ? "로그인" : "OAuth로 로그인")));
  }
  actions.append(
    h("button", { class: "btn", onclick: async () => {
      toast("확인하는 중...");
      const res = await hubCall(api().connector_verify(c.id));
      if (res) {
        const v = res.verified || {};
        toast(v.state === "connected" ? `연결됨${v.account ? ": " + v.account : ""}` : (v.detail || "확인하지 못했습니다"));
        renderHub();
      }
    } }, "연결 확인"),
    h("button", { class: "btn danger", onclick: async () => {
      if (!confirm(`${c.name} 연결을 해제할까요? 이 기기에 저장된 인증 정보를 지웁니다.`)) return;
      if (await hubCall(api().connector_logout(c.id))) renderHub();
    } }, "연결 해제"));
  const logBox = h("div", {});
  const detail = c.detail && c.state !== "disabled" ? h("p", { class: c.state === "error" ? "mcp-error" : "" }, c.detail) : null;
  const missing = (c.missing_scopes || []).length
    ? h("p", { class: "mcp-error" }, "허용받지 못한 권한: " + c.missing_scopes.map((s) => s.split("/").pop()).join(", ")) : null;
  return h("div", { class: "conn-card" },
    h("div", { class: "skill-item" }, toggle,
      h("div", { class: "s-main" },
        h("b", {}, c.name), stateBadge(c), c.desktop_only ? h("span", { class: "badge" }, "데스크톱 전용") : null,
        c.account ? h("span", { class: "badge" }, c.account) : null,
        h("p", {}, c.description), detail, missing)),
    hubDetails(`conn:${c.id}`, "연결 설정 · 권한 · 기록",
      c.setup ? h("div", { class: "conn-setup" }, renderMarkdown(c.setup)) : null,
      ...c.secrets.map((f) => secretRow(c, f)),
      c.device_flow ? oauthClientRow("github", data, "GitHub OAuth App의 Client ID (선택, Device Flow 사용 설정 필요)", false) : null,
      ...c.options.map((f) => optionRow(c, f)),
      c.scopes.length ? h("div", { class: "field" }, h("label", {}, c.auth === "oauth" ? "요청하는 권한(scope)" : "토큰에 필요한 권한"),
        h("ul", { class: "scope-list" }, c.scopes.map((s) => h("li", { class: "mono" }, s)))) : null,
      actions,
      h("div", { class: "field" }, h("label", {}, `도구 ${c.tools.length}개와 승인 정책`), toolPolicyTable(c)),
      h("div", { class: "field" }, h("label", {}, "최근 호출 기록"),
        h("button", { class: "btn", onclick: () => showConnectorLog(c, logBox) }, "불러오기"), logBox)));
}

function oauthClientRow(provider, data, label, withSecret = true) {
  const client = data.oauth_clients[provider] || {};
  const id = h("input", { type: "text", value: client.client_id || "", placeholder: "클라이언트 ID", autocomplete: "off" });
  const secret = withSecret ? h("input", { type: "password", autocomplete: "off",
    placeholder: client.has_secret ? "저장됨 — 바꾸려면 새로 입력" : "클라이언트 보안 비밀번호" }) : null;
  return h("div", { class: "field" }, h("label", {}, label),
    h("div", { class: "row wrap" }, id, secret,
      h("button", { class: "btn", onclick: async () => {
        if (await hubCall(api().set_oauth_client(provider, id.value.trim(), secret ? secret.value.trim() : null), "저장했습니다")) renderHub();
      } }, "저장"),
      client.client_id ? h("button", { class: "btn danger", onclick: async () => {
        if (await hubCall(api().set_oauth_client(provider, "", null, true), "지웠습니다")) renderHub();
      } }, "지우기") : null));
}

async function renderConnectors(panel) {
  const data = await api().get_connectors();
  HUB.android = !!data.android;
  const groups = {};
  for (const c of data.connectors) (groups[c.group] = groups[c.group] || []).push(c);
  const backend = data.secret_backend.startsWith("os:") ? "OS 보안 저장소(Windows 자격 증명 관리자·macOS 키체인)"
    : data.android ? "앱 전용 저장소(안드로이드 샌드박스)" : "앱 전용 파일(secrets.json, 이 사용자만 읽기 가능)";
  fill(panel, 
    h("p", { class: "hub-intro" }, "외부 서비스를 연결하면 에이전트 모드에서 그 서비스의 도구를 씁니다. 커넥터는 기본으로 꺼져 있고, ",
      "켠 커넥터의 도구만 모델에게 보입니다. 쓰기는 승인을 받고, 메일 전송·리뷰 제출 같은 작업은 매번 묻습니다."),
    featureToggle(data.features, "connectors", "끄면 모든 커넥터를 한 번에 멈춥니다(설정은 남습니다)."),
    h("small", { class: "muted block" }, `인증 정보 저장 위치: ${backend}. 토큰은 설정 파일·동기화·로그에 들어가지 않습니다.`),
    ...Object.entries(groups).map(([group, items]) => h("section", { class: "hub-group" },
      h("h3", {}, group),
      group === "Google Workspace" ? hubDetails("google-client", "Google OAuth 클라이언트 (처음 한 번)",
        h("div", { class: "conn-setup" }, renderMarkdown(items[0].setup)),
        oauthClientRow("google", data, "데스크톱 앱 OAuth 클라이언트")) : null,
      ...items.map((c) => connectorCard(c, data)))));
}

/* ---------- MCP 서버 탭 (1.9의 MCP 창) ---------- */

async function renderMcpPanel(panel, st) {
  st = st || await api().get_mcp();
  const STATE = { connected: "연결됨", error: "연결 실패", idle: "대기" };
  const list = h("div", {});
  for (const sv of st.servers) {
    const toggle = checkbox(sv.enabled, async (on) => renderMcpPanel(panel, await api().set_mcp_enabled(sv.name, on)),
      sv.enabled ? "끄기" : "켜기");
    if (sv.connector) toggle.disabled = true;  // 커넥터 서버는 커넥터 탭에서 켜고 끈다
    const detail = sv.state === "connected" ? "도구: " + sv.tools.join(", ")
      : sv.error ? sv.error : (sv.command || sv.description);
    const strict = !sv.builtin ? h("label", { class: "inline-label" },
      checkbox(sv.policy === "ask_all", async (on) => renderMcpPanel(panel, await api().set_server_policy(sv.name, on ? "ask_all" : ""))),
      "읽기 도구도 항상 묻기") : null;
    list.append(h("div", { class: "skill-item" }, toggle,
      h("div", { class: "s-main" },
        h("b", {}, sv.name),
        h("span", { class: "badge" }, sv.connector ? "커넥터" : sv.builtin ? "내장" : sv.preset ? "추천" : "외부"),
        sv.enabled ? h("span", { class: "badge mcp-" + sv.state }, STATE[sv.state] || sv.state) : null,
        h("p", {}, sv.description || ""),
        detail && detail !== sv.description ? h("p", { class: sv.error ? "mcp-error" : "" }, detail) : null,
        strict)));
  }
  fill(panel, 
    h("p", { class: "hub-intro" },
      "MCP 서버는 에이전트가 쓸 수 있는 도구를 더해 줍니다. 내장 서버로 Word·PowerPoint·Excel 문서를 만들고 고치고, ",
      "논문을 찾아 읽고(paper), Notion 페이지를 다루고(notion, 설정에 토큰 필요), ",
      "웹페이지를 읽고 검색할 수 있습니다(firecrawl, 설정에 키 필요). 파일은 작업 폴더 안의 것만 다룹니다. ",
      "추천 서버(playwright: 브라우저 자동화, context7: 라이브러리 문서 검색)는 PC에 Node.js가 있으면 켜서 씁니다. ",
      "다른 MCP 서버는 설정 파일(mcp.json)에 Claude Desktop과 같은 형식으로 추가합니다. 커넥터의 서버는 커넥터 탭에서 켭니다."),
    list,
    st.config_error ? h("p", { class: "mcp-error" }, st.config_error) : null,
    h("div", { class: "row wrap", style: "margin-top:10px" },
      h("button", { class: "btn", onclick: () => api().open_mcp_config() }, "설정 파일 열기"),
      h("button", { class: "btn", onclick: async () => {
        if (!S.workspace.path) return toast("먼저 작업 폴더를 선택하세요");
        toast("MCP 서버에 연결하는 중...");
        renderMcpPanel(panel, await api().connect_mcp());
      } }, "지금 연결")),
    h("small", { class: "muted block" },
      "서버는 에이전트 모드에서 처음 필요할 때 연결됩니다. 작업 폴더의 파일을 고치는 도구는 파일 수정처럼, ",
      "외부 서버의 도구와 Notion에 쓰기·브라우저 조작처럼 바깥에 영향을 주는 도구는 명령 실행처럼 승인을 받습니다. ",
      "외부 서버의 도구 결과는 '외부 데이터'로 표시되어 모델이 그 안의 지시를 따르지 않도록 합니다."));
}

HUB_TABS.push({ id: "connectors", label: "커넥터", render: renderConnectors },
  { id: "mcp", label: "MCP 서버", render: (panel) => renderMcpPanel(panel) });

/* ---------- 연구 라이브러리 화면 (Phase 2, 1.11부터 PO노트처럼 본문에 연다) ---------- */

const RESEARCH = { query: "", tag: "", progress: null, tab: "papers" };

function paperItem(p) {
  const authors = (p.authors || []).slice(0, 4).join(", ") + ((p.authors || []).length > 4 ? ` 외 ${p.authors.length - 4}명` : "");
  const ids = [p.doi ? `DOI ${p.doi}` : "", p.arxiv ? `arXiv ${p.arxiv}` : "", p.pdf ? `PDF ${p.pdf}` : ""].filter(Boolean).join(" · ");
  const edit = (field, label, join) => async () => {
    const current = Array.isArray(p[field]) ? p[field].join(", ") : (p[field] || "");
    const value = prompt(label, current);
    if (value == null) return;
    const res = await hubCall(api().research_update(p.id, { [field]: join ? value.split(",").map((t) => t.trim()).filter(Boolean) : value }));
    if (res) renderHub();
  };
  return h("div", { class: "skill-item paper-item" },
    h("div", { class: "s-main" },
      h("b", { class: "paper-title" }, p.title || "(제목 없음)"), h("span", { class: "badge" }, p.year || "연도 미상"),
      p.citations != null ? h("span", { class: "badge" }, `인용 ${p.citations}`) : null,
      h("p", {}, [authors, p.venue].filter(Boolean).join(" · ")),
      ids ? h("p", { class: "mono small" }, ids) : null,
      (p.tags || []).length ? h("p", {}, (p.tags || []).map((t) => h("span", { class: "badge tag", onclick: () => { RESEARCH.tag = t; renderHub(); } }, `#${t}`))) : null,
      p.notes ? h("p", { class: "muted" }, `메모: ${p.notes}`) : null,
      h("div", { class: "row wrap paper-actions" },
        h("button", { class: "link-btn", onclick: edit("tags", "태그(쉼표로 구분)", true) }, "태그"),
        h("button", { class: "link-btn", onclick: edit("notes", "메모") }, "메모"),
        h("button", { class: "link-btn", onclick: async () => {
          const res = await hubCall(api().research_bibtex([p.id]));
          if (res) showBibtex(res);
        } }, "BibTeX"),
        h("button", { class: "link-btn danger", onclick: async () => {
          if (!confirm(`'${p.title}'을(를) 라이브러리에서 지울까요?`)) return;
          if (await hubCall(api().research_remove(p.id), "지웠습니다")) renderHub();
        } }, "지우기"))));
}

function showBibtex(res) {
  const pre = h("pre", { class: "diff bib" }, h("div", {}, res.bibtex));
  modal({
    title: `BibTeX (${res.count}편)`, body: pre, wide: true,
    buttons: [{ label: "복사", action: () => copyText(res.bibtex) },
      { label: "파일로 저장", action: async () => { const r = await hubCall(api().research_bibtex(null, RESEARCH.tag || null, true)); if (r) toast(`저장했습니다: ${r.path}`); } },
      { label: "닫기", class: "primary" }],
  });
}

async function renderResearch(panel) {
  const st = await api().research_state(RESEARCH.query, RESEARCH.tag);
  const docs = st.index.documents || [];
  const v = st.vector || {};
  const bibtexAll = h("button", { class: "btn", onclick: async () => {
    const r = await hubCall(api().research_bibtex(null, RESEARCH.tag || null));
    if (r) showBibtex(r);
  } }, RESEARCH.tag ? `#${RESEARCH.tag} BibTeX` : "BibTeX 내보내기");
  const zotero = st.zotero !== "disabled" ? h("button", { class: "btn", onclick: async () => {
    toast("Zotero에서 가져오는 중...");
    const r = await hubCall(api().zotero_import_now(false));
    if (r) { toast(r.result); renderHub(); }
  } }, "Zotero에서 가져오기") : null;
  const intro = pageIntro("연구 라이브러리",
    "논문을 모아 태그로 정리하고 BibTeX으로 내보내며, 작업 폴더의 PDF·문서를 인덱싱해 쪽·섹션이 붙은 원문으로 찾습니다. 모든 데이터는 이 기기에만 저장됩니다.",
    st.feature ? zotero : null, st.feature ? bibtexAll : null);
  if (!st.feature) {
    return fill(panel, intro, pageStart("연구 워크스페이스가 꺼져 있습니다",
      "켜면 논문 라이브러리와 문서 인덱스를 쓸 수 있고, 에이전트에게 연구 도구(논문 더하기·추천·인용 관계·문서 검색)를 줄 수 있습니다.",
      "연구 워크스페이스 켜기", () => hubCall(api().set_feature("research", true), "연구 워크스페이스를 켰습니다")));
  }
  const pane = { papers: researchPapers, docs: researchDocs, vector: researchVector }[RESEARCH.tab] || researchPapers;
  fill(panel, intro,
    !st.enabled ? h("div", { class: "po-card po-warn row wrap" },
      h("span", { style: "flex:1" }, "에이전트는 아직 연구 도구를 쓰지 않습니다. 켜면 대화 중에 논문을 찾아 더하고 인덱스의 원문을 인용합니다."),
      h("button", { class: "btn", onclick: async () => { if (await hubCall(api().set_connector_enabled("research", true), "켰습니다")) renderHub(); } }, "에이전트 도구 켜기")) : null,
    pageTabs(RESEARCH, [["papers", "논문", st.total], ["docs", "문서 검색", docs.length || null],
      ["vector", "벡터 검색", v.enabled ? "켜짐" : null]]),
    h("div", { class: "po-pane" }, pane(st)),
    pageFooter(h("button", { class: "link-btn", onclick: async () => {
      if (!confirm("연구 워크스페이스를 끌까요? 모은 논문과 인덱스는 지우지 않습니다.")) return;
      await hubCall(api().set_feature("research", false), "연구 워크스페이스를 껐습니다");
      renderHub();
    } }, "연구 워크스페이스 끄기")));
}

function researchPapers(st) {
  const add = h("input", { type: "text", placeholder: "arXiv 번호(1706.03762)·DOI·논문 주소" });
  const addTags = h("input", { type: "text", placeholder: "태그(선택, 쉼표로 구분)" });
  const addBtn = h("button", { class: "btn primary", onclick: async () => {
    if (!add.value.trim()) return toast("arXiv 번호·DOI·주소를 입력하세요");
    addBtn.disabled = true;
    try {
      const tags = addTags.value.split(",").map((t) => t.trim()).filter(Boolean);
      if (await hubCall(api().research_add(add.value.trim(), tags), "라이브러리에 더했습니다")) renderHub();
    } finally { addBtn.disabled = false; }
  } }, "더하기");
  add.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) addBtn.click(); });
  const search = h("input", { type: "search", placeholder: "제목·저자·초록·메모 검색 (Enter)", value: RESEARCH.query });
  search.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) { RESEARCH.query = search.value.trim(); renderHub(); } });
  const tags = Object.entries(st.tags || {});
  return h("div", { class: "tool-stack" },
    h("div", { class: "po-card" }, h("div", { class: "po-label" }, "논문 더하기", h("small", {}, "제목·저자·초록·인용 수를 자동으로 채웁니다")),
      h("div", { class: "row wrap" }, add, addTags, addBtn)),
    h("div", { class: "row wrap" }, search,
      RESEARCH.query ? h("button", { class: "btn", onclick: () => { RESEARCH.query = ""; renderHub(); } }, "검색 지우기") : null),
    tags.length ? h("p", { class: "tag-row" }, h("span", { class: "badge tag" + (RESEARCH.tag ? "" : " active"), onclick: () => { RESEARCH.tag = ""; renderHub(); } }, "전체"),
      tags.map(([t, n]) => h("span", { class: "badge tag" + (RESEARCH.tag === t ? " active" : ""), onclick: () => { RESEARCH.tag = t; renderHub(); } }, `#${t} ${n}`))) : null,
    st.papers.length ? h("div", { class: "po-list" }, st.papers.map(paperItem))
      : h("p", { class: "po-empty" }, st.total ? "맞는 논문이 없습니다." : "아직 논문이 없습니다. 위에서 arXiv 번호나 DOI로 더해 보세요."));
}

function researchDocs(st) {
  const docs = st.index.documents || [];
  const v = st.vector || {};
  const progress = h("small", { class: "muted block" }, RESEARCH.progress || (st.indexing ? "인덱싱 중..." : ""));
  RESEARCH.progressNode = progress;
  const ragQuery = h("input", { type: "search", placeholder: "인덱스에서 찾기(출처가 붙은 원문 조각)" });
  const ragOut = h("div", {});
  ragQuery.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter" || e.isComposing || !ragQuery.value.trim()) return;
    const res = await hubCall(api().research_search(ragQuery.value.trim()));
    if (!res) return;
    fill(ragOut, res.results.length ? res.results.map((r) => h("div", { class: "rag-hit" },
      h("small", { class: "mono" }, r.cite), h("p", {}, r.text.length > 400 ? r.text.slice(0, 400) + "…" : r.text)))
      : [h("small", { class: "muted" }, "맞는 내용이 없습니다.")]);
  });
  return h("div", { class: "tool-stack" },
    h("div", { class: "po-card" },
      h("div", { class: "po-label" }, "작업 폴더 인덱싱",
        h("small", {}, `문서 ${docs.length}개 · 청크 ${st.index.chunks}개 · 검색 방식 ${st.index.fts}${v.enabled ? " + 벡터" : ""}`)),
      h("div", { class: "row wrap" },
        h("small", { class: "muted", style: "flex:1;word-break:break-all" }, st.workspace ? `작업 폴더: ${st.workspace}` : "왼쪽 아래 '작업 폴더'를 고르면 그 폴더의 PDF·문서를 인덱싱합니다."),
        h("button", { class: "btn", disabled: !st.workspace || st.indexing, onclick: async () => {
          RESEARCH.progress = "인덱싱을 시작합니다...";
          if (await hubCall(api().research_index())) renderHub();
        } }, "작업 폴더 인덱싱")),
      progress,
      st.index.error ? h("p", { class: "mcp-error" }, st.index.error) : null),
    h("div", { class: "po-card" }, h("div", { class: "po-label" }, "원문 찾기", h("small", {}, "찾은 조각마다 문서·쪽·섹션 출처가 붙습니다")),
      h("div", { class: "row" }, ragQuery), ragOut),
    docs.length ? hubDetails("rag-docs", `인덱싱한 문서 ${docs.length}개`, h("div", { class: "table-scroll" }, h("table", { class: "help-table log-table" }, docs.map((d) => h("tr", {},
      h("td", { class: "mono" }, d.path.split(/[\\/]/).pop()), h("td", {}, d.collection === "library" ? "라이브러리" : "작업 폴더"),
      h("td", {}, `${d.pages || "-"}쪽 · 청크 ${d.chunks}`),
      h("td", {}, h("button", { class: "link-btn danger", onclick: async () => { if (await hubCall(api().research_remove_document(d.doc_id))) renderHub(); } }, "빼기"))))))) : null);
}

function researchVector(st) {
  const v = st.vector || {};
  const vEnabled = checkbox(v.enabled, () => {});
  const vUrl = h("input", { type: "url", value: v.qdrant_url || "", placeholder: "http://127.0.0.1:6333" });
  const vColl = h("input", { type: "text", value: v.collection || "poschat" });
  const vEmbUrl = h("input", { type: "url", value: v.embedding_url || "", placeholder: "https://.../v1/embeddings" });
  const vModel = h("input", { type: "text", value: v.embedding_model || "", placeholder: "임베딩 모델 ID" });
  const vQKey = h("input", { type: "password", placeholder: v.has_qdrant_key ? "저장됨" : "Qdrant API 키(선택)" });
  const vEKey = h("input", { type: "password", placeholder: v.has_embedding_key ? "저장됨" : "임베딩 API 키" });
  return h("div", { class: "po-card" },
    h("div", { class: "po-label" }, "벡터 검색 (선택)", h("small", {}, "Qdrant + OpenAI 호환 임베딩 API")),
    h("small", { class: "muted block" }, "켜면 인덱싱할 때 문서 조각을 임베딩 API로 보내 벡터를 만들고 Qdrant에 저장해, 키워드 검색과 섞어(RRF) 찾습니다. ",
      "문서 내용이 그 서버로 전송되므로 직접 운영하거나 신뢰하는 서버만 쓰세요. 끄면 키워드 검색만 씁니다."),
    h("label", { class: "feature-toggle" }, vEnabled, h("span", {}, "벡터 검색 켜기")),
    h("div", { class: "field" }, h("label", {}, "Qdrant 주소 · 컬렉션"), h("div", { class: "row wrap" }, vUrl, vColl)),
    h("div", { class: "field" }, h("label", {}, "임베딩 API(OpenAI 호환 /embeddings) 주소 · 모델"), h("div", { class: "row wrap" }, vEmbUrl, vModel)),
    h("div", { class: "field" }, h("label", {}, "키"), h("div", { class: "row wrap" }, vQKey, vEKey)),
    h("div", { class: "row po-actions" }, h("button", { class: "btn primary", onclick: async () => {
      const r = await hubCall(api().set_vector_config({ enabled: vEnabled.checked, qdrant_url: vUrl.value.trim(), collection: vColl.value.trim(),
        embedding_url: vEmbUrl.value.trim(), embedding_model: vModel.value.trim(), qdrant_key: vQKey.value.trim(), embedding_key: vEKey.value.trim() }), "저장했습니다");
      if (r) renderHub();
    } }, "저장")));
}

/* ---------- 메모리·동기화 탭 (Phase 3) ---------- */

const MEM = { layer: "", query: "", syncNote: "" };
const LAYER_LABEL = { profile: "프로필", global: "memory.md", conversation: "대화", project: "프로젝트", research: "연구" };
const MEM_KINDS = ["note", "decision", "status", "todo", "issue", "experiment", "result", "hypothesis", "data", "preference", "summary"];
const SYNC_LABEL = { memory: "메모리(memory.md)", profile: "내 정보(USER.md)", threads: "대화 기록", project: "프로젝트 메모리·인계",
  research: "논문 라이브러리", settings: "설정 일부(대화·PO노트)", po_notes: "PO노트(제목·노트·메모·전사)" };
const HANDOFF_STATUS = { open: ["열림", "st-warn"], accepted: ["받음", "st-ok"], completed: ["완료", ""], cancelled: ["취소", ""] };

function fmtTime(ts) {
  return ts ? new Date(ts * 1000).toLocaleString() : "-";
}

function memoryItem(e) {
  return h("div", { class: "skill-item paper-item" },
    h("div", { class: "s-main" },
      h("span", { class: "badge" }, LAYER_LABEL[e.layer] || e.layer), h("span", { class: "badge" }, e.kind || "note"),
      e.project ? h("span", { class: "badge" }, e.project) : null,
      h("p", { class: "mem-text" }, (e.title ? e.title + ": " : "") + e.text),
      h("p", { class: "muted small" }, `${e.source || ""} · ${fmtTime(e.updated)}`),
      e.key && !String(e.key).startsWith("entry:") ? null : h("div", { class: "row wrap paper-actions" },
        h("button", { class: "link-btn danger", onclick: async () => {
          if (!confirm("이 기억을 지울까요?")) return;
          if (await hubCall(api().memory_delete_entry(e.id), "지웠습니다")) renderHub();
        } }, "지우기"))));
}

function handoffItem(r) {
  const [label, cls] = HANDOFF_STATUS[r.status] || [r.status, ""];
  const lists = [["변경 파일", r.files_changed], ["커밋", r.commits], ["실행한 도구", r.tools_run], ["다음 단계", r.next_steps],
    ["필요한 승인", r.approvals_needed], ["남은 질문", r.open_questions]].filter(([, v]) => (v || []).length);
  return h("div", { class: "conn-card" },
    h("div", { class: "skill-item paper-item" }, h("div", { class: "s-main" },
      h("b", { class: "paper-title" }, r.goal), h("span", { class: "badge " + cls }, label),
      h("span", { class: "badge" }, r.from_agent || "?"), r.accepted_by ? h("span", { class: "badge" }, "→ " + r.accepted_by) : null,
      h("p", { class: "muted small" }, `${r.task_id} · ${r.project || "-"} · ${fmtTime(r.updated)}`),
      r.summary ? h("p", { class: "mem-text" }, r.summary.length > 300 ? r.summary.slice(0, 300) + "…" : r.summary) : null,
      ...lists.map(([k, v]) => h("p", { class: "small" }, `${k}: ${v.slice(0, 8).join("; ")}${v.length > 8 ? ` 외 ${v.length - 8}개` : ""}`)),
      ...(r.tests || []).map((t) => h("p", { class: "small" }, `${t.passed === true ? "✓" : t.passed === false ? "✗" : "·"} ${t.command} ${t.result || ""}`)),
      r.status === "open" || r.status === "accepted" ? h("div", { class: "row wrap paper-actions" },
        h("button", { class: "link-btn", onclick: async () => { if (await hubCall(api().handoff_set_status(r.task_id, "completed"))) renderHub(); } }, "완료로 표시"),
        h("button", { class: "link-btn danger", onclick: async () => { if (await hubCall(api().handoff_set_status(r.task_id, "cancelled"))) renderHub(); } }, "취소")) : null)));
}

function syncPanel(st) {
  if (!st.available) return h("p", { class: "mcp-error" }, st.reason);
  const include = {};
  const includeBoxes = Object.entries(SYNC_LABEL).map(([k, label]) => {
    const box = checkbox(st.include[k] !== false, async (on) => {
      include[k] = on;
      if (st.enabled) { await api().sync_set_include({ ...st.include, ...include }); toast("동기화 대상을 바꿨습니다"); }
    });
    include[k] = st.include[k] !== false;
    return h("label", { class: "inline-label sync-include" }, box, label);
  });
  if (st.enabled) {
    const r = st.last_report || {};
    return h("div", {},
      h("div", { class: "stat-grid" },
        h("div", { class: "stat" }, h("b", {}, st.backend === "gdrive" ? "Google Drive" : "폴더"), h("span", {}, st.backend === "gdrive" ? "앱 전용 숨김 폴더" : st.folder)),
        h("div", { class: "stat" }, h("b", {}, st.running ? "동기화 중…" : fmtTime(st.last_sync)), h("span", {}, "마지막 동기화")),
        h("div", { class: "stat" }, h("b", {}, `↑${r.uploaded || 0} ↓${r.downloaded || 0}`), h("span", {}, `병합 ${r.merged || 0} · 삭제 ${r.deleted || 0}`)),
        h("div", { class: "stat" }, h("b", {}, String((r.devices || []).length || 1)), h("span", {}, "기기"))),
      st.last_error ? h("p", { class: "mcp-error" }, `마지막 오류: ${st.last_error}`) : null,
      MEM.syncNote ? h("small", { class: "muted block" }, MEM.syncNote) : null,
      (r.conflicts || []).length ? h("p", { class: "small" }, `충돌로 따로 보관한 파일 ${r.conflicts.length}개: `, r.conflicts.map((c) => c.split(/[\\/]/).pop()).join(", ")) : null,
      (r.devices || []).length ? h("p", { class: "small muted" }, "기기: " + r.devices.map((d) => `${d.name || d.id} (${d.platform || "?"}, ${fmtTime(d.last_seen)})`).join(" · ")) : null,
      h("div", { class: "field" }, h("label", {}, "동기화할 것"), h("div", { class: "row wrap" }, includeBoxes)),
      h("div", { class: "row wrap" },
        h("button", { class: "btn primary", disabled: st.running, onclick: async () => { if (await hubCall(api().sync_now())) { MEM.syncNote = "동기화 중…"; renderHub(); } } }, "지금 동기화"),
        h("button", { class: "btn", onclick: async () => {
          if (!confirm("이 기기의 동기화를 끌까요? 이 기기의 키만 지우고 원격·로컬 데이터는 남깁니다.")) return;
          if (await hubCall(api().sync_disconnect(), "이 기기의 동기화를 껐습니다")) renderHub();
        } }, "이 기기 연결 해제"),
        h("button", { class: "btn danger", onclick: async () => {
          if (!confirm("원격 동기화 데이터를 모두 지울까요? 다른 기기도 동기화가 멈춥니다. 각 기기의 로컬 데이터는 남습니다.")) return;
          if (!confirm("정말 지울까요? 되돌릴 수 없습니다.")) return;
          if (await hubCall(api().sync_wipe_remote(), "원격 동기화 데이터를 지웠습니다")) renderHub();
        } }, "원격 데이터 삭제")));
  }
  const backend = h("select", {}, h("option", { value: "folder" }, "동기화 폴더(OneDrive·Dropbox·Google Drive 데스크톱 등)"),
    h("option", { value: "gdrive" }, `Google Drive 앱 전용 폴더${st.gsync === "connected" ? "" : " — 커넥터 탭에서 먼저 로그인"}`));
  backend.value = HUB.android ? "gdrive" : (st.backend || "folder");
  const folder = h("input", { type: "text", value: st.folder || "", placeholder: "동기화 폴더 경로" });
  const pick = h("button", { class: "btn", onclick: async () => { const r = await api().sync_choose_folder(); if (r.ok) folder.value = r.folder; } }, "고르기");
  const folderRow = h("div", { class: "field" }, h("label", {}, "폴더"), h("div", { class: "row wrap" }, folder, pick));
  const syncBackend = () => { folderRow.hidden = backend.value !== "folder"; };
  backend.addEventListener("change", syncBackend);
  syncBackend();
  const pass1 = h("input", { type: "password", placeholder: "동기화 암호(8글자 이상)", autocomplete: "new-password" });
  const pass2 = h("input", { type: "password", placeholder: "한 번 더", autocomplete: "new-password" });
  const device = h("input", { type: "text", value: st.device_name || "", placeholder: "이 기기 이름(예: 연구실 PC)" });
  return h("div", {},
    h("small", { class: "muted block" }, "동기화는 직접 켤 때만 동작합니다. 데이터는 이 기기에서 암호화(AES-256-GCM)한 뒤 올리고, 암호는 어디에도 저장하지 않습니다(이 기기의 보안 저장소에는 암호로 만든 키만 둡니다). ",
      "암호를 잊으면 동기화 데이터를 되살릴 수 없습니다. API 키·로그인 토큰·작업 폴더 경로·첨부 원본은 동기화하지 않습니다."),
    h("div", { class: "field" }, h("label", {}, "저장소"), backend), folderRow,
    h("div", { class: "field" }, h("label", {}, "동기화 암호 (다른 기기에서도 같은 암호)"), h("div", { class: "row wrap" }, pass1, pass2)),
    h("div", { class: "field" }, h("label", {}, "이 기기 이름"), device),
    h("div", { class: "field" }, h("label", {}, "동기화할 것"), h("div", { class: "row wrap" }, includeBoxes)),
    h("button", { class: "btn primary", onclick: async (ev) => {
      if (pass1.value !== pass2.value) return toast("두 암호가 다릅니다");
      ev.target.disabled = true;
      try {
        const res = await hubCall(api().sync_setup({ backend: backend.value, folder: folder.value.trim(), passphrase: pass1.value,
          device_name: device.value.trim(), include }), "동기화를 켰습니다. 곧 첫 동기화를 합니다.");
        if (res) renderHub();
      } finally { ev.target.disabled = false; }
    } }, "동기화 켜기"));
}

async function renderMemory(panel) {
  const st = await api().memory_state(MEM.layer, MEM.query);
  HUB.android = !!st.android;
  const layers = st.stats.layers || {};
  const search = h("input", { type: "search", placeholder: "기억 검색(프로젝트·연구·대화 요약·memory.md·USER.md·예전 대화)", value: MEM.query });
  search.addEventListener("keydown", (e) => { if (e.key === "Enter") { MEM.query = search.value.trim(); renderHub(); } });
  const layerSel = h("select", { class: "policy-select" }, h("option", { value: "" }, "모든 계층"),
    ...Object.entries(LAYER_LABEL).map(([k, v]) => h("option", { value: k }, v)));
  layerSel.value = MEM.layer;
  layerSel.addEventListener("change", () => { MEM.layer = layerSel.value; renderHub(); });
  const text = h("textarea", { rows: 2, placeholder: "남길 기억(예: API 응답은 JSON으로 통일하기로 함)" });
  const addLayer = h("select", { class: "policy-select" }, ["project", "research", "conversation", "profile"].map((k) => h("option", { value: k }, LAYER_LABEL[k])));
  const addKind = h("select", { class: "policy-select" }, MEM_KINDS.map((k) => h("option", { value: k }, k)));
  const handoffs = st.handoffs || [];
  fill(panel,
    h("p", { class: "hub-intro" }, "memory.md·내 정보(USER.md)·대화 기록은 그대로 쓰고, 그 위에 프로젝트(설계 결정·진행 상태·TODO)·연구(실험·가설) 계층과 에이전트 인계를 더합니다. ",
      "켜면 에이전트가 작업 폴더의 프로젝트 기억을 참고하고, 파일을 고친 실행 뒤에는 인계(변경 파일·테스트·다음 단계)를 남깁니다."),
    featureToggle({ memory_hub: { label: "통합 메모리", enabled: st.feature } }, "memory_hub"),
    st.feature && !st.enabled ? h("div", { class: "row wrap" }, h("small", { class: "muted" }, "에이전트 도구(memory 서버)가 꺼져 있습니다."),
      h("button", { class: "btn", onclick: async () => { if (await hubCall(api().set_connector_enabled("memory", true), "켰습니다")) renderHub(); } }, "에이전트 도구 켜기")) : null,
    st.error ? h("p", { class: "mcp-error" }, st.error) : null,
    h("div", { class: "stat-grid" },
      ...["project", "research", "conversation", "profile"].map((k) => h("div", { class: "stat" }, h("b", {}, String(layers[k] || 0)), h("span", {}, `${LAYER_LABEL[k]} 기억`))),
      h("div", { class: "stat" }, h("b", {}, String((st.stats.handoffs || {}).open || 0)), h("span", {}, "열린 인계"))),
    h("small", { class: "muted block" }, st.project ? `지금 프로젝트: ${st.project}` : "작업 폴더를 고르면 그 폴더의 프로젝트 기억을 씁니다."),
    h("section", { class: "hub-group" }, h("h3", {}, "기억"),
      h("div", { class: "row wrap" }, search, layerSel),
      h("div", { class: "row wrap", style: "margin-top:8px" }, text, addLayer, addKind,
        h("button", { class: "btn", onclick: async () => {
          if (!text.value.trim()) return;
          const r = await hubCall(api().memory_add(text.value.trim(), addLayer.value, addKind.value));
          if (r) { toast(r.created ? "기억을 남겼습니다" : "같은 기억이 있어 갱신했습니다"); renderHub(); }
        } }, "남기기")),
      S.currentId ? h("button", { class: "link-btn", onclick: async () => {
        if (await hubCall(api().memory_summarize_thread(S.currentId))) toast("지금 대화를 요약하는 중… (모델을 한 번 부릅니다)");
      } }, "지금 대화를 요약해 대화 메모리에 남기기") : null,
      (st.items || []).length ? st.items.map(memoryItem) : h("small", { class: "muted block" }, MEM.query ? "맞는 기억이 없습니다." : "아직 남긴 기억이 없습니다.")),
    h("section", { class: "hub-group" }, h("h3", {}, `에이전트 인계 (${handoffs.length})`),
      handoffs.length ? handoffs.map(handoffItem) : h("small", { class: "muted block" }, "아직 인계가 없습니다. 통합 메모리를 켜고 에이전트가 파일을 고치면 자동으로 남깁니다.")),
    h("section", { class: "hub-group" }, h("h3", {}, "기기 사이 동기화"),
      featureToggle({ sync: { label: "클라우드 동기화", enabled: st.sync.feature } }, "sync"),
      st.sync.feature ? syncPanel(st.sync) : h("small", { class: "muted block" }, "켜면 Windows·macOS·Android 사이에서 메모리·대화·설정·PO노트를 맞춥니다(직접 켤 때만).")));
}

HUB_TABS.push({ id: "memory", label: "메모리·동기화", render: renderMemory });

window.hubExtraEvent = (ev) => {
  if (ev.kind === "sync_started") {
    MEM.syncNote = "동기화 중…";
  } else if (ev.kind === "sync_done") {
    const r = ev.report;
    MEM.syncNote = `동기화했습니다: 올림 ${r.uploaded}, 받음 ${r.downloaded}, 병합 ${r.merged}` + (r.errors.length ? ` · 오류 ${r.errors.length}개` : "");
    if (HUB.tab === "memory") renderHub();
  } else if (ev.kind === "sync_error") {
    MEM.syncNote = `동기화 실패: ${ev.error}`;
    if (HUB.tab === "memory") renderHub();
  } else if (ev.kind === "summary_done") {
    toast("대화 요약을 대화 메모리에 남겼습니다");
    if (HUB.tab === "memory") renderHub();
  } else if (ev.kind === "summary_error") {
    toast(`요약하지 못했습니다: ${ev.error}`);
  }
};

/* ---------- 에이전트 자동화 화면 (Phase 4, 1.11부터 PO노트처럼 본문에 연다) ---------- */

const AUTO = { tab: "python" };

async function renderAutomation(panel) {
  const st = await api().automation_state();
  const intro = pageIntro("에이전트 자동화",
    "에이전트가 Python 코드·Jupyter 노트북을 실행하거나 등록한 원격 서버(SSH)에서 명령을 실행하게 합니다. 실행할 때마다 대상과 내용을 보여 주고 승인을 받습니다.");
  if (st.android) {
    return fill(panel, intro, h("div", { class: "po-card po-warn" }, "Python·SSH 실행은 하위 프로세스를 띄울 수 없는 안드로이드에서는 쓸 수 없습니다. PC 앱에서 켜세요. ",
      "에이전트 인계(작업 상태·변경 파일·다음 단계)는 '연결·도구 → 메모리·동기화'에서 볼 수 있고, 동기화를 켜면 PC와 공유됩니다."));
  }
  if (!st.feature) {
    return fill(panel, intro, pageStart("에이전트 자동화가 꺼져 있습니다",
      "켜면 Python·Jupyter 실행과 원격 서버 실행을 설정할 수 있습니다. 각 실행 도구는 따로 켜며, 자동 허용 설정과 관계없이 실행마다 승인을 받습니다.",
      "에이전트 자동화 켜기", () => hubCall(api().set_feature("automation", true), "에이전트 자동화를 켰습니다")));
  }
  const pane = { python: automationPython, ssh: automationSsh, log: automationLog }[AUTO.tab] || automationPython;
  fill(panel, intro,
    pageTabs(AUTO, [["python", "Python · Jupyter", st.python.enabled ? "켜짐" : null],
      ["ssh", "원격 서버(SSH)", Object.keys(st.ssh.hosts || {}).length || null], ["log", "실행 기록", st.log.length || null]]),
    h("div", { class: "po-pane" }, pane(st)),
    pageFooter(h("button", { class: "link-btn", onclick: async () => {
      if (!confirm("에이전트 자동화를 끌까요? 등록한 호스트와 설정은 남겨 둡니다.")) return;
      await hubCall(api().set_feature("automation", false), "에이전트 자동화를 껐습니다");
      renderHub();
    } }, "에이전트 자동화 끄기")));
}

function automationToggle(cid, on, label) {
  return h("label", { class: "feature-toggle" },
    checkbox(on, async (v) => { if (await hubCall(api().set_connector_enabled(cid, v), v ? `${label}을(를) 켰습니다` : `${label}을(를) 껐습니다`)) renderHub(); }),
    h("span", {}, h("b", {}, label), h("small", {}, "켜면 에이전트가 이 실행 도구를 씁니다. 실행할 때마다 대상과 내용을 보여 주고 승인을 받습니다(자동 허용 설정과 관계없음).")));
}

function automationPython(st) {
  const py = st.python;
  const interp = h("input", { type: "text", value: py.interpreter, placeholder: py.detected ? `자동: ${py.detected}` : "python 실행 파일 경로" });
  const iso = h("select", { class: "policy-select" }, h("option", { value: "none" }, "격리 없음(이 PC의 사용자 권한)"),
    h("option", { value: "docker", disabled: !py.docker }, `Docker 격리${py.docker ? "" : " (Docker 없음)"}`));
  iso.value = py.isolation;
  const image = h("input", { type: "text", value: py.docker_image });
  const timeout = h("input", { type: "number", min: 5, max: 3600, value: py.timeout });
  const memory = h("input", { type: "number", min: 128, max: 65536, value: py.memory_mb });
  const info = h("pre", { class: "diff bib", hidden: true }, h("div", {}));
  return h("div", { class: "po-card" },
    automationToggle("python", py.enabled, "Python·Jupyter 실행"),
    py.error ? h("p", { class: "mcp-error" }, py.error) : null,
    h("div", { class: "field" }, h("label", {}, "Python · 격리"), h("div", { class: "row wrap" }, interp, iso)),
    h("div", { class: "field" }, h("label", {}, "Docker 이미지 · 시간 제한(초) · 메모리(MB, Docker·macOS/Linux)"), h("div", { class: "row wrap" }, image, timeout, memory)),
    h("div", { class: "row po-actions" },
      h("button", { class: "btn", onclick: async () => {
        const r = await hubCall(api().python_check());
        if (r) { info.hidden = false; info.firstChild.textContent = r.info; }
      } }, "확인"),
      h("button", { class: "btn primary", onclick: async () => {
        if (await hubCall(api().set_python_settings({ interpreter: interp.value.trim(), isolation: iso.value, docker_image: image.value.trim(),
          timeout: timeout.value, memory_mb: memory.value }), "저장했습니다")) renderHub();
      } }, "저장")),
    info);
}

function automationSsh(st) {
  const hosts = Object.entries(st.ssh.hosts || {});
  const f = {};
  for (const [k, ph] of [["alias", "별칭(예: gpu1)"], ["host", "호스트(예: gpu.example.ac.kr)"], ["user", "사용자"], ["port", "포트(22)"],
    ["identity_file", "키 파일(선택, ~/.ssh/id_ed25519)"], ["cwd", "원격 작업 폴더(선택)"], ["allowed_commands", "허용 명령 접두어(쉼표로, 예: nvidia-smi, python train.py)"]]) {
    f[k] = h("input", { type: "text", placeholder: ph });
  }
  const allowShell = checkbox(false, () => {});
  return h("div", { class: "tool-stack" },
    h("div", { class: "po-card" },
      automationToggle("ssh", st.ssh.enabled, "원격 서버 실행"),
      st.ssh.client ? null : h("p", { class: "mcp-error" }, "이 PC에서 ssh 명령을 찾지 못했습니다(Windows는 설정 → 선택적 기능 → OpenSSH 클라이언트)."),
      hosts.length ? h("div", { class: "table-scroll" }, h("table", { class: "help-table log-table" }, hosts.map(([alias, hst]) => h("tr", {},
        h("td", { class: "mono" }, alias), h("td", {}, `${hst.user ? hst.user + "@" : ""}${hst.host}:${hst.port || 22}`),
        h("td", { class: "small" }, (hst.allowed_commands || []).join(", ") || "제한 없음"),
        h("td", {}, h("button", { class: "link-btn danger", onclick: async () => { if (await hubCall(api().remove_ssh_host(alias))) renderHub(); } }, "지우기"))))))
        : h("small", { class: "muted block" }, "등록한 호스트가 없습니다.")),
    h("div", { class: "po-card" }, h("div", { class: "po-label" }, "호스트 등록",
      h("small", {}, "비밀번호는 쓰지 않습니다. 이 PC의 ssh 키·ssh-agent로 접속하고, 처음 보는 호스트 키는 자동으로 믿지 않습니다.")),
      h("div", { class: "row wrap" }, f.alias, f.host, f.user, f.port),
      h("div", { class: "row wrap", style: "margin-top:6px" }, f.identity_file, f.cwd),
      h("div", { class: "row wrap", style: "margin-top:6px" }, f.allowed_commands),
      h("label", { class: "inline-label" }, allowShell, "셸 연결 문자(; && | > 등) 허용 — 권장하지 않음"),
      h("div", { class: "row po-actions" }, h("button", { class: "btn primary", onclick: async () => {
        const spec = Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.value.trim()]));
        spec.allow_shell = allowShell.checked;
        if (await hubCall(api().set_ssh_host(spec.alias, spec), "등록했습니다")) renderHub();
      } }, "등록"))));
}

function automationLog(st) {
  return st.log.length ? h("div", { class: "po-card table-scroll" }, h("table", { class: "help-table log-table" }, st.log.map((r) => h("tr", {},
    h("td", {}, fmtTime(r.ts)), h("td", {}, r.kind), h("td", { class: "mono small" }, r.target),
    h("td", {}, r.timed_out ? "시간 초과" : `코드 ${r.code}`), h("td", { class: "mono small" }, (r.input || "").slice(0, 120))))))
    : h("p", { class: "po-empty" }, "아직 실행 기록이 없습니다. 실행한 코드·명령과 결과 앞부분이 최근 30개까지 여기에 남습니다.");
}

/* ---------- 사용량·진단 탭 (Phase 5) ---------- */

const DIAG = { days: 30, evalNote: "", models: null };
const pct = (x) => x == null ? "-" : `${Math.round(x * 1000) / 10}%`;
const ms = (x) => x == null ? "-" : x >= 1000 ? `${(x / 1000).toFixed(1)}s` : `${x}ms`;
const num = (x) => x == null ? "-" : Number(x).toLocaleString();

function diagTable(head, rows) {
  return h("div", { class: "table-scroll" }, h("table", { class: "help-table diag-table" },
    h("tr", {}, head.map((c) => h("th", {}, c))), rows.map((r) => h("tr", {}, r.map((c) => h("td", {}, c))))));
}

async function renderDiagnostics(panel) {
  const st = await api().diagnostics_state(DIAG.days);
  const sm = st.summary;
  const days = h("select", { class: "policy-select" }, [7, 30, 90].map((d) => h("option", { value: d }, `최근 ${d}일`)));
  days.value = String(DIAG.days);
  days.addEventListener("change", () => { DIAG.days = Number(days.value); renderHub(); });
  const calls = sm.models.reduce((a, m) => a + m.calls, 0);
  const errors = sm.models.reduce((a, m) => a + m.errors, 0);
  const agentRuns = sm.agent.agent || { runs: 0, success_rate: null, avg_steps: 0 };
  const toolCalls = sm.tools.reduce((a, t) => a + t.calls, 0);
  const toolOk = sm.tools.reduce((a, t) => a + t.ok, 0);
  const lf = st.langfuse || {};
  const lfOn = checkbox(lf.enabled, () => {});
  const lfHost = h("input", { type: "url", value: lf.host || "", placeholder: "https://cloud.langfuse.com" });
  const lfPub = h("input", { type: "password", placeholder: lf.has_public ? "공개 키 저장됨" : "공개 키(pk-lf-…)" });
  const lfSec = h("input", { type: "password", placeholder: lf.has_secret ? "비밀 키 저장됨" : "비밀 키(sk-lf-…)" });
  const lfContent = checkbox(lf.include_content, () => {});
  const setSel = h("select", { class: "policy-select" }, st.eval_sets.map((e) => h("option", { value: e.name }, `${e.name} — ${e.description} (${e.cases}개)`)));
  DIAG.models = DIAG.models || new Set(st.models.slice(0, 2).map((m) => m.id));
  const modelBoxes = st.models.map((m) => h("label", { class: "inline-label sync-include" },
    checkbox(DIAG.models.has(m.id), (on) => (on ? DIAG.models.add(m.id) : DIAG.models.delete(m.id))), m.label.split(" — ")[0]));
  const progress = h("small", { class: "muted block" }, DIAG.evalNote || (st.evaluating ? "평가하는 중…" : ""));
  DIAG.progressNode = progress;
  fill(panel,
    h("p", { class: "hub-intro" }, "이 앱이 보낸 모델 호출·도구 호출·에이전트 실행의 성공률·지연·토큰을 모아 봅니다. 기록에는 질문·답변·문서 내용이 없고 ",
      "(메타데이터만) 이 기기에만 90일 보관합니다. 외부 관측 서비스(Langfuse)로 보내는 것은 직접 켤 때만 합니다."),
    featureToggle({ observability: { label: "사용량·진단 기록", enabled: st.feature } }, "observability", "끄면 새 기록을 남기지 않습니다(이미 남은 기록은 그대로)."),
    h("div", { class: "row wrap" }, days),
    h("div", { class: "stat-grid" },
      h("div", { class: "stat" }, h("b", {}, num(calls)), h("span", {}, "모델 호출")),
      h("div", { class: "stat" }, h("b", {}, calls ? pct(errors / calls) : "-"), h("span", {}, "호출 오류율")),
      h("div", { class: "stat" }, h("b", {}, sm.credits_total == null ? "추정 불가" : `약 ${num(sm.credits_total)}`), h("span", {}, "크레딧 추정(근거 있는 모델만)")),
      h("div", { class: "stat" }, h("b", {}, agentRuns.runs ? pct(agentRuns.success_rate) : "-"), h("span", {}, `에이전트 성공률 (${agentRuns.runs}회, 평균 ${agentRuns.avg_steps}단계)`)),
      h("div", { class: "stat" }, h("b", {}, toolCalls ? pct(toolOk / toolCalls) : "-"), h("span", {}, `MCP 도구 성공률 (${num(toolCalls)}회)`))),
    h("section", { class: "hub-group" }, h("h3", {}, "모델별 비교"),
      sm.models.length ? diagTable(["모델", "호출", "오류율", "평균", "p95", "입력 토큰", "출력 토큰", "크레딧(추정)", "재시도", "👍", "👎", "평가 점수"],
        sm.models.map((m) => [m.model, num(m.calls), pct(m.error_rate), ms(m.avg_ms), ms(m.p95_ms), num(m.input_tokens), num(m.output_tokens),
          m.credits == null ? "추정 불가" : num(m.credits), num(m.retries), num(m.feedback_up), num(m.feedback_down), m.eval_score == null ? "-" : pct(m.eval_score)]))
        : h("small", { class: "muted block" }, "아직 기록이 없습니다."),
      h("small", { class: "muted block" }, `크레딧은 앱 안내에 근거가 있는 모델(${st.documented_credit_models.join(", ")})만 추정합니다. 토큰 수는 서버가 알려 준 호출만 셉니다. `,
        "답변 아래 👍·👎로 남긴 평가가 모델별로 모입니다.")),
    adaptiveDiagnostics(st.adaptive),
    (S.config || {}).developer_mode ? adaptiveDevSection() : null,
    h("section", { class: "hub-group" }, h("h3", {}, "MCP 도구"),
      sm.tools.length ? diagTable(["도구", "종류", "호출", "성공률", "거부·차단", "재시도", "평균"],
        sm.tools.map((t) => [t.tool, KIND_LABEL[t.kind] || t.kind || "-", num(t.calls), pct(t.success_rate), num(t.denied), num(t.retries), ms(t.avg_ms)]))
        : h("small", { class: "muted block" }, "아직 도구 호출 기록이 없습니다.")),
    h("section", { class: "hub-group" }, h("h3", {}, "자동 평가"),
      h("small", { class: "muted block" }, "같은 질문 세트를 여러 모델에 보내 규칙(포함·정규식·JSON 형식·길이)으로 채점합니다. 모델이 채점하지 않으므로 같은 답이면 같은 점수입니다. ",
        "호출 수(항목 수 × 모델 수)만큼 크레딧을 씁니다. 직접 만든 세트는 데이터 폴더의 evals/*.json에 둡니다."),
      h("div", { class: "row wrap" }, setSel),
      h("div", { class: "row wrap", style: "margin:6px 0" }, modelBoxes),
      h("div", { class: "row wrap" },
        h("button", { class: "btn", disabled: st.evaluating, onclick: async () => {
          const chosen = [...DIAG.models];
          const set = st.eval_sets.find((e) => e.name === setSel.value);
          if (!chosen.length) return toast("모델을 고르세요");
          if (!confirm(`${set.cases * chosen.length}번 모델을 부릅니다(크레딧 사용). 평가할까요?`)) return;
          if (await hubCall(api().eval_run(setSel.value, chosen))) { DIAG.evalNote = "평가하는 중…"; renderHub(); }
        } }, "평가 실행"),
        st.evaluating ? h("button", { class: "btn", onclick: () => api().eval_cancel() }, "중지") : null),
      progress,
      (st.eval_results || []).length ? diagTable(["결과", "모델", "점수", "통과", "평균 지연"],
        st.eval_results.flatMap((r) => Object.entries(r.models).map(([m, v]) => [`${fmtTime(r.started)} ${r.set}`, m, pct(v.score), `${v.passed}/${v.cases}`, ms(v.ms)])))
        : null),
    h("section", { class: "hub-group" }, h("h3", {}, "외부 관측 서비스 (Langfuse, 선택)"),
      h("small", { class: "muted block" }, "켜면 위 기록(모델·토큰·지연·성공 여부)을 1분마다 Langfuse로 보냅니다. 키는 이 기기의 보안 저장소에만 둡니다."),
      h("label", { class: "feature-toggle" }, lfOn, h("span", {}, "Langfuse로 보내기")),
      h("div", { class: "field" }, h("label", {}, "주소 · 키"), h("div", { class: "row wrap" }, lfHost, lfPub, lfSec)),
      h("label", { class: "feature-toggle" }, lfContent, h("span", {}, "질문·답변 앞부분도 보내기(권장하지 않음)",
        h("small", {}, "켜도 키·토큰·이메일 같은 비밀 패턴은 가린 뒤 2,000자까지만 보냅니다. 개인 문서·민감한 대화가 외부 서비스에 남을 수 있습니다."))),
      h("div", { class: "row wrap" },
        h("button", { class: "btn", onclick: async () => {
          if (lfContent.checked && !lf.include_content && !confirm("질문·답변 내용 일부가 Langfuse로 전송됩니다. 계속할까요?")) return;
          if (await hubCall(api().set_telemetry_settings({ enabled: lfOn.checked, host: lfHost.value.trim(), include_content: lfContent.checked,
            public_key: lfPub.value.trim(), secret_key: lfSec.value.trim() }), "저장했습니다")) renderHub();
        } }, "저장"),
        lf.enabled ? h("button", { class: "btn", onclick: async () => { const r = await hubCall(api().telemetry_export_now()); if (r) toast(`${r.sent}건 보냈습니다${r.export.last_error ? " · " + r.export.last_error : ""}`); } }, "지금 보내기") : null),
      lf.enabled ? h("small", { class: "muted block" }, `보낸 이벤트 ${sm.export.sent}건 · 대기 ${sm.export.pending}건${sm.export.last_error ? ` · 마지막 오류: ${sm.export.last_error}` : ""}`) : null),
    h("section", { class: "hub-group" }, h("h3", {}, "이 앱의 API 사용량(1.9부터)"),
      usageChart(st.usage.daily),
      diagTable(["기간", "호출", "토큰 입력", "토큰 출력"], [["오늘", st.usage.today], [`이번 달 (${st.usage.month_name})`, st.usage.month], ["최근 30일", st.usage.last30]]
        .map(([label, u]) => [label, num(u.calls), num(u.input_tokens), num(u.output_tokens)]))));
}

// 1.17 Adaptive AI 통계. 측정하지 않은 값은 '-'·'추정 불가'로 두고, 로컬의 Cloud 비용 0은 'Cloud API 비용만 0'임을 밝힌다.
function adaptiveDiagnostics(ad) {
  if (!ad || ad.error) return null;
  const a = ad.summary || {};
  const lat = (x) => (x ? `${ms(x.avg)} / p95 ${ms(x.p95)}` : "-");
  const succ = (x) => (x && x.checked ? `${pct(x.rate)} (${x.ok}/${x.checked})` : "-");
  return h("section", { class: "hub-group" }, h("h3", {}, "Adaptive AI (자동 모델 선택, 1.17)"),
    h("small", { class: "muted block" }, ad.enabled ? `켜짐 · 정책 ${ad.policy}` : "꺼짐 — 설정 → AI 실행 정책에서 켤 수 있습니다. 아래는 켰던 동안의 기록입니다."),
    a.requests ? h("div", { class: "stat-grid" },
      h("div", { class: "stat" }, h("b", {}, num(a.requests)), h("span", {}, "자동으로 고른 요청")),
      h("div", { class: "stat" }, h("b", {}, pct(a.local_ratio)), h("span", {}, `로컬로 끝냄 (${num(a.local)})`)),
      h("div", { class: "stat" }, h("b", {}, pct(a.cloud_ratio)), h("span", {}, `Cloud가 답함 (${num(a.cloud)}, 승격 포함)`)),
      a.light ? h("div", { class: "stat" }, h("b", {}, pct(a.light_ratio)), h("span", {}, `경량 Cloud 모델로 보냄 (${num(a.light)}, 상담 ${num(a.consults)})`)) : null,
      a.frontier_token_saving_est != null ? h("div", { class: "stat" }, h("b", {}, pct(a.frontier_token_saving_est)),
        h("span", {}, `프런티어 입력 토큰 줄임(추정): ${num(a.frontier_tokens_est)} / 모두 프런티어였다면 ${num(a.baseline_tokens_est)}`)) : null,
      h("div", { class: "stat" }, h("b", {}, pct(a.escalation_ratio)), h("span", {}, `로컬 → Cloud 승격 (${num(a.escalations)})`)),
      h("div", { class: "stat" }, h("b", {}, a.saved_credits_est == null ? "추정 불가" : `약 ${num(a.saved_credits_est)}`),
        h("span", {}, "로컬로 처리해 쓰지 않은 Cloud 크레딧(추정)"))) : h("small", { class: "muted block" }, "아직 자동으로 고른 요청이 없습니다."),
    a.requests ? diagTable(["", "로컬", "Cloud"], [
      ["평균 / p95 지연", lat(a.latency_local), lat(a.latency_cloud)],
      ["검증 통과율(검증할 수 있었던 답)", succ(a.success_local), succ(a.success_cloud)],
      ["답변 평가 👍/👎", `${num(a.feedback?.local?.up)} / ${num(a.feedback?.local?.down)}`, `${num(a.feedback?.cloud?.up)} / ${num(a.feedback?.cloud?.down)}`],
      ["Cloud 요청당 크레딧(추정)", "Cloud API 비용 없음", a.credits_per_cloud_request == null ? "추정 불가" : num(a.credits_per_cloud_request)],
    ]) : null,
    Object.keys(a.measured_tokens || {}).length ? diagTable(["서버가 알려 준 실제 토큰", "호출", "입력", "출력", "캐시 읽기", "캐시 쓰기"],
      Object.entries(a.measured_tokens).map(([tier, m]) => [{ light: "경량", frontier: "프런티어" }[tier] || tier, num(m.calls), num(m.input_tokens),
        num(m.output_tokens), num(m.cache_read_input_tokens), num(m.cache_creation_input_tokens)])) : null,
    (a.models || []).length ? diagTable(["모델", "호출", "오류율", "평균", "p95"], a.models.map((m) => [m.model, num(m.calls), pct(m.error_rate), ms(m.avg_ms), ms(m.p95_ms)])) : null,
    Object.keys(a.failures || {}).length ? h("small", { class: "muted block" }, "보낼 곳이 없거나 막힌 요청: " + Object.entries(a.failures).map(([k, v]) => `${k} ${v}번`).join(", ")) : null,
    h("small", { class: "muted block" }, "로컬의 비용 0은 Cloud API 청구 비용만 0이라는 뜻입니다(이 PC의 전기·하드웨어 비용은 따로이며 재지 않습니다). ",
      "크레딧은 앱 안내에 근거가 있는 Cloud 모델만 추정하고, 근거가 없는 모델은 '추정 불가'로 둡니다(" + (a.saved_unknown ? `${a.saved_unknown}건 추정 불가` : "모두 추정함") + "). ",
      "POSTECH 크레딧과 Claude API 요금(USD)은 바꾸거나 더하지 않습니다. 검증 통과율은 규칙으로 확인할 수 있었던 답만 셉니다. ",
      "프런티어 토큰은 글자 수로 어림한 입력 토큰이며, 경량 모델이 쓴 토큰(" + (a.light_tokens_est == null ? "-" : num(a.light_tokens_est)) + ")은 따로입니다."));
}

/* 개발자 모드: Adaptive AI 원자료(내용 없는 기록·실측 토큰·손익분기 표). 누를 때만 불러온다. */
function adaptiveDevSection() {
  const out = h("div", {});
  const load = async () => {
    const r = await api().adaptive_dev_data(DIAG.days);
    if (!r.ok) return fill(out, h("small", { class: "muted block" }, r.error));
    const tierName = { local: "로컬", light: "경량", frontier: "프런티어" };
    const json = JSON.stringify(r, null, 2);
    fill(out,
      diagTable(["단계", "호출", "실측한 호출", "입력(추정)", "입력(실측)", "출력", "캐시 읽기", "캐시 쓰기", "캐시 적중"],
        Object.entries(r.tokens).map(([t, m]) => [tierName[t] || t, num(m.calls), num(m.measured_calls), num(m.est_input), num(m.input_tokens),
          num(m.output_tokens), num(m.cache_read_input_tokens), num(m.cache_creation_input_tokens), pct(m.cache_hit_ratio)])),
      diagTable(["요청 길이(토큰)", "손익분기 (지금 단가·실측 분포)"],
        Object.entries(r.economics).map(([t, e]) => [t, window.econText ? window.econText(e) : JSON.stringify(e)])),
      h("div", { class: "dev-events" }, diagTable(["시각", "종류", "단계·모델", "ms", "결과", "토큰"],
        r.events.slice(-60).reverse().map((e) => [new Date(e.ts * 1000).toLocaleTimeString(), e.type,
          [e.tier, e.provider, e.model || e.to_model || e.frontier_model].filter(Boolean).join(" · "), e.ms ?? "-",
          e.ok === false ? "실패 " + (e.error || "") : e.ok ? "성공" : (e.reason || e.kind || "-"),
          e.input_tokens != null ? (window.devTokens ? window.devTokens(e) : "") : (e.est_tokens != null ? `추정 ${e.est_tokens}` : "-")]))),
      h("small", { class: "muted block" }, `최근 ${r.days}일 기록 ${r.event_count}개 중 마지막 60개. 질문·답·첨부 내용은 기록하지 않습니다.`),
      h("div", { class: "row" }, h("button", { class: "btn", type: "button", onclick: () => copyText(json) }, "JSON 복사")),
      h("details", {}, h("summary", {}, "원본 JSON"), h("pre", { class: "dev-events" }, json)));
  };
  fill(out, h("button", { class: "btn", type: "button", onclick: load }, "개발자 데이터 불러오기"));
  return h("section", { class: "hub-group" }, h("h3", {}, "Adaptive AI 개발자 데이터 (개발자 모드)"), out);
}

HUB_TABS.push({ id: "diagnostics", label: "사용량·진단", render: renderDiagnostics });

const _hubExtraEvent = window.hubExtraEvent;
window.hubExtraEvent = (ev) => {
  if (ev.kind === "eval_progress") {
    DIAG.evalNote = `평가하는 중… ${ev.done}/${ev.total} (${ev.model})`;
    if (DIAG.progressNode) DIAG.progressNode.textContent = DIAG.evalNote;
  } else if (ev.kind === "eval_done") {
    DIAG.evalNote = "평가를 마쳤습니다: " + Object.entries(ev.summary).map(([m, v]) => `${m} ${pct(v.score)}`).join(", ");
    if (HUB.tab === "diagnostics") renderHub();
  } else if (ev.kind === "eval_error") {
    DIAG.evalNote = `평가 실패: ${ev.error}`;
    if (HUB.tab === "diagnostics") renderHub();
  } else if (_hubExtraEvent) {
    _hubExtraEvent(ev);
  }
};

/* ---------- 플러그인 화면 (1.12): Anthropic Knowledge Work Plugins ----------
   직무별 스킬 묶음을 받아 설치하고 켜고 끈다. Python 쪽은 workspace_api.plugin_* · plugins.py. */

const PLUG = { tab: "browse", query: "", data: null, busy: "", status: "" };

function pluginMatches(p, q) {
  if (!q) return true;
  const hay = [p.name, p.display_name, p.summary, p.description,
    ...[...(p.skills || []), ...(p.commands || [])].map((s) => `${s.name} ${s.description} ${s.description_ko || ""}`)]
    .join(" ").toLowerCase();
  return q.toLowerCase().split(/\s+/).every((w) => hay.includes(w));
}

function pluginSlash(p, item) {
  return `/${p.name}:${item.name}`;
}

// 대화 입력창에 /플러그인:스킬을 넣고 채팅으로 돌아간다
function usePluginSkill(command) {
  leaveViews();
  const input = $("#input");
  input.value = command + " ";
  autoresize();
  updateSend();
  input.focus();
  toast(`${command} 를 입력창에 넣었습니다. 요청을 덧붙여 보내세요`);
}

async function pluginAction(promise, okText) {
  const res = await hubCall(promise, okText);
  if (!res) return null;
  if (res.skills) S.skills = res.skills;  // / 메뉴에 바로 보이도록
  if (PLUG.data) PLUG.data.installed = res.installed;
  return res;
}

async function installPlugin(p) {
  if (p.partner && !confirm(`'${p.display_name}'은(는) 파트너가 만든 플러그인입니다. 그 지침이 에이전트에게 전달됩니다. 설치할까요?`)) return;
  PLUG.busy = p.name;
  PLUG.status = `${p.display_name} 설치 중...`;
  renderHub();
  try {
    if (await pluginAction(api().plugin_install(p.name), `${p.display_name} 플러그인을 설치했습니다`)) {
      PLUG.status = `${p.display_name} 설치 완료 — 스킬 ${p.skills.length + p.commands.length}개를 쓸 수 있습니다.`;
    } else {
      PLUG.status = "";
    }
  } finally {
    PLUG.busy = "";
    renderHub();
  }
}

async function removePlugin(p) {
  if (!confirm(`'${p.display_name}' 플러그인을 지울까요? 나중에 다시 설치할 수 있습니다.`)) return;
  if (await pluginAction(api().plugin_remove(p.name), "지웠습니다")) {
    PLUG.status = `${p.display_name} 플러그인을 지웠습니다.`;
    renderHub();
  }
}

function pluginSwitch(p, inst) {
  const on = inst.enabled !== false;
  return h("button", { class: "switch" + (on ? " on" : ""), role: "switch", "aria-checked": String(on),
    "aria-label": `${p.display_name} 사용`, title: on ? "켜짐: 에이전트가 이 플러그인의 스킬을 씁니다" : "꺼짐",
    onclick: async () => {
      if (await pluginAction(api().plugin_set_enabled(p.name, !on), on ? `${p.display_name}을(를) 껐습니다` : `${p.display_name}을(를) 켰습니다`)) renderHub();
    } }, h("span", { class: "switch-thumb", "aria-hidden": "true" }), h("span", { class: "switch-label" }, on ? "켜짐" : "꺼짐"));
}

function pluginCard(p) {
  const inst = (PLUG.data.installed || {})[p.name];
  const count = (p.skills || []).length + (p.commands || []).length;
  const titleId = `plugin-${p.name}`;
  const actions = p.installable ? (inst
    ? [pluginSwitch(p, inst),
      h("button", { class: "btn", onclick: () => showPluginDetail(p.name), "aria-describedby": titleId }, "스킬 보기"),
      h("button", { class: "link-btn danger", onclick: () => removePlugin(p), "aria-label": `${p.display_name} 제거` }, "제거")]
    : [h("button", { class: "btn primary", disabled: !!PLUG.busy, onclick: () => installPlugin(p), "aria-describedby": titleId },
      PLUG.busy === p.name ? "설치 중..." : "설치"),
      h("button", { class: "btn", onclick: () => showPluginDetail(p.name), "aria-describedby": titleId }, "자세히")])
    : [safeHref(p.homepage) ? h("a", { class: "btn", href: safeHref(p.homepage), target: "_blank", rel: "noopener" }, "홈페이지") : null];
  return h("li", { class: "plugin-card" + (inst && inst.enabled !== false ? " installed" : "") },
    h("div", { class: "plugin-head" },
      h("h3", { id: titleId }, p.display_name),
      h("span", { class: "badge" }, p.external ? "다른 저장소" : p.partner ? "파트너" : "Anthropic"),
      inst ? h("span", { class: "badge st-ok" }, "설치됨") : null),
    p.summary ? h("p", { class: "plugin-summary" }, p.summary) : null,
    // 1.19: 한국어 소개가 있으면 영문 원문은 접어 둔다
    p.summary ? (p.description ? h("details", { class: "plugin-orig" }, h("summary", {}, "영문 원문"), h("p", { class: "plugin-desc", lang: "en" }, p.description)) : null)
      : h("p", { class: "plugin-desc", lang: "en" }, p.description),
    p.installable ? h("p", { class: "plugin-meta" }, `스킬 ${count}개` + (p.version ? ` · v${p.version}` : "")
      + ((p.connectors || []).length ? ` · 외부 도구 ${p.connectors.length}개 연동 안내` : "")) : null,
    h("div", { class: "row wrap plugin-actions" }, actions));
}

async function renderPlugins(panel, refresh = false) {
  if (!PLUG.data || refresh) {
    const res = await api().plugins_state(refresh);
    if (res.ok === false) {
      PLUG.data = null;
      return fill(panel, pageIntro("플러그인", "직무별 스킬 묶음을 설치하면 에이전트가 그 분야의 절차대로 일합니다."),
        h("div", { class: "po-card po-warn", role: "alert" }, res.error, " 인터넷 연결을 확인하고 다시 시도하세요."),
        h("div", { class: "row" }, h("button", { class: "btn primary", onclick: () => renderPlugins(panel, true) }, "다시 시도")));
    }
    PLUG.data = res;
  }
  const data = PLUG.data;
  const installed = data.installed || {};
  const all = data.plugins || [];
  const lists = {
    browse: all.filter((p) => p.installable),
    installed: all.filter((p) => installed[p.name]),
    external: all.filter((p) => !p.installable),
  };
  const shown = (lists[PLUG.tab] || lists.browse).filter((p) => pluginMatches(p, PLUG.query));
  const search = h("input", { type: "search", id: "plugin-search", value: PLUG.query, placeholder: "이름·스킬·설명으로 찾기 (예: pdf, 논문, SQL)",
    "aria-label": "플러그인 검색", autocomplete: "off" });
  search.addEventListener("input", () => {
    PLUG.query = search.value;
    const list = panel.querySelector(".plugin-grid");
    const items = (lists[PLUG.tab] || lists.browse).filter((p) => pluginMatches(p, PLUG.query));
    if (list) fill(list, items.map(pluginCard));
    const count = panel.querySelector("#plugin-count");
    if (count) count.textContent = `${items.length}개`;
  });
  const updated = data.updated ? new Date(data.updated * 1000).toLocaleString() : "";
  const refreshBtn = h("button", { class: "btn", onclick: async (e) => {
    e.target.disabled = true;
    PLUG.status = "목록을 새로 받는 중...";
    renderHub();
    await renderPlugins(panel, true);
    PLUG.status = "목록을 새로 받았습니다.";
    renderHub();
  } }, "목록 새로 받기");
  fill(panel,
    pageIntro("플러그인",
      "직무별 스킬 묶음을 설치하면 에이전트가 그 분야의 절차대로 일합니다. 설치한 스킬은 에이전트가 알아서 쓰고, 입력창에 /플러그인:스킬 로 직접 부를 수도 있습니다.",
      refreshBtn),
    h("p", { class: "visually-hidden", role: "status", "aria-live": "polite" }, PLUG.status),
    PLUG.status ? h("div", { class: "po-card po-warn", "aria-hidden": "true" }, PLUG.status) : null,
    pageTabs(PLUG, [["browse", "둘러보기", lists.browse.length], ["installed", "설치됨", Object.keys(installed).length || null],
      ["external", "다른 저장소", lists.external.length]]),
    h("div", { class: "row wrap plugin-toolbar" }, search, h("small", { class: "muted", id: "plugin-count", "aria-live": "polite" }, `${shown.length}개`)),
    PLUG.tab === "external" ? h("p", { class: "po-card po-warn" },
      "다른 회사 저장소에 있는 플러그인입니다. POSCHAT이 그 코드를 검토할 수 없어 앱 안에서는 설치하지 않습니다. 홈페이지에서 내용을 확인하세요.") : null,
    shown.length ? h("ul", { class: "plugin-grid", "aria-label": "플러그인 목록" }, shown.map(pluginCard))
      : h("p", { class: "po-empty" }, PLUG.tab === "installed" && !PLUG.query
        ? "아직 설치한 플러그인이 없습니다. '둘러보기'에서 하나 골라 설치해 보세요. 학생·연구자에게는 Productivity, Bio Research, Data를 먼저 권합니다."
        : "맞는 플러그인이 없습니다."),
    h("div", { class: "row wrap tool-footer" },
      h("span", { style: "flex:1" }, "출처: ", h("a", { href: data.source, target: "_blank", rel: "noopener" }, "anthropics/knowledge-work-plugins"),
        " (Apache-2.0)" + (updated ? ` · 목록 ${updated}` : "") + ". 플러그인의 외부 커넥터(Slack 등)는 연결하지 않고, 첨부한 자료와 POSCHAT 커넥터로 동작합니다."),
      h("button", { class: "link-btn", onclick: () => showHub() }, "연결·도구 열기")));
}

async function showPluginDetail(name) {
  const res = await api().plugin_detail(name);
  if (res.ok === false) return toast(res.error);
  const p = res.plugin;
  const inst = res.installed;
  const items = [...(p.skills || []).map((x) => ({ ...x, kind: "스킬" })), ...(p.commands || []).map((x) => ({ ...x, kind: "명령" }))];
  const skillList = h("ul", { class: "plugin-skills" }, items.map((it) => {
    const cmd = pluginSlash(p, it);
    return h("li", {},
      h("div", { class: "plugin-skill-head" },
        h("code", {}, cmd), h("span", { class: "badge" }, it.kind),
        inst && inst.enabled !== false ? h("button", { class: "link-btn", "aria-label": `${cmd} 대화에서 쓰기`,
          onclick: () => { dlg.close(); usePluginSkill(cmd); } }, "대화에서 쓰기") : null),
      it.description_ko ? h("p", {}, it.description_ko) : h("p", { lang: "en" }, it.description || "(설명 없음)"),
      it.description_ko && it.description ? h("details", { class: "plugin-orig" }, h("summary", {}, "영문 원문"), h("p", { lang: "en" }, it.description)) : null,
      it.argument ? h("small", { class: "muted" }, `인자: ${it.argument}`) : null);
  }));
  const body = h("div", { class: "plugin-detail" },
    p.summary ? h("p", {}, p.summary) : null,
    p.summary && p.description ? h("details", { class: "plugin-orig" }, h("summary", {}, "영문 원문"), h("p", { class: "muted", lang: "en" }, p.description))
      : h("p", { class: "muted", lang: "en" }, p.description),
    h("p", { class: "small muted" }, [p.partner ? `파트너 제작${p.author ? ` (${p.author})` : ""}` : "Anthropic 제작", p.version ? `v${p.version}` : ""].filter(Boolean).join(" · "),
      " · ", h("a", { href: safeHref(p.homepage), target: "_blank", rel: "noopener" }, "원본 보기")),
    h("h3", {}, `스킬과 명령 ${items.length}개`),
    inst ? null : h("p", { class: "small muted" }, "설치하면 에이전트가 요청에 맞는 스킬을 알아서 쓰고, 입력창에 아래 이름으로 직접 부를 수도 있습니다."),
    skillList,
    (p.connectors || []).length ? h("div", { class: "po-card po-warn" },
      h("b", {}, "외부 도구 안내: "), p.connectors.join(", "),
      h("br"), "원래 플러그인은 이 도구들에 연결해 씁니다. POSCHAT은 이 연결을 만들지 않으므로, 필요한 자료는 첨부하거나 붙여 넣거나 ",
      "POSCHAT 커넥터(GitHub·Google·Notion·Zotero)를 켜서 쓰세요.") : null,
    p.readme ? h("details", { class: "plugin-readme" }, h("summary", {}, "설명서 (README, 영문)"), renderMarkdown(p.readme)) : null);
  const buttons = p.installable ? (inst
    ? [{ label: "제거", action: async (close) => { close(); await removePlugin(p); } }, { label: "닫기", class: "primary" }]
    : [{ label: "닫기" }, { label: "설치", class: "primary", action: async (close) => { close(); await installPlugin(p); } }])
    : [{ label: "닫기", class: "primary" }];
  const dlg = modal({ title: p.display_name, body, wide: true, buttons });
}

$("#btn-plugins").addEventListener("click", () => pageOpen("plugins"));

$("#btn-research").addEventListener("click", () => pageOpen("research"));
$("#btn-auto").addEventListener("click", () => pageOpen("automation"));

/* ---------- 백엔드 이벤트 ---------- */

function hubEvent(ev) {
  if (ev.type === "hub") return hubPanelEvent(ev);
  if (ev.type !== "connector") return;
  if (ev.kind === "device_code") {
    modal({
      title: "GitHub 로그인",
      body: h("div", {},
        h("p", {}, "브라우저에서 열린 GitHub 페이지에 아래 코드를 입력하세요."),
        h("div", { class: "device-code" }, ev.user_code),
        h("p", {}, h("a", { href: safeHref(ev.url), target: "_blank", rel: "noopener" }, ev.url))),
      buttons: [{ label: "코드 복사", action: () => copyText(ev.user_code) },
        { label: "취소", action: (close) => { api().connector_cancel_login(ev.id); close(); } },
        { label: "닫기", class: "primary" }],
    });
  } else if (ev.kind === "login_url") {
    toast("브라우저에서 로그인을 마치세요. 창이 열리지 않으면 연결 설정에서 다시 시도하세요.");
  } else if (ev.kind === "login_done") {
    toast(ev.status && ev.status.state === "connected" ? "연결했습니다" : (ev.status.detail || "로그인했습니다"));
    renderHub();
  } else if (ev.kind === "login_error") {
    toast(ev.error);
    renderHub();
  }
}

function hubPanelEvent(ev) {
  if (ev.kind === "index_progress") {
    RESEARCH.progress = `인덱싱 중... ${ev.done}/${ev.total} ${ev.name}`;
    if (RESEARCH.progressNode) RESEARCH.progressNode.textContent = RESEARCH.progress;
  } else if (ev.kind === "index_done") {
    const s = ev.summary;
    RESEARCH.progress = `인덱싱 완료: 새로 ${s.indexed}개, 그대로 ${s.unchanged}개, 지움 ${s.removed}개, 청크 ${s.chunks}개` +
      (s.failed.length ? ` · 실패 ${s.failed.length}개 (${s.failed.slice(0, 3).join("; ")})` : "");
    if (hubShowing("research")) renderHub();
  } else if (ev.kind === "index_error") {
    RESEARCH.progress = `인덱싱 실패: ${ev.error}`;
    if (hubShowing("research")) renderHub();
  } else if (window.hubExtraEvent) {
    hubExtraEvent(ev);
  }
}
