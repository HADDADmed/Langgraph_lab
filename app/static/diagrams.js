// Hand-drawn architecture diagrams (rough.js + Caveat). Drawn as SVG in the browser.
(function () {
  const INK = "#1f2328", MUTED = "#6b6b6b", NS = "http://www.w3.org/2000/svg";
  const C = { yellow: "#ffe8a3", blue: "#c7e9ff", green: "#d9f7be", pink: "#ffd6e7", orange: "#ffe7ba",
              violet: "#e8e1ff", grey: "#eeeeee", cream: "#fff1b8" };

  function Sketch(svg, seed = 7) {
    svg.innerHTML = "";
    const rc = rough.svg(svg, { options: { seed, roughness: 1.15, bowing: 1.1, stroke: INK, strokeWidth: 1.5 } });
    const add = n => (svg.appendChild(n), n);
    const text = (x, y, s, o = {}) => {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", x); t.setAttribute("y", y);
      t.setAttribute("text-anchor", o.anchor || "middle");
      t.setAttribute("font-family", "Caveat, cursive");
      t.setAttribute("font-size", o.size || 22); t.setAttribute("font-weight", o.weight || 700);
      t.setAttribute("fill", o.color || INK);
      t.textContent = s; return add(t);
    };
    const box = (x, y, w, h, title, sub = [], fill = C.grey, o = {}) => {
      add(rc.rectangle(x, y, w, h, { fill, fillStyle: "hachure", hachureGap: 7, fillWeight: 1.1, hachureAngle: -41,
                                     strokeWidth: o.strong ? 2.2 : 1.6, strokeLineDash: o.dashed ? [8, 6] : undefined }));
      const lines = (Array.isArray(sub) ? sub : [sub]).filter(Boolean);
      const top = y + h / 2 - (lines.length * 9) + 4;
      text(x + w / 2, top, title, { size: o.size || 25 });
      lines.forEach((l, i) => text(x + w / 2, top + 22 + i * 19, l, { size: 18, weight: 500, color: "#3a3a3a" }));
    };
    const pill = (cx, cy, w, h, label, fill = INK) => {
      add(rc.ellipse(cx, cy, w, h, { fill, fillStyle: "solid", strokeWidth: 1.6 }));
      text(cx, cy + 7, label, { size: 21, color: fill === INK ? "#fff" : INK });
    };
    const head = (p, q) => {
      const a = Math.atan2(q[1] - p[1], q[0] - p[0]), L = 13, s = 0.45;
      add(rc.linearPath([[q[0] - L * Math.cos(a - s), q[1] - L * Math.sin(a - s)], q,
                         [q[0] - L * Math.cos(a + s), q[1] - L * Math.sin(a + s)]], { strokeWidth: 1.6, roughness: 0.6 }));
    };
    const arrow = (pts, o = {}) => {
      const opt = { strokeWidth: o.w || 1.5, strokeLineDash: o.dashed ? [7, 6] : undefined, stroke: o.color || INK };
      add(pts.length > 2 && o.curve !== false ? rc.curve(pts, opt) : rc.linearPath(pts, opt));
      if (!o.noHead) head(pts[pts.length - 2], pts[pts.length - 1]);
      if (o.both) head(pts[1], pts[0]);
      if (o.label) text(o.lx ?? (pts[0][0] + pts[pts.length - 1][0]) / 2, o.ly ?? (pts[0][1] + pts[pts.length - 1][1]) / 2 - 8,
                        o.label, { size: o.size || 19, weight: 500, color: o.lcolor || "#2b2b2b", anchor: o.anchor });
    };
    const badge = (x, y, n) => {
      add(rc.circle(x, y, 24, { fill: "#4338ca", fillStyle: "solid", stroke: "#4338ca", roughness: 0.8 }));
      text(x, y + 6, n, { size: 17, color: "#fff" });
    };
    return { rc, add, text, box, pill, arrow, badge };
  }

  function system() {
    const s = Sketch(document.getElementById("d-system"), 3);
    s.add(s.rc.rectangle(12, 10, 1076, 450, { strokeLineDash: [10, 8], stroke: "#9a9a9a", strokeWidth: 1.2, roughness: 1.6 }));
    s.text(30, 448, "one machine · nothing leaves it", { anchor: "start", size: 20, color: MUTED, weight: 500 });
    s.box(30, 180, 190, 100, "Browser UI", ["chat · inspector", "docs · eval"], C.violet);
    s.box(290, 180, 190, 100, "FastAPI", ["REST + SSE", "uvicorn (async)"], C.green);
    s.box(550, 160, 230, 140, "LangGraph", ["StateGraph · 5 agents", "ToolNode · RetryPolicy", "trim_messages"], C.yellow, { strong: true, size: 28 });
    s.box(565, 22, 200, 78, "Local tools", "calculator · datetime", C.pink);
    s.box(850, 30, 220, 95, "Ollama · qwen3:8b", ["local GPU", "tool calls · JSON schema"], C.blue);
    s.box(850, 185, 220, 95, "SQLite checkpointer", ["AsyncSqliteSaver", "memory per thread_id"], C.orange);
    s.box(850, 340, 220, 95, "MCP campus server", ["FastMCP · stdio", "3 tools"], C.green);
    s.box(565, 362, 200, 78, "campus.db", "courses · calendar", C.grey);
    s.arrow([[220, 212], [290, 212]], { label: "POST /api/chat", ly: 168, size: 18 });
    s.arrow([[290, 250], [220, 250]], { label: "SSE events", ly: 300, size: 18 });
    s.arrow([[480, 230], [550, 230]], { label: "astream()", ly: 216, size: 17 });
    s.arrow([[665, 160], [665, 100]], { both: true, label: "@tool", lx: 655, ly: 136, anchor: "end" });
    s.arrow([[780, 185], [815, 120], [850, 90]], { both: true, label: "prompt ⇄ tool calls", lx: 862, ly: 157, anchor: "start" });
    s.arrow([[780, 232], [850, 232]], { both: true, label: "checkpoint", ly: 222, size: 17 });
    s.arrow([[780, 280], [815, 340], [850, 380]], { both: true, label: "MCP tools/call", lx: 862, ly: 318, anchor: "start" });
    s.arrow([[850, 405], [765, 405]], { label: "SQL", ly: 396 });
  }

  function graph() {
    const s = Sketch(document.getElementById("d-graph"), 11);
    s.pill(62, 262, 96, 46, "START");
    s.box(132, 222, 170, 80, "classifier", ["Pydantic Route", "enum · confidence"], C.yellow, { strong: true });
    s.arrow([[110, 262], [132, 262]]);
    const agents = [
      ["courses_agent", "course_lookup · calendar", C.blue, 30], ["programming_agent", "no tools", C.green, 115],
      ["mathematics_agent", "calculator", C.pink, 200], ["administration_agent", "procedure · calendar · date", C.orange, 285],
      ["general_agent", "date · calc · courses", C.violet, 370]];
    agents.forEach(([n, sub, fill, y]) => {
      s.box(400, y, 210, 62, n, sub, fill, { size: 22 });
      s.arrow([[302, 262], [350, (262 + y + 31) / 2], [400, y + 31]], { dashed: true });
      s.arrow([[610, y + 31], [662, y + 31]], { noHead: true });
    });
    s.text(217, 208, "category?", { size: 19, weight: 500, color: MUTED });
    s.box(400, 452, 210, 50, "fallback", "", C.grey, { size: 22 });
    s.arrow([[260, 302], [300, 470], [400, 477]], { dashed: true, label: "EMPTY / error", lx: 205, ly: 405 });
    s.add(s.rc.line(662, 50, 662, 410, { strokeWidth: 2.4 }));
    s.box(790, 96, 180, 112, "ToolNode", ["shared · handles", "tool errors"], C.cream, { strong: true });
    s.arrow([[662, 152], [790, 152]], { dashed: true, label: "tool_calls?", ly: 140 });
    s.arrow([[880, 96], [860, 30], [720, 26], [664, 52]], { label: "result → same agent", lx: 790, ly: 20 });
    s.text(882, 236, "(state.category)", { size: 18, weight: 500, color: MUTED });
    s.pill(1010, 352, 100, 46, "END");
    s.arrow([[662, 352], [958, 352]], { dashed: true, label: "final answer", ly: 340 });
    s.arrow([[610, 477], [880, 470], [1006, 377]], { label: "message", lx: 905, ly: 440 });
    s.arrow([[760, 470 + 32], [800, 470 + 32]], { noHead: false });
    s.text(810, 509, "edge", { anchor: "start", size: 18, weight: 500, color: MUTED });
    s.arrow([[880, 502], [920, 502]], { dashed: true });
    s.text(930, 509, "conditional edge", { anchor: "start", size: 18, weight: 500, color: MUTED });
  }

  function sequence() {
    const s = Sketch(document.getElementById("d-seq"), 5);
    const lanes = [["Browser", 125, C.violet], ["FastAPI", 300, C.green], ["LangGraph", 485, C.yellow],
                   ["qwen3:8b", 675, C.blue], ["Tools / MCP", 855, C.pink], ["SQLite", 1022, C.orange]];
    const X = Object.fromEntries(lanes.map(([n, x]) => [n, x]));
    lanes.forEach(([n, x, f]) => {
      s.box(x - 72, 14, 144, 46, n, "", f, { size: 23 });
      s.add(s.rc.line(x, 62, x, 588, { strokeLineDash: [5, 7], stroke: "#a3a3a3", strokeWidth: 1.1, roughness: 0.5 }));
    });
    const msgs = [
      ["Browser", "FastAPI", "POST /api/chat {message, thread_id}"],
      ["FastAPI", "LangGraph", "astream(messages, updates)"],
      ["LangGraph", "SQLite", "load checkpoint of the thread"],
      ["LangGraph", "qwen3:8b", "classify → JSON {MATHEMATICS, 1.0}"],
      ["LangGraph", "Browser", "SSE: route + node events", true],
      ["LangGraph", "qwen3:8b", "mathematics_agent + [calculator]"],
      ["qwen3:8b", "LangGraph", "tool_call calculator('125*38+17')", true],
      ["LangGraph", "Tools / MCP", "ToolNode executes the call"],
      ["Tools / MCP", "LangGraph", "ToolMessage: 4767", true],
      ["LangGraph", "qwen3:8b", "same agent reads the result"],
      ["LangGraph", "Browser", "SSE: tokens “The result is 4767”", true],
      ["LangGraph", "SQLite", "save checkpoint (each step)"],
      ["FastAPI", "Browser", "SSE: done {path, timings}", true],
    ];
    msgs.forEach(([a, b, label, dashed], i) => {
      const y = 100 + i * 37, x1 = X[a], x2 = X[b], dir = Math.sign(x2 - x1);
      s.arrow([[x1 + dir * 6, y], [x2 - dir * 6, y]], { dashed, label, lx: (x1 + x2) / 2, ly: y - 7, size: 18 });
      s.badge(26, y - 4, String(i + 1));
    });
  }

  let drawn = false;
  window.drawDiagrams = async function () {
    if (drawn) return;
    drawn = true;
    await document.fonts.load("700 22px Caveat");
    await document.fonts.load("500 18px Caveat");
    system(); graph(); sequence();
  };
})();
