// Campus Copilot front-end: chat with SSE streaming, run inspector, docs and evaluation views.
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const CAT_COLOR = { COURSES: "var(--c-courses)", PROGRAMMING: "var(--c-programming)", MATHEMATICS: "var(--c-mathematics)",
  ADMINISTRATION: "var(--c-administration)", GENERAL: "var(--c-general)", EMPTY: "var(--c-empty)" };
const AI_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="#18181b" stroke-width="2" stroke-linecap="round"><circle cx="5" cy="12" r="2.2"/><circle cx="19" cy="5" r="2.2"/><circle cx="19" cy="19" r="2.2"/><path d="M7 11l10-5M7 13l10 5"/></svg>';

marked.use({ renderer: { html: t => esc(t.text ?? t) } });   // never render raw HTML from the model
// small LaTeX clean-up: local models sometimes still answer with $...$ despite the prompt
const deLatex = s => s.replace(/\\times/g, "×").replace(/\\cdot/g, "·").replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "($1)/($2)")
  .replace(/\\left|\\right/g, "").replace(/\$\$?([^$]+)\$\$?/g, "$1");
const md = s => marked.parse(deLatex(s || ""));

// ------------------------------------------------------------------ navigation
document.querySelectorAll(".nav").forEach(b => b.onclick = () => show(b.dataset.view));
function show(v) {
  document.querySelectorAll(".nav").forEach(n => n.classList.toggle("on", n.dataset.view === v));
  document.querySelectorAll(".view").forEach(n => n.classList.toggle("on", n.id === "v-" + v));
  if (v === "arch") window.drawDiagrams && window.drawDiagrams();
  if (v === "eval") loadEval();
  history.replaceState(null, "", "#" + v);
}

// ------------------------------------------------------------------ chat
let tid = localStorage.getItem("thread") || newId();
function newId() { const id = "t-" + Math.random().toString(36).slice(2, 8); localStorage.setItem("thread", id); return id; }
const msgs = $("#msgs");
const SUGG = [
  ["Courses", "Who teaches Deep Learning, and in which room?"],
  ["Mathematics", "What is 125 * 38 + 17?"],
  ["Administration", "How do I request an enrollment certificate?"],
  ["Programming", "Write a Python function that checks if a string is a palindrome."],
  ["Calendar", "When do the semester 1 final exams start?"],
  ["Memory", "My name is Sara and I love computer vision."],
];

function emptyState() {
  msgs.innerHTML = `<div class="empty"><div class="eyebrow">Multi-agent · tools · memory</div><h1>What can I help you with?</h1>
    <p class="muted">Five specialist agents, campus tools over MCP, and memory that survives restarts. Everything runs locally.</p>
    <div class="sugg">${SUGG.map(([k, q]) => `<button data-q="${esc(q)}"><b style="color:${CAT_COLOR[k.toUpperCase()] || "var(--accent)"}">${k}</b>${esc(q)}</button>`).join("")}</div></div>`;
  msgs.querySelectorAll(".sugg button").forEach(b => b.onclick = () => send(b.dataset.q));
}

function addUser(text) {
  $(".empty", msgs)?.remove();
  msgs.insertAdjacentHTML("beforeend", `<div class="m-user">${esc(text)}</div>`);
}
function addAI(html = '<div class="typing"><i></i><i></i><i></i></div>', meta = "") {
  $(".empty", msgs)?.remove();
  const el = document.createElement("div");
  el.className = "m-ai";
  el.innerHTML = `<div class="av">${AI_ICON}</div><div class="body"><div class="meta">${meta}</div><div class="md">${html}</div></div>`;
  msgs.appendChild(el);
  return el;
}
const scroll = () => { const s = $(".msgs"); s.scrollTop = s.scrollHeight; };
const chip = (cat, extra = "") => `<span class="chip" style="color:${CAT_COLOR[cat] || "var(--ink-2)"}"><i></i>${esc(cat)}${extra}</span>`;
const plain = (t) => `<span class="chip">${esc(t)}</span>`;

function resetInspector() {
  $("#route").innerHTML = '<div class="placeholder">Classifying…</div>';
  $("#path").innerHTML = ""; $("#tools").innerHTML = '<div class="placeholder">No tool used.</div>';
}
let toolCount = 0;

async function send(text) {
  text = (text ?? $("#q").value);
  $("#q").value = "";
  addUser(text.trim() ? text : "(empty message)");
  const ai = addAI(); scroll();
  resetInspector(); toolCount = 0;
  let draft = "", cat = "", tools = [];
  const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, thread_id: tid }) });
  const reader = res.body.getReader(), dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i); buf = buf.slice(i + 2);
      if (!line.startsWith("data: ")) continue;
      const ev = JSON.parse(line.slice(6));
      if (ev.type === "route") {
        cat = ev.category;
        const pct = Math.round((ev.confidence ?? 0) * 100);
        $("#route").innerHTML = `<div class="cat">${chip(cat)}<span class="muted" style="font-weight:400;font-size:12.5px;margin-left:auto">${pct}% confidence</span></div>
          <div class="bar"><i style="width:${pct}%;background:${CAT_COLOR[cat]}"></i></div><p>${esc(ev.reason)}</p>`;
        $(".meta", ai).innerHTML = chip(cat);
      } else if (ev.type === "node") {
        $("#path").insertAdjacentHTML("beforeend", `<li><span class="mono">${esc(ev.node)}</span><span class="ms">${ev.ms} ms</span></li>`);
      } else if (ev.type === "tool_call") {
        if (!toolCount++) $("#tools").innerHTML = "";
        tools.push(ev.name); draft = "";
        $(".md", ai).innerHTML = `<div class="muted" style="font-size:13px">Calling <code>${esc(ev.name)}</code>…</div>`;
        $("#tools").insertAdjacentHTML("beforeend", `<div class="card tool"><div class="n">${esc(ev.name)}<span>call</span></div><pre>${esc(JSON.stringify(ev.args))}</pre><div class="res"></div></div>`);
      } else if (ev.type === "tool_result") {
        const boxes = [...document.querySelectorAll("#tools .tool")], box = boxes.reverse().find(b => !$(".res", b).innerHTML);
        if (box) $(".res", box).innerHTML = `<div class="n" style="margin-top:8px">result<span>${esc(ev.status)}</span></div><pre>${esc(ev.content)}</pre>`;
      } else if (ev.type === "token") {
        draft += ev.text; $(".md", ai).innerHTML = md(draft); scroll();
      } else if (ev.type === "done") {
        $(".md", ai).innerHTML = md(ev.answer || draft);
        $(".meta", ai).innerHTML = (cat ? chip(cat) : "") + [...new Set(tools)].map(t => plain("⚙ " + t)).join("") + plain((ev.total_ms / 1000).toFixed(1) + " s");
        $("#path").insertAdjacentHTML("beforeend", `<li class="end"><span class="mono">END</span><span class="ms">${(ev.total_ms / 1000).toFixed(2)} s total</span></li>`);
        refreshMemory().then(() => { window.runsDone = (window.runsDone || 0) + 1; });
      } else if (ev.type === "error") {
        $("#route").insertAdjacentHTML("beforeend", `<p class="bad" style="margin-top:8px">${esc(ev.message)}</p>`);
      }
    }
  }
  scroll();
}

async function refreshMemory() {
  const r = await (await fetch(`/api/threads/${tid}`)).json();
  $("#mem").innerHTML = `<span>thread</span><span class="mono">${esc(tid)}</span><span>messages</span><span>${r.messages.length}</span>
    <span>checkpoints</span><span>${r.checkpoints}</span><span>store</span><span>SQLite (AsyncSqliteSaver)</span>`;
  return r;
}

async function restoreThread() {
  $("#tid").textContent = tid;
  const r = await refreshMemory();
  if (!r.messages.length) return emptyState();
  msgs.innerHTML = "";
  for (const m of r.messages) {
    if (m.role === "user") addUser(m.content);
    else if (m.role === "assistant") $(".md", addAI()).innerHTML = md(m.content);
  }
  scroll();
}

$("#f").onsubmit = e => { e.preventDefault(); send(); };
$("#new-thread").onclick = () => { tid = newId(); $("#tid").textContent = tid; emptyState(); refreshMemory();
  $("#route").innerHTML = '<div class="placeholder">Send a message to see how the classifier routes it.</div>';
  $("#path").innerHTML = ""; $("#tools").innerHTML = '<div class="placeholder">No tool used yet.</div>'; };

// ------------------------------------------------------------------ docs
const TECH = [
  ["LangGraph", "Orchestration", "Defines the assistant as a <b>StateGraph</b>: typed shared state, nodes, conditional edges, a tool loop. It also provides checkpointing, streaming, retries and <code>RetryPolicy</code>.", "app/agent.py · build_graph()"],
  ["LangChain Core", "Abstractions", "Common message types, the <code>@tool</code> decorator, <code>bind_tools</code>, <code>with_structured_output</code> and <code>trim_messages</code>. The same code works with any chat model.", "app/agent.py"],
  ["Ollama + qwen3:8b", "Local LLM", "Runs the 8-billion-parameter Qwen3 model locally on the GPU: no API key, no data leaves the machine. It supports tool calling and JSON-schema output. Thinking mode is off for low latency.", "make_llm()"],
  ["langchain-ollama", "Model adapter", "<code>ChatOllama</code> has the same interface as <code>ChatOpenAI</code>, so switching provider changes one line.", "make_llm()"],
  ["Pydantic structured output", "Reliable routing", "The <code>Route</code> schema (enum category + confidence + reason) becomes a JSON-schema constraint: the classifier can only return a valid label. A free-text fallback is used if the schema fails.", "Route · classifier()"],
  ["Model Context Protocol (MCP)", "Tool interoperability", "The campus tools live in a <b>separate MCP server</b> (FastMCP, stdio). The agent discovers them at start-up with <code>langchain-mcp-adapters</code>, as it would any third-party MCP server.", "app/mcp_server.py · load_mcp_tools()"],
  ["AsyncSqliteSaver", "Durable memory", "LangGraph checkpointer backed by SQLite. Each step of each thread is saved, so conversations survive a server restart and the full history can be replayed (time travel).", "app/server.py · lifespan()"],
  ["FastAPI + SSE", "Serving & streaming", "An async web API. <code>graph.astream(stream_mode=[\"messages\",\"updates\"])</code> is forwarded as Server-Sent Events: tokens, node updates and tool calls appear live.", "app/server.py · /api/chat"],
  ["SQLite", "Campus data", "Course catalogue and academic calendar queried by the MCP tools, so the answers are grounded in data instead of invented.", "app/campus_data.py"],
  ["rough.js + Caveat", "Hand-drawn diagrams", "The architecture diagrams are drawn in the browser as sketchy SVG: the same diagram code always matches the real graph.", "app/static/diagrams.js"],
  ["marked", "Rendering", "Renders the model's Markdown (code blocks, lists, tables). Raw HTML from the model is escaped.", "app/static/app.js"],
  ["Playwright + pytest", "Testing", "Unit tests for the tools and graph, API tests with a real streamed run, and headless-browser screenshots of the UI.", "tests/ · scripts/screenshots.py"],
];
function renderDocs(info) {
  $("#techs").innerHTML = TECH.map(([n, tag, p, w]) => `<div class="card tech"><div class="top"><h3>${n}</h3><span class="tag">${tag}</span></div><p>${p}</p><div class="where mono">${w}</div></div>`).join("");
  if (!info) return;
  $("#tool-table tbody").innerHTML = info.tools.map(t => `<tr><td class="mono">${esc(t.name)}</td><td><span class="chip">${t.source}</span></td>
    <td>${t.agents.map(a => chip(a)).join(" ")}</td><td>${esc(t.description)}</td></tr>`).join("");
}

// ------------------------------------------------------------------ evaluation
function renderEval(d) {
  if (!d.summary) { $("#tiles").innerHTML = '<p class="muted">No report yet. Click “Re-run evaluation”.</p>'; return; }
  const s = d.summary, pct = x => Math.round(x * 100) + "%";
  $("#tiles").innerHTML = [["Routing accuracy", pct(s.routing_accuracy)], ["Correct tool selection", pct(s.tool_accuracy)],
    ["Grounded answers", pct(s.answer_accuracy)], ["Avg. latency", s.avg_seconds + " s"]]
    .map(([l, v]) => `<div class="card tile"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
  const mark = ok => ok === null ? '<span class="muted">—</span>' : ok ? '<span class="pill-ok">✓</span>' : '<span class="pill-bad">✗</span>';
  $("#eval-table tbody").innerHTML = d.rows.map(r => `<tr><td>${esc(r.question)}</td><td>${chip(r.expected)}</td>
    <td>${mark(r.route_ok)} <span class="muted">${esc(r.got)}</span></td><td>${mark(r.tool_ok)} <span class="mono">${esc(r.tools.join(", ") || "—")}</span></td>
    <td>${mark(r.answer_ok)}</td><td class="muted">${r.seconds}s</td></tr>`).join("");
  $("#eval-meta").textContent = `Model ${s.model} · ${s.cases} cases · run ${s.date} · per category: ` +
    Object.entries(s.per_category).map(([k, v]) => `${k} ${v}`).join(" · ");
}
async function loadEval() { renderEval(await (await fetch("/api/eval")).json()); }
$("#run-eval").onclick = async e => {
  e.target.disabled = true; e.target.textContent = "Running… (~20 s)";
  renderEval(await (await fetch("/api/eval/run", { method: "POST" })).json());
  e.target.disabled = false; e.target.textContent = "Re-run evaluation";
};

// ------------------------------------------------------------------ boot
(async () => {
  let info = null;
  try {
    info = await (await fetch("/api/info")).json();
    $("#st-model").classList.add("on"); $("#st-model-t").textContent = info.model + " · Ollama";
    $("#st-mcp").classList.toggle("on", info.mcp); $("#st-mcp-t").textContent = info.mcp ? "MCP campus server" : "MCP offline";
  } catch (e) { $("#st-model-t").textContent = "server offline"; }
  renderDocs(info);
  await restoreThread();
  show((location.hash || "#chat").slice(1));
})();
