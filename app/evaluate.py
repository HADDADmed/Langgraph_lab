"""Offline evaluation of Campus Copilot: routing accuracy, tool selection, answer checks and latency.

    python -m app.evaluate            # writes data/eval.json (shown in the web app, Evaluation tab)
"""
import asyncio
import json
import os
import time
import uuid

from langchain_core.messages import HumanMessage

from app.agent import CATEGORIES, LOCAL_TOOLS, MODEL, ROOT, build_graph, load_mcp_tools
from app.campus_data import init_db

# (question, expected category, expected tool or None, expected substring(s) in the answer or None)
CASES = [
    ("Who teaches Deep Learning and in which room?", "COURSES", "course_lookup", "Amrani"),
    ("What are the prerequisites of Generative AI and LLM Agents?", "COURSES", "course_lookup", "AI502"),
    ("How is the Computer Vision course assessed?", "COURSES", "course_lookup", "60%"),
    ("When do the semester 1 final exams start?", "COURSES", "academic_calendar", ["2027-01-11", "January 11", "11 January"]),
    ("Write a Python function that returns the n-th Fibonacci number.", "PROGRAMMING", None, "def "),
    ("What is the difference between a list and a tuple in Python?", "PROGRAMMING", None, "immutable"),
    ("Why do I get 'IndexError: list index out of range'?", "PROGRAMMING", None, None),
    ("What is 125 * 38 + 17?", "MATHEMATICS", "calculator", "4767"),
    ("Compute (15 + 27) * 3 - 2 ** 5.", "MATHEMATICS", "calculator", "94"),
    ("What is the derivative of x^3 + 2x?", "MATHEMATICS", None, "3x"),
    ("How do I request an enrollment certificate?", "ADMINISTRATION", "admin_procedure", "portal"),
    ("How can I get an official transcript?", "ADMINISTRATION", "admin_procedure", "Registrar"),
    ("What is the deadline to pay the tuition fees?", "ADMINISTRATION", "academic_calendar", ["2026-11-30", "November 30", "30 November"]),
    ("What is today's date?", "GENERAL", "current_datetime", None),
    ("Explain overfitting in one paragraph.", "GENERAL", None, None),
    ("Hello! Who are you?", "GENERAL", None, None),
]


async def run_eval(graph=None, progress=None):
    client = None
    if graph is None:
        init_db()
        client, mcp_tools = await load_mcp_tools()
        from langgraph.checkpoint.memory import MemorySaver
        graph = build_graph(LOCAL_TOOLS + mcp_tools, MemorySaver())
    rows = []
    for i, (q, cat, tool, needle) in enumerate(CASES):
        t0 = time.perf_counter()
        r = await graph.ainvoke({"messages": [HumanMessage(q)]}, {"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}})
        dt = time.perf_counter() - t0
        used = [tc["name"] for m in r["messages"] for tc in (getattr(m, "tool_calls", None) or [])]
        answer = r["messages"][-1].content
        rows.append({
            "question": q, "expected": cat, "got": r["category"], "confidence": r.get("confidence"),
            "route_ok": r["category"] == cat,
            "expected_tool": tool, "tools": used, "tool_ok": (tool in used) if tool else (not used or cat == "GENERAL"),
            "answer_ok": any(n.lower() in answer.lower() for n in ([needle] if isinstance(needle, str) else needle))
                         if needle else None,
            "seconds": round(dt, 2), "answer": answer[:400],
        })
        if progress:
            progress(i + 1, len(CASES))
    n = len(rows)
    checked = [r for r in rows if r["answer_ok"] is not None]
    summary = {
        "model": MODEL, "date": time.strftime("%Y-%m-%d %H:%M"), "cases": n,
        "routing_accuracy": sum(r["route_ok"] for r in rows) / n,
        "tool_accuracy": sum(r["tool_ok"] for r in rows) / n,
        "answer_accuracy": sum(r["answer_ok"] for r in checked) / len(checked),
        "avg_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "per_category": {c: f"{sum(r['route_ok'] for r in rows if r['expected'] == c)}/"
                            f"{sum(1 for r in rows if r['expected'] == c)}" for c in CATEGORIES},
    }
    result = {"summary": summary, "rows": rows}
    os.makedirs(f"{ROOT}/data", exist_ok=True)
    json.dump(result, open(f"{ROOT}/data/eval.json", "w"), indent=2)
    return result


if __name__ == "__main__":
    res = asyncio.run(run_eval(progress=lambda i, n: print(f"\r{i}/{n}", end="", flush=True)))
    print()
    for r in res["rows"]:
        flag = "✓" if r["route_ok"] and r["tool_ok"] and r["answer_ok"] is not False else "✗"
        print(f"{flag} {r['got']:<15} {r['seconds']:>5}s tools={','.join(r['tools']) or '-':<20} {r['question']}")
    print(json.dumps(res["summary"], indent=2))
