// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

/* ---------- PO노트: 강의 녹음 → 실시간 전사 → 강의 자료와 함께 필기 노트 ----------
   app.js 다음에 불러온다. app.js의 h, $, api, S, modal, toast, renderMarkdown, ICONS 등을 쓴다.
   Python 쪽은 main.Bridge의 po_* 메서드이고, 진행 상황은 {"type": "po", "kind": ...} 이벤트로 온다. */

const PO = {
  open: false,
  list: [],
  note: null,        // 열린 노트 전체(전사·노트·메모 포함)
  tab: "transcript",
  editing: false,
  state: null,       // po_state() 결과: 엔진 설정·녹음·내려받기·노트 만들기 상태
  live: { level: 0, speaking: false, elapsed: 0 },
  streaming: "",     // 만드는 중인 노트 글
  genStatus: "",
  memoTimer: 0,
};

const MATERIAL_ACCEPT = ".pptx,.pdf,.docx,.hwp,.hwpx,.xlsx,.xlsm,.txt,.md";
const ENGINE_LABELS = {
  auto: "자동 (권장) — 로컬 AI로 바로 받아 적고, 불확실한 구간만 POSTECH 서버가 보정",
  server: "POSTECH 서버로 모두 받아 적기 (Gemini 3.8 Flash)",
  local: "로컬 AI만 (크레딧을 쓰지 않음)",
};
const RESERVES = [[0, "끄기"], [10, "10% 남기기"], [20, "20% 남기기"], [30, "30% 남기기 (기본)"], [50, "50% 남기기"]];
const LOW_CONF = 0.8;  // stt.CONF_THRESHOLD와 같은 값

function fmtClock(sec) {
  sec = Math.max(0, Math.floor(sec || 0));
  const hh = Math.floor(sec / 3600), mm = Math.floor((sec % 3600) / 60), ss = sec % 60;
  const two = (n) => String(n).padStart(2, "0");
  return hh ? `${hh}:${two(mm)}:${two(ss)}` : `${two(mm)}:${two(ss)}`;
}

function fmtDate(ts) {
  const d = new Date(ts * 1000);
  return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

const recording = () => (PO.state && PO.state.recording) || null;
const isRecordingNote = (id) => !!recording() && recording().note_id === id;

/* ---------- 화면 전환 ---------- */
async function poOpen() {
  if (window.codeLeave) codeLeave();  // 코드도 하나의 화면(탭은 그대로)
  if (window.pageLeave) pageLeave();
  PO.open = true;
  for (const sel of ["#scroll", "#composer-wrap", "#thread-model-picker", "#agent-label"]) $(sel).hidden = true;
  $("#po-view").hidden = false;
  $("#chat-title").textContent = "PO노트";
  $("#btn-po").classList.add("active");
  if (window.renderBrowserBar) renderBrowserBar();
  document.querySelectorAll(".thread.active").forEach((t) => t.classList.remove("active"));
  setCollapsed(true);
  await poRefresh();
  if (PO.note) await poLoadNote(PO.note.id);
  renderPo();
}

function poLeave() {
  if (!PO.open) return;
  poFlushMemo();
  PO.open = false;
  $("#po-view").hidden = true;
  $("#scroll").hidden = false;
  $("#composer-wrap").hidden = false;
  $("#agent-label").hidden = false;
  $("#btn-po").classList.remove("active");
  if (window.renderBrowserBar) renderBrowserBar();
  if (S.thread) $("#chat-title").textContent = S.thread.title;
  renderThreadModel();
}

async function poRefresh() {
  const [state, list] = await Promise.all([api().po_state(), api().po_list()]);
  PO.state = state;
  PO.list = list;
  if (state.credit) S.credit = state.credit;
  renderRecDot();
}

async function poLoadNote(id) {
  const res = await api().po_load(id);
  if (res.ok === false) {
    toast(res.error);
    PO.note = null;
    return;
  }
  PO.note = res.result;
  PO.editing = false;
  if (!(PO.state && PO.state.generating === id)) PO.streaming = "";
}

function renderRecDot() {
  const rec = recording();
  $("#po-rec-dot").hidden = !rec;
  $("#btn-po").title = rec ? "녹음 중입니다. 눌러서 PO노트로 가기" : "강의를 녹음해 받아 적고, 강의 자료와 함께 필기 노트를 만듭니다";
}

function renderPo() {
  if (!PO.open) return;
  const view = $("#po-view");
  view.replaceChildren(PO.note ? renderDetail() : renderList());
}

/* ---------- 노트 목록 ---------- */
function renderList() {
  const st = PO.state || {};
  const rec = recording();
  const cards = PO.list.map((n) => h("div", { class: "po-card po-item", onclick: () => openNote(n.id) },
    h("div", { class: "po-item-main" },
      h("b", {}, n.title),
      h("small", {}, [fmtDate(n.created), n.duration ? `녹음 ${fmtClock(n.duration)}` : "녹음 없음",
        n.materials ? `자료 ${n.materials}개` : null, n.has_note ? "노트 ✓" : null].filter(Boolean).join(" · "))),
    isRecordingNote(n.id) ? h("span", { class: "badge po-live" }, "녹음 중") : null,
    h("button", { class: "icon-btn", title: "삭제", html: ICONS.trash, onclick: (e) => { e.stopPropagation(); deleteNote(n); } })));
  return h("div", { class: "po-wrap" },
    h("div", { class: "po-intro" },
      h("div", {},
        h("h1", {}, "PO노트"),
        h("p", {}, "강의를 녹음하면 실시간으로 받아 적고, 강의 자료(PPT·PDF 등)와 함께 복습용 필기 노트를 만듭니다.")),
      h("div", { class: "row" },
        h("button", { class: "btn", onclick: showPoSettings }, "음성 인식 설정"),
        h("button", { class: "btn primary", onclick: createNote }, "새 강의 노트"))),
    st.available === false ? h("div", { class: "po-card po-warn" }, st.reason, " 노트를 보고 만드는 기능은 쓸 수 있습니다.") : null,
    rec ? h("div", { class: "po-card po-warn", onclick: () => openNote(rec.note_id), style: "cursor:pointer" },
      "● 녹음 중인 강의가 있습니다. 눌러서 열기") : null,
    h("div", { class: "po-credit" }, creditLine()),
    cards.length ? h("div", { class: "po-list" }, cards)
      : h("p", { class: "po-empty" }, "아직 강의 노트가 없습니다. '새 강의 노트'를 눌러 시작하세요."));
}

async function createNote() {
  const res = await api().po_create(null);
  if (res.ok === false) return toast(res.error);
  PO.note = res.result;
  PO.tab = "transcript";
  await poRefresh();
  renderPo();
  setTimeout(() => $("#po-title")?.select(), 50);
}

async function openNote(id) {
  await poLoadNote(id);
  if (PO.note && !PO.note.transcript.length && PO.note.note) PO.tab = "note";
  renderPo();
}

async function deleteNote(n) {
  if (!confirm(`'${n.title}' 노트를 지울까요? 전사·노트·강의 자료가 모두 지워집니다.`)) return;
  const res = await api().po_delete(n.id);
  if (res.ok === false) return toast(res.error);
  if (PO.note && PO.note.id === n.id) PO.note = null;
  await poRefresh();
  renderPo();
}

/* ---------- 노트 화면 ---------- */
function renderDetail() {
  const note = PO.note;
  const st = PO.state || {};
  const title = h("input", { id: "po-title", class: "po-title", value: note.title, "aria-label": "강의 제목" });
  const saveTitle = async () => {
    const t = title.value.trim();
    if (!t || t === note.title) return (title.value = note.title);
    const res = await api().po_rename(note.id, t);
    if (res.ok === false) return toast(res.error);
    note.title = t;
  };
  title.addEventListener("blur", saveTitle);
  title.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) title.blur(); });
  const head = h("div", { class: "po-head" },
    h("button", { class: "icon-btn", title: "목록으로", html: ICONS.back, onclick: async () => { poFlushMemo(); PO.note = null; await poRefresh(); renderPo(); } }),
    title,
    h("button", { class: "btn", title: "노트·전사 파일이 있는 폴더를 엽니다", onclick: () => api().po_open_folder(note.id) }, "폴더 열기"),
    h("button", { class: "icon-btn", title: "노트 삭제", html: ICONS.trash, onclick: () => deleteNote(note) }));
  return h("div", { class: "po-wrap" }, head, recorderCard(st), materialsCard(), generateBar(), tabs(), pane(),
    h("div", { class: "po-credit" }, creditLine(false)));
}

function recorderCard(st) {
  const note = PO.note;
  const rec = recording();
  const mine = isRecordingNote(note.id);
  const other = rec && !mine;
  if (st.available === false) {
    return h("div", { class: "po-card po-rec" },
      h("span", { class: "po-rec-note" }, st.reason, " 녹음은 Windows·macOS 앱에서 할 수 있습니다."));
  }
  const btn = h("button", { class: "po-rec-btn" + (mine ? " on" : ""), disabled: other || (mine && rec.stopping),
    onclick: () => (mine ? stopRecording() : startRecording()) },
    h("span", { class: "po-rec-icon" }), mine ? (rec.stopping ? "마무리 중…" : "녹음 정지") : (note.duration ? "이어서 녹음" : "녹음 시작"));
  const elapsed = mine ? PO.live.elapsed || note.duration : note.duration;
  const engine = mine ? recEngineLabel(rec) : (ENGINE_LABELS[st.engine] || "");
  return h("div", { class: "po-card po-rec" },
    btn,
    h("span", { class: "po-clock", id: "po-clock" }, fmtClock(elapsed)),
    h("div", { class: "po-meter", title: "마이크 입력" }, h("i", { id: "po-meter", style: `width:${mine ? Math.round(PO.live.level * 100) : 0}%` })),
    h("span", { class: "po-rec-note", id: "po-rec-note" },
      other ? "다른 강의를 녹음하고 있습니다." : mine ? (PO.live.speaking ? "🗣 말하는 중 · " : "듣는 중 · ") + engine : engine),
    h("button", { class: "btn", onclick: showPoSettings, disabled: mine }, "음성 인식 설정"));
}

/* 녹음 중 엔진 표시. 예산 보호로 서버 보정을 멈췄으면 그렇다고 함께 보인다(2.1.1) */
function recEngineLabel(rec) {
  return rec.engine + (rec.budget_paused ? " · 서버 보정 멈춤(크레딧 예산 보호, 2분마다 다시 확인)" : "");
}

async function startRecording() {
  const note = PO.note;
  const status = $("#po-rec-note");
  if (status) status.textContent = "준비 중…";
  const res = await api().po_start(note.id);
  if (res.ok === false) {
    toast(res.error);
    renderPo();
    return;
  }
  PO.state = res.state;
  PO.live = { level: 0, speaking: false, elapsed: note.duration || 0 };
  PO.tab = "transcript";
  renderRecDot();
  renderPo();
  toast(res.notice || `녹음을 시작했습니다 · ${res.engine}`);
}

async function stopRecording() {
  await api().po_stop();
  if (PO.state && PO.state.recording) PO.state.recording.stopping = true;
  renderPo();
}

function materialsCard() {
  const note = PO.note;
  const picker = h("input", { type: "file", multiple: true, hidden: true, accept: MATERIAL_ACCEPT });
  picker.addEventListener("change", () => { uploadMaterials(picker.files); picker.value = ""; });
  const chips = (note.materials || []).map((m) => h("div", { class: "file-chip po-material", title: `${m.name} · ${fmtSize(m.size)} · ${m.chars.toLocaleString()}자` },
    h("div", { class: "f-icon", html: ICONS.file }),
    h("button", { class: "f-text po-link", onclick: () => api().po_open_material(note.id, m.id) },
      h("span", { class: "f-name" }, m.name), h("small", {}, `${m.chars.toLocaleString()}자 읽음`)),
    h("button", { class: "t-remove", title: "빼기", html: ICONS.close, onclick: () => removeMaterial(m) })));
  const uploading = (PO.uploading || []).map((u) => h("div", { class: "file-chip po-material uploading" },
    h("div", { class: "f-icon", html: ICONS.file }),
    h("div", { class: "f-text" }, h("span", { class: "f-name" }, u.name), h("small", {}, `올리는 중 ${Math.round(u.progress * 100)}%`))));
  return h("div", { class: "po-card po-materials" },
    h("div", { class: "po-label" }, "강의 자료",
      h("small", {}, "PPT·PDF·Word·한글 등. 노트를 만들 때 자료의 순서와 내용을 뼈대로 씁니다.")),
    h("div", { class: "po-chips" }, chips, uploading,
      h("button", { class: "chip", onclick: () => picker.click(), html: ICONS.plus + "<span>자료 추가</span>" }), picker));
}

async function uploadMaterials(fileList) {
  const note = PO.note;
  PO.uploading = PO.uploading || [];
  for (const file of Array.from(fileList || [])) {
    const entry = { name: file.name, progress: 0 };
    PO.uploading.push(entry);
    renderPo();
    try {
      const id = newAttachId();
      const CHUNK = 512 * 1024;
      for (let offset = 0; ;) {
        const blob = file.slice(offset, offset + CHUNK);
        const last = offset + blob.size >= file.size;
        const res = await api().po_upload_material(note.id, id, file.name, offset, await readBase64(blob), last);
        if (res.ok === false) throw new Error(res.error);
        offset += blob.size;
        entry.progress = file.size ? offset / file.size : 1;
        if (last) break;
        renderPo();
      }
    } catch (e) {
      toast(e.message || String(e));
    } finally {
      PO.uploading = PO.uploading.filter((u) => u !== entry);
    }
  }
  if (PO.note && PO.note.id === note.id) await poLoadNote(note.id);
  renderPo();
}

async function removeMaterial(m) {
  const res = await api().po_remove_material(PO.note.id, m.id);
  if (res.ok === false) return toast(res.error);
  PO.note.materials = res.result.materials;
  renderPo();
}

function generateBar() {
  const note = PO.note;
  const busy = PO.state && PO.state.generating;
  const mine = busy === note.id;
  const mode = S.config.api_mode || "chat_completions";
  const models = modeModels();
  const select = mode === "a1" ? null : h("select", { class: "po-model", title: "노트를 만들 모델" },
    models.map((m) => h("option", { value: m.id }, m.label)));
  if (select) select.value = models.some((m) => m.id === PO.model) ? PO.model : modeDefaultModel();
  select?.addEventListener("change", () => { PO.model = select.value; });
  const has = note.transcript.length || (note.materials || []).length;
  return h("div", { class: "po-gen" },
    select,
    h("button", { class: "btn primary", disabled: !!busy || !has,
      title: has ? "" : "녹음한 전사나 강의 자료가 있어야 합니다",
      html: ICONS.spark + `<span>${mine ? "노트 만드는 중…" : note.note ? "노트 다시 만들기" : "노트 만들기"}</span>`,
      onclick: generateNote }),
    h("span", { class: "po-gen-status", id: "po-gen-status" }, mine ? PO.genStatus : busy ? "다른 노트를 만들고 있습니다." : ""));
}

async function generateNote() {
  const note = PO.note;
  if (note.note && !confirm("지금 노트를 새로 만든 노트로 바꿀까요? 직접 고친 내용도 바뀝니다.")) return;
  poFlushMemo();
  const res = await api().po_generate(note.id, PO.model || null);
  if (res.ok === false) return toast(res.error);
  PO.state.generating = note.id;
  PO.streaming = "";
  PO.genStatus = "준비 중…";
  PO.tab = "note";
  PO.editing = false;
  renderPo();
}

const TABS = [["note", "노트"], ["transcript", "전사"], ["memo", "메모"], ["materials", "자료 내용"]];

function tabs() {
  const note = PO.note;
  const count = { transcript: note.transcript.length, materials: (note.materials || []).length };
  return h("div", { class: "po-tabs", role: "tablist" }, TABS.map(([key, label]) =>
    h("button", { class: "po-tab" + (PO.tab === key ? " active" : ""), role: "tab",
      onclick: () => { poFlushMemo(); PO.tab = key; PO.editing = false; renderPo(); } },
      label, count[key] ? h("small", { id: key === "transcript" ? "po-count" : null }, ` ${count[key]}`) : null)));
}

function pane() {
  return h("div", { class: "po-pane", id: "po-pane" },
    { note: notePane, transcript: transcriptPane, memo: memoPane, materials: materialPane }[PO.tab]());
}

function notePane() {
  const note = PO.note;
  const generating = PO.state && PO.state.generating === note.id;
  if (generating) {
    return h("div", { id: "po-note-live" }, PO.streaming ? renderMarkdown(PO.streaming)
      : h("p", { class: "po-empty" }, h("span", { class: "dots" }, h("i"), h("i"), h("i")), PO.genStatus || "노트를 만드는 중입니다…"));
  }
  if (PO.editing) {
    const area = h("textarea", { class: "note-editor po-editor", spellcheck: "false" });
    area.value = note.note;
    setTimeout(() => area.focus(), 30);
    return h("div", {}, area, h("div", { class: "row po-actions" },
      h("button", { class: "btn", onclick: () => { PO.editing = false; renderPo(); } }, "취소"),
      h("button", { class: "btn primary", onclick: async () => {
        const res = await api().po_save_note(note.id, area.value);
        if (res.ok === false) return toast(res.error);
        note.note = area.value;
        PO.editing = false;
        renderPo();
        toast("노트를 저장했습니다");
      } }, "저장")));
  }
  if (!note.note) {
    return h("p", { class: "po-empty" }, "아직 노트가 없습니다. 녹음하거나 강의 자료를 올린 뒤 '노트 만들기'를 누르세요. ",
      h("button", { class: "btn", onclick: () => { PO.editing = true; renderPo(); } }, "직접 쓰기"));
  }
  return h("div", {},
    h("div", { class: "row po-actions" },
      h("button", { class: "btn", onclick: () => copyText(note.note), html: ICONS.copy + "<span>복사</span>" }),
      h("button", { class: "btn", onclick: () => { PO.editing = true; renderPo(); }, html: ICONS.pencil + "<span>고치기</span>" })),
    renderMarkdown(note.note));
}

function segmentRow(seg) {
  // 로컬 AI가 확신하지 못한 구간은 흐리게 보인다. 하이브리드 방식이면 서버가 곧 고친다.
  const low = seg.src !== "server" && seg.conf != null && seg.conf < LOW_CONF;
  return h("div", { class: "po-seg" + (low ? " low" : ""), "data-id": seg.id ?? null,
    title: seg.src === "server" ? "POSTECH 서버가 받아 적거나 고친 구간" : low ? `로컬 AI 신뢰도 ${Math.round(seg.conf * 100)}%` : null },
  h("span", { class: "po-seg-time" }, fmtClock(seg.start)), h("span", {}, seg.text));
}

function transcriptPane() {
  const note = PO.note;
  const mine = isRecordingNote(note.id);
  if (!note.transcript.length) {
    return h("p", { class: "po-empty", id: "po-transcript" },
      mine ? "듣는 중입니다. 말이 끝날 때마다 여기에 받아 적습니다." : "아직 전사가 없습니다. '녹음 시작'을 누르세요.");
  }
  return h("div", {},
    h("div", { class: "row po-actions" },
      h("button", { class: "btn", html: ICONS.copy + "<span>복사</span>",
        onclick: () => copyText(note.transcript.map((s) => `[${fmtClock(s.start)}] ${s.text}`).join("\n")) })),
    h("div", { class: "po-transcript", id: "po-transcript" }, note.transcript.map(segmentRow)));
}

function memoPane() {
  const note = PO.note;
  const area = h("textarea", { class: "note-editor po-editor", id: "po-memo", spellcheck: "false",
    placeholder: "강의 중 떠오른 질문, 칠판 필기, 꼭 기억할 것을 적어 두세요. 노트를 만들 때 함께 반영합니다." });
  area.value = note.memo || "";
  area.addEventListener("input", () => {
    note.memo = area.value;
    clearTimeout(PO.memoTimer);
    PO.memoTimer = setTimeout(poFlushMemo, 700);
  });
  return area;
}

function poFlushMemo() {
  if (!PO.memoTimer || !PO.note) return;
  clearTimeout(PO.memoTimer);
  PO.memoTimer = 0;
  api().po_save_memo(PO.note.id, PO.note.memo || "");
}

function materialPane() {
  const note = PO.note;
  if (!(note.materials || []).length) return h("p", { class: "po-empty" }, "올린 강의 자료가 없습니다.");
  return h("div", {}, note.materials.map((m) => {
    const box = h("pre", { class: "po-material-text" }, "불러오는 중…");
    const d = h("details", {}, h("summary", {}, m.name, h("small", {}, ` · ${m.chars.toLocaleString()}자`)), box);
    d.addEventListener("toggle", async () => {
      if (!d.open || box.dataset.loaded) return;
      const res = await api().po_material_text(note.id, m.id);
      box.textContent = res.ok === false ? res.error : res.result;
      box.dataset.loaded = "1";
    });
    return d;
  }));
}

/* ---------- 음성 인식 설정 ---------- */
async function showPoSettings() {
  const st = await api().po_state();
  PO.state = st;
  if (!st.available) return toast(st.reason);
  const engine = h("select", {}, Object.entries(ENGINE_LABELS).map(([v, l]) => h("option", { value: v }, l)));
  engine.value = st.engine;
  const language = h("select", {}, Object.entries(st.languages).map(([v, l]) => h("option", { value: v }, l)));
  language.value = st.language;
  const device = h("select", {}, h("option", { value: "" }, "시스템 기본 마이크"));
  api().po_devices().then((list) => {
    device.append(...list.map((d) => h("option", { value: String(d.index) }, d.name)));
    device.value = st.device === "" ? "" : String(st.device);
  });
  const model = h("select", {}, st.models.map((m) => h("option", { value: m.key }, m.label)));
  model.value = st.model;
  const models = h("div", {});
  const renderModels = () => {
    const dl = PO.state.download;
    models.replaceChildren(...PO.state.models.map((m) => h("div", { class: "skill-item" },
      h("div", { class: "s-main" },
        h("b", { style: "font-family:inherit" }, m.label), h("span", { class: "badge" + (m.installed ? " mcp-connected" : "") },
          m.installed ? "내려받음" : `${m.size_mb}MB`),
        h("p", {}, m.desc),
        dl && dl.key === m.key ? h("div", { class: "po-meter po-progress" },
          h("i", { style: `width:${dl.total ? Math.round(dl.done / dl.total * 100) : 0}%` })) : null),
      dl && dl.key === m.key
        ? h("button", { class: "btn", onclick: () => api().po_cancel_download() }, "취소")
        : m.installed
          ? h("button", { class: "btn danger", onclick: async () => {
            const res = await api().po_delete_model(m.key);
            if (res.ok === false) return toast(res.error);
            PO.state = res.state;
            renderModels();
          } }, "지우기")
          : h("button", { class: "btn", disabled: !!dl, onclick: async () => {
            const res = await api().po_download_model(m.key);
            if (res.ok === false) return toast(res.error);
            PO.state.download = { key: m.key, done: 0, total: 0 };
            renderModels();
          } }, "내려받기"))));
  };
  PO.renderModels = renderModels;
  renderModels();
  const reserve = h("select", {}, RESERVES.map(([v, l]) => h("option", { value: String(v) }, l)));
  reserve.value = String(st.reserve);
  const costHint = h("small", {},
    "자동: 로컬 AI가 바로 받아 적고, 약 2분치 구간 가운데 로컬 AI가 확신하지 못한 구간(잡음·전문 용어 등)이 있을 때만 ",
    "POSTECH 서버(Gemini 3.8 Flash)가 음성과 대조해 고칩니다. 1시간에 0~약 420크레딧이고, 서버가 실패해도 로컬 글은 남습니다. ",
    "로컬 AI 모델이 없으면 첫 녹음은 서버로 받아 적으면서 모델을 내려받습니다. ",
    "서버로 모두 받아 적기: 말 구간을 약 25초씩 모아 보내 1시간에 약 1,000~1,300크레딧(주간 한도의 약 7~9%)이 듭니다. ",
    "로컬 AI만: 크레딧·인터넷 없이 이 PC의 CPU 2코어만 씁니다.");
  const body = h("div", {},
    h("div", { class: "field" }, h("label", {}, "받아 적는 방식"), engine, costHint),
    h("div", { class: "field" }, h("label", {}, "크레딧 예산 보호"), reserve,
      h("small", {}, "이번 주 남은 크레딧이 한도의 이 비율 아래로 내려가면 서버를 쓰지 않고 로컬 AI로만 받아 적습니다. ",
        "채팅과 노트 만들기에 쓸 크레딧을 남겨 둡니다.")),
    h("div", { class: "field" }, h("label", {}, "강의 언어"), language,
      h("small", {}, "한국어 강의는 '한국어'가 가장 정확합니다. 영어 강의는 '영어'(로컬 AI는 다국어 모델이 필요), 섞여 있으면 '자동 감지'.")),
    h("div", { class: "field" }, h("label", {}, "마이크"), device),
    h("div", { class: "field" }, h("label", {}, "로컬 AI 모델"), model,
      h("small", {}, "로컬 AI로 받아 적을 때(자동 방식에서 서버가 실패했을 때 포함) 쓰는 모델입니다. 아래에서 내려받으세요."), models),
    h("div", { class: "field" }, h("label", {}, "POSTECH GenAI 크레딧"), creditLine()));
  modal({
    title: "음성 인식 설정",
    body,
    wide: true,
    onClose: () => { PO.renderModels = null; },
    buttons: [
      { label: "취소", value: null },
      { label: "저장", class: "primary", action: async (close) => {
        if (engine.value === "local" && !PO.state.models.find((m) => m.key === model.value)?.installed) {
          return toast("로컬 AI를 쓰려면 고른 모델을 먼저 내려받으세요.");
        }
        PO.state = await api().po_save_settings({ engine: engine.value, language: language.value, model: model.value,
          device: device.value === "" ? "" : Number(device.value), reserve: Number(reserve.value) });
        close();
        renderPo();
        toast("음성 인식 설정을 저장했습니다");
      } },
    ],
  });
}

/* ---------- 백엔드 이벤트 ---------- */
function poEvent(ev) {
  const note = PO.note;
  const here = note && ev.note_id === note.id;
  switch (ev.kind) {
    case "level": {
      PO.live = { level: ev.level, speaking: ev.speaking, elapsed: ev.elapsed };
      if (!PO.open || !here) break;
      const meter = $("#po-meter");
      if (meter) meter.style.width = `${Math.round(ev.level * 100)}%`;
      const clock = $("#po-clock");
      if (clock) clock.textContent = fmtClock(ev.elapsed);
      const status = $("#po-rec-note");
      if (status && recording()) status.textContent = (ev.speaking ? "🗣 말하는 중 · " : "듣는 중 · ") + recEngineLabel(recording());
      break;
    }
    case "segment": {
      if (!here) break;
      note.transcript.push(ev.segment);
      if (!PO.open || PO.tab !== "transcript") {
        const count = $("#po-count");
        if (count) count.textContent = ` ${note.transcript.length}`;
        if (PO.open && !count) renderPo();
        break;
      }
      const list = $("#po-transcript.po-transcript");
      if (!list) { renderPo(); break; }
      const pane = $("#po-view");
      const atBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 80;
      list.append(segmentRow(ev.segment));
      const count = $("#po-count");
      if (count) count.textContent = ` ${note.transcript.length}`;
      if (atBottom) pane.scrollTop = pane.scrollHeight;
      break;
    }
    case "transcript": {
      if (!here) break;
      note.transcript = ev.transcript;
      if (!PO.open || PO.tab !== "transcript") break;
      const pane = $("#po-view");
      const top = pane.scrollTop, atBottom = pane.scrollHeight - pane.scrollTop - pane.clientHeight < 80;
      renderPo();
      pane.scrollTop = atBottom ? pane.scrollHeight : top;
      break;
    }
    case "budget": {
      // 2.1.1: 크레딧 예산 보호로 서버 보정을 멈추거나 다시 시작했다(녹음 중 표시에 남긴다)
      const rec = recording();
      if (rec && rec.note_id === ev.note_id) rec.budget_paused = !!ev.paused;
      if (!ev.paused) toast("크레딧 예산이 돌아와 서버 보정을 다시 시작합니다.");
      if (PO.open && here) renderPo();
      break;
    }
    case "status":
      if (here) toast(ev.text);
      break;
    case "error":
      toast(ev.error);
      break;
    case "stopping":
      if (PO.state && PO.state.recording) PO.state.recording.stopping = true;
      renderPo();
      break;
    case "stopped":
      api().po_state().then(async (st) => {
        PO.state = st;
        renderRecDot();
        if (PO.open && PO.note && PO.note.id === ev.note_id) await poLoadNote(ev.note_id);
        if (PO.open) {
          if (!PO.note) PO.list = await api().po_list();
          renderPo();
        }
        toast("녹음을 마쳤습니다. '노트 만들기'로 필기 노트를 만들 수 있습니다.");
      });
      break;
    case "download":
      if (PO.state) PO.state.download = { key: ev.key, done: ev.done, total: ev.total };
      if (PO.renderModels) PO.renderModels();
      break;
    case "download_done":
      PO.state = ev.state;
      if (PO.renderModels) PO.renderModels();
      toast("음성 인식 모델을 내려받았습니다");
      break;
    case "download_error":
      if (PO.state) PO.state.download = null;
      if (PO.renderModels) PO.renderModels();
      toast(ev.error);
      break;
    case "note_status":
      if (here) {
        PO.genStatus = ev.text;
        const el = $("#po-gen-status");
        if (el) el.textContent = ev.text;
        if (!PO.streaming && PO.tab === "note") renderPo();
      }
      break;
    case "note_delta":
      if (!here) break;
      PO.streaming = ev.text;
      if (PO.open && PO.tab === "note") {
        if (PO.frame) break;
        PO.frame = requestAnimationFrame(() => {
          PO.frame = 0;
          const live = $("#po-note-live");
          if (live) live.replaceChildren(renderMarkdown(PO.streaming));
          else renderPo();
        });
      }
      break;
    case "note_done":
    case "note_error":
      if (PO.state) PO.state.generating = null;
      PO.streaming = "";
      PO.genStatus = "";
      if (ev.kind === "note_error") toast(`노트를 만들지 못했습니다: ${ev.error}`);
      else toast("필기 노트를 만들었습니다");
      if (here) {
        if (ev.kind === "note_done") note.note = ev.note;
        renderPo();
      }
      break;
  }
}

$("#btn-po").addEventListener("click", () => {
  if (PO.open && PO.note && !recording()) {
    poFlushMemo();
    PO.note = null;
    poRefresh().then(renderPo);
  } else if (!PO.open) {
    const rec = recording();
    if (rec && (!PO.note || PO.note.id !== rec.note_id)) PO.note = { id: rec.note_id };
    poOpen();
  }
});
