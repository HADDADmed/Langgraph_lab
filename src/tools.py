"""Tools used by the agents: a safe calculator, the current date/time and a SQLite course catalogue."""
import ast
import operator as op
import os
import sqlite3
from datetime import datetime

from langchain_core.tools import tool

_ALLOWED_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.Mod: op.mod, ast.FloorDiv: op.floordiv,
    ast.USub: op.neg, ast.UAdd: op.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("Unsupported expression")


@tool
def calculator(expression: str) -> str:
    """Calculate a mathematical expression such as '25 * 4 + 10'. Supports + - * / ** % //."""
    try:
        return str(_safe_eval(ast.parse(expression.strip(), mode="eval")))
    except Exception:
        return "Invalid expression"


@tool
def current_datetime(_: str = "") -> str:
    """Return the current date and time. Use for any question about today's date or the current time."""
    return datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")


# ---------------- Optional extension: course catalogue in SQLite ----------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "courses.db")
COURSES = [
    ("AI501", "Machine Learning", 6, "Mon 09:00-12:00", "Dr. Benali",
     "Linear models, decision trees, SVMs, ensembles, model evaluation", "Linear algebra, probability"),
    ("AI502", "Deep Learning", 6, "Tue 14:00-17:00", "Dr. Amrani",
     "MLPs, CNNs, RNNs, Transformers, training tricks", "AI501"),
    ("AI503", "Generative AI and LLM Agents", 4, "Thu 09:00-12:00", "Dr. Idrissi",
     "LLMs, prompting, RAG, LangChain, LangGraph agents", "AI502"),
    ("CS510", "Advanced Python Programming", 4, "Wed 10:00-12:00", "Dr. Alaoui",
     "OOP, typing, async, testing, packaging", "Basic Python"),
    ("MA520", "Optimization for Machine Learning", 5, "Fri 09:00-12:00", "Dr. Tazi",
     "Convex optimization, gradient descent, SGD, Adam, constraints", "Calculus, linear algebra"),
]


def init_db(path: str = DB_PATH) -> str:
    """Create (or recreate) the demo course database and return its path."""
    con = sqlite3.connect(path)
    con.execute("DROP TABLE IF EXISTS courses")
    con.execute("CREATE TABLE courses (code TEXT PRIMARY KEY, title TEXT, ects INTEGER, "
                "schedule TEXT, instructor TEXT, topics TEXT, prerequisites TEXT)")
    con.executemany("INSERT INTO courses VALUES (?,?,?,?,?,?,?)", COURSES)
    con.commit()
    con.close()
    return path


@tool
def course_lookup(query: str) -> str:
    """Look up the university course catalogue (code, title, ECTS credits, schedule, instructor, topics,
    prerequisites). Pass a course code (e.g. 'AI502') or a keyword (e.g. 'deep learning'); pass 'all' to list every course."""
    if not os.path.exists(DB_PATH):
        init_db()
    con = sqlite3.connect(DB_PATH)
    q = query.strip().lower()
    if q in ("", "all", "*", "list"):
        rows = con.execute("SELECT * FROM courses").fetchall()
    else:
        like = f"%{q}%"
        rows = con.execute("SELECT * FROM courses WHERE lower(code) LIKE ? OR lower(title) LIKE ? "
                           "OR lower(topics) LIKE ?", (like, like, like)).fetchall()
    con.close()
    if not rows:
        return f"No course found for '{query}'."
    return "\n".join(f"{c} | {t} | {e} ECTS | {s} | {i} | topics: {tp} | prerequisites: {p}"
                     for c, t, e, s, i, tp, p in rows)
