"""Campus Copilot web server: FastAPI + Server-Sent Events streaming of a LangGraph run.

    uvicorn app.server:app --port 8000        # then open http://127.0.0.1:8000
"""
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel

from app.agent import AGENT_OF, CATEGORIES, LOCAL_TOOLS, MODEL, ROOT, TOOLS_OF, build_graph, load_mcp_tools
from app.campus_data import init_db

STATIC = os.path.join(ROOT, "app", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        app.state.mcp_client, mcp_tools = await load_mcp_tools()
        app.state.mcp_ok = True
    except Exception as e:                       # the assistant still works with local tools only
        print("MCP server unavailable:", e)
        mcp_tools, app.state.mcp_ok = [], False
    app.state.tools = [(t, "local") for t in LOCAL_TOOLS] + [(t, "mcp") for t in mcp_tools]
    async with AsyncSqliteSaver.from_conn_string(os.path.join(ROOT, "data", "checkpoints.db")) as saver:
        app.state.saver = saver
        app.state.graph = build_graph([t for t, _ in app.state.tools], saver)
        yield


app = FastAPI(title="Campus Copilot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/info")
async def info(request: Request):
    st = request.app.state
    return {
        "model": MODEL, "mcp": st.mcp_ok, "categories": CATEGORIES,
        "tools": [{"name": t.name, "source": src, "description": (t.description or "").split("\n")[0],
                   "agents": [c for c, names in TOOLS_OF.items() if t.name in names]} for t, src in st.tools],
        "nodes": ["classifier", *AGENT_OF.values(), "tools", "fallback"],
    }


class ChatIn(BaseModel):
    message: str
    thread_id: str


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": body.thread_id}}

    async def stream():
        t0 = last = time.perf_counter()
        path, final = [], ""
        try:
            async for mode, chunk in graph.astream({"messages": [HumanMessage(body.message)]}, config,
                                                   stream_mode=["messages", "updates"]):
                if mode == "messages":
                    msg, meta = chunk
                    node = meta.get("langgraph_node", "")
                    if node.endswith("_agent") and isinstance(msg, AIMessageChunk) and msg.content:
                        yield sse({"type": "token", "node": node, "text": msg.content})
                    continue
                for node, update in chunk.items():         # mode == "updates"
                    now = time.perf_counter()
                    ms, last = round((now - last) * 1000), now
                    path.append({"node": node, "ms": ms})
                    yield sse({"type": "node", "node": node, "ms": ms})
                    update = update or {}
                    if node == "classifier":
                        yield sse({"type": "route", "category": update.get("category"),
                                   "confidence": update.get("confidence"), "reason": update.get("reason")})
                    for m in update.get("messages", []):
                        if isinstance(m, AIMessage) and m.tool_calls:
                            for tc in m.tool_calls:
                                yield sse({"type": "tool_call", "name": tc["name"], "args": tc["args"]})
                        elif isinstance(m, ToolMessage):
                            content = m.content if isinstance(m.content, str) else "\n".join(
                                p.get("text", "") if isinstance(p, dict) else str(p) for p in m.content)
                            yield sse({"type": "tool_result", "name": m.name, "status": m.status,
                                       "content": content[:600]})
                        elif isinstance(m, AIMessage):
                            final = m.content
        except Exception as e:                              # after RetryPolicy gave up
            final = f"Sorry, the model is unavailable right now ({type(e).__name__}). Please try again."
            yield sse({"type": "error", "message": str(e)[:300]})
        snap = await graph.aget_state(config)
        yield sse({"type": "done", "answer": final, "total_ms": round((time.perf_counter() - t0) * 1000),
                   "path": path, "messages_in_memory": len(snap.values.get("messages", []))})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/threads/{thread_id}")
async def thread(thread_id: str, request: Request):
    graph = request.app.state.graph
    config = {"configurable": {"thread_id": thread_id}}
    snap = await graph.aget_state(config)
    history = [h async for h in graph.aget_state_history(config)]
    msgs = []
    for m in snap.values.get("messages", []):
        role = {"human": "user", "ai": "assistant", "tool": "tool"}.get(m.type, m.type)
        if role == "assistant" and not m.content:
            continue
        msgs.append({"role": role, "content": m.content if isinstance(m.content, str) else str(m.content),
                     "name": getattr(m, "name", None)})
    return {"thread_id": thread_id, "messages": msgs, "checkpoints": len(history),
            "category": snap.values.get("category")}


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str, request: Request):
    await request.app.state.saver.adelete_thread(thread_id)
    return {"deleted": thread_id}


@app.get("/api/eval")
async def get_eval():
    p = os.path.join(ROOT, "data", "eval.json")
    return JSONResponse(json.load(open(p)) if os.path.exists(p) else {"summary": None, "rows": []})


@app.post("/api/eval/run")
async def run_eval_now(request: Request):
    from app.evaluate import run_eval
    return await run_eval(graph=request.app.state.graph)
