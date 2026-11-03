"""Campus MCP server (Model Context Protocol, stdio transport).

The assistant does not import these tools: it discovers them at start-up through
langchain-mcp-adapters, the same way it would use any external MCP server.

    python app/mcp_server.py      # normally started by the assistant as a subprocess
"""
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.campus_data import DB_PATH, PROCEDURES, init_db  # noqa: E402

mcp = FastMCP("campus")


def _db():
    if not os.path.exists(DB_PATH):
        init_db()
    return sqlite3.connect(DB_PATH)


@mcp.tool()
def course_lookup(query: str) -> str:
    """Search the university course catalogue (code, title, ECTS, schedule, room, instructor, topics,
    prerequisites, assessment). Pass a course code (e.g. 'AI502'), a keyword (e.g. 'deep learning'),
    or 'all' to list every course."""
    q = query.strip().lower()
    con = _db()
    if q in ("", "all", "*", "list", "courses"):
        rows = con.execute("SELECT * FROM courses").fetchall()
    else:
        like = f"%{q}%"
        rows = con.execute("SELECT * FROM courses WHERE lower(code) LIKE ? OR lower(title) LIKE ? "
                           "OR lower(topics) LIKE ? OR lower(instructor) LIKE ?", (like,) * 4).fetchall()
    con.close()
    if not rows:
        return f"No course found for '{query}'. Try 'all' to list the catalogue."
    return "\n".join(f"{c} | {t} | {e} ECTS | {s} | {r} | {i} | topics: {tp} | prerequisites: {p} | assessment: {a}"
                     for c, t, e, s, r, i, tp, p, a in rows)


@mcp.tool()
def academic_calendar(query: str = "") -> str:
    """Return official academic calendar dates (semester start, exams, breaks, registration and fee deadlines).
    Optionally filter with a keyword such as 'exam', 'fee' or 'break'."""
    con = _db()
    rows = con.execute("SELECT date, event FROM calendar WHERE lower(event) LIKE ? ORDER BY date",
                       (f"%{query.strip().lower()}%",)).fetchall()
    con.close()
    return "\n".join(f"{d}: {e}" for d, e in rows) or f"No calendar entry matches '{query}'."


@mcp.tool()
def admin_procedure(topic: str) -> str:
    """Return the official administrative procedure for a topic: enrollment certificate, transcript,
    tuition fees, re-enrollment, exam absence."""
    t = topic.strip().lower()
    words = [w for w in re.findall(r"[a-z]+", t) if len(w) > 3 and w not in ("request", "official", "procedure")]
    hits = [f"{k}: {v}" for k, v in PROCEDURES.items() if k in t or any(w in k for w in words)]
    return "\n".join(hits) or ("No official procedure found for this topic. Known topics: "
                               + ", ".join(PROCEDURES) + ". Otherwise contact the administration office.")


if __name__ == "__main__":
    mcp.run(transport="stdio")
