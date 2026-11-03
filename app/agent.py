"""Campus Copilot: the advanced LangGraph assistant behind the web app.

What it adds to the lab capstone (src/assistant.py):
  * structured routing: a Pydantic schema (enum + confidence + reason), few-shot examples, conversation-aware,
    with a free-text fallback
  * MCP tools: campus tools served by a separate MCP server and discovered at start-up
  * least-privilege tools: each specialist agent is bound only to the tools of its domain
  * durable memory: AsyncSqliteSaver checkpointer (conversations survive a restart) + time-travel history
  * context window control: trim_messages keeps only the last turns sent to the LLM
  * RetryPolicy on LLM nodes (transient errors are retried with exponential back-off)
  * streaming: tokens, node updates and tool events are streamed to the UI
"""
import ast
import operator as op
import os
import sys
from datetime import datetime
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, trim_messages
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.types import RetryPolicy
from pydantic import BaseModel, Field

MODEL = os.environ.get("MODEL", "qwen3:8b")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORIES = ["COURSES", "PROGRAMMING", "MATHEMATICS", "ADMINISTRATION", "GENERAL"]
AGENT_OF = {c: f"{c.lower()}_agent" for c in CATEGORIES}

# ----------------------------------------------------------------------------- local tools
_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Pow: op.pow,
        ast.Mod: op.mod, ast.FloorDiv: op.floordiv, ast.USub: op.neg, ast.UAdd: op.pos}


def _safe_eval(n):
    if isinstance(n, ast.Expression):
        return _safe_eval(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        return _OPS[type(n.op)](_safe_eval(n.left), _safe_eval(n.right))
    if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
        return _OPS[type(n.op)](_safe_eval(n.operand))
    raise ValueError("Unsupported expression")


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression such as '125 * 38 + 17'. Supports + - * / ** % // and parentheses."""
    try:
        return str(_safe_eval(ast.parse(expression.strip().replace("^", "**"), mode="eval")))
    except Exception:
        return "Invalid expression"


@tool
def current_datetime() -> str:
    """Return the current date and time. Use for any question about today's date, the day or the time."""
    return datetime.now().strftime("%A, %d %B %Y, %H:%M")


LOCAL_TOOLS = [calculator, current_datetime]

# which tools each specialist may call (least privilege)
TOOLS_OF = {
    "COURSES": ["course_lookup", "academic_calendar"],
    "PROGRAMMING": [],
    "MATHEMATICS": ["calculator"],
    "ADMINISTRATION": ["admin_procedure", "academic_calendar", "current_datetime"],
    "GENERAL": ["current_datetime", "calculator", "course_lookup"],
}

STYLE = (" Answer in GitHub Markdown, concisely. Never use LaTeX: write math in plain text (e.g. 125 × 38 = 4750)."
         " Only state facts about this university that a tool returned.")
SYSTEM_PROMPTS = {
    "COURSES": "You are the courses advisor of the university. ALWAYS call course_lookup for questions about the "
               "university's courses (topics, schedule, room, credits, instructor, prerequisites, assessment) and "
               "academic_calendar for exam or semester dates. For generic curriculum questions you may answer "
               "from general knowledge, saying so.",
    "PROGRAMMING": "You are a programming tutor. Give clear explanations and correct, idiomatic Python code.",
    "MATHEMATICS": "You are a mathematics tutor. Show the reasoning steps. ALWAYS use the calculator tool for "
                   "any arithmetic, never compute numbers yourself.",
    "ADMINISTRATION": "You are the university administration assistant. ALWAYS call admin_procedure for procedures "
                      "and academic_calendar for deadlines. Never invent rules, fees or dates; if the tools have "
                      "no answer, tell the student to contact the administration office.",
    "GENERAL": "You are Campus Copilot, a friendly university assistant. Use current_datetime for questions about "
               "today's date or time. When the student asks which course fits them, CALL course_lookup right away "
               "(with a keyword of their interest) instead of offering to search, and never invent course names. "
               "Remember what the student told you earlier in the conversation.",
}


# ----------------------------------------------------------------------------- state & routing schema
class Route(BaseModel):
    """Routing decision of the classifier."""
    category: Literal["COURSES", "PROGRAMMING", "MATHEMATICS", "ADMINISTRATION", "GENERAL"] = Field(
        description="COURSES: the university's courses, syllabus, schedule, rooms, credits, exams of a course. "
                    "PROGRAMMING: writing, explaining or debugging code. "
                    "MATHEMATICS: calculations, equations, calculus, probability. "
                    "ADMINISTRATION: enrollment, certificates, transcripts, fees, procedures, deadlines. "
                    "GENERAL: anything else (greetings, personal info, date/time, general AI questions).")
    confidence: float = Field(ge=0, le=1, description="confidence in the category, 0 to 1")
    reason: str = Field(description="one short sentence explaining the choice")


class State(TypedDict):
    messages: Annotated[list, add_messages]
    category: str
    confidence: float
    reason: str


FEW_SHOT = """Examples:
"Who teaches Deep Learning and in which room?" -> COURSES
"When are the final exams of semester 1?" -> COURSES
"Fix this IndexError in my Python loop" -> PROGRAMMING
"Implement binary search in Python" -> PROGRAMMING
"What is 17% of 2350?" -> MATHEMATICS
"Integrate x*sin(x)" -> MATHEMATICS
"How do I get my transcript?" -> ADMINISTRATION
"What is the deadline to pay tuition fees?" -> ADMINISTRATION
"Which course should I take if I like NLP?" -> COURSES
"Hi, I'm Sara" -> GENERAL
"What day is it today?" -> GENERAL
"Explain overfitting" -> GENERAL"""


def _text(m) -> str:
    c = getattr(m, "content", m)
    return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if isinstance(p, dict))


def make_llm(**kw):
    from langchain_ollama import ChatOllama
    return ChatOllama(model=MODEL, temperature=0, seed=42, reasoning=False, **kw)


def build_graph(tools, checkpointer=None, llm=None):
    """tools: local + MCP tools. Returns a compiled graph."""
    llm = llm or make_llm()
    by_name = {t.name: t for t in tools}
    router = llm.with_structured_output(Route, method="json_schema")
    retry = RetryPolicy(max_attempts=3, initial_interval=0.5)

    async def classifier(state: State):
        question = _text(state["messages"][-1]).strip()
        if not question:
            return {"category": "EMPTY", "confidence": 1.0, "reason": "Empty input."}
        history = [m for m in state["messages"][:-1] if isinstance(m, (HumanMessage, AIMessage)) and _text(m)][-4:]
        context = "\n".join(f"{'Student' if isinstance(m, HumanMessage) else 'Assistant'}: {_text(m)[:200]}"
                            for m in history) or "(none)"
        prompt = (f"Route the student's latest message to exactly one category.\n{FEW_SHOT}\n\n"
                  f"Recent conversation (for follow-up questions):\n{context}\n\nLatest message: {question}")
        try:
            r = await router.ainvoke(prompt)
            return {"category": r.category, "confidence": round(r.confidence, 2), "reason": r.reason}
        except Exception:                                   # schema failure -> free-text fallback
            raw = _text(await llm.ainvoke(prompt + "\nReturn only the category name.")).upper()
            cat = next((c for c in CATEGORIES if c in raw), "GENERAL")
            return {"category": cat, "confidence": 0.5, "reason": "Fallback (free-text) classification."}

    def make_agent(category):
        bound = [by_name[n] for n in TOOLS_OF[category] if n in by_name]
        model = llm.bind_tools(bound) if bound else llm
        system = SystemMessage(content=SYSTEM_PROMPTS[category] + STYLE)

        async def agent(state: State):
            # keep the context small: system prompt + the last 16 messages, starting on a human turn
            window = trim_messages(state["messages"], max_tokens=16, token_counter=len,
                                   strategy="last", start_on="human")
            return {"messages": [await model.ainvoke([system] + window)]}
        agent.__name__ = AGENT_OF[category]
        return agent

    async def fallback(state: State):
        msg = ("Your message looks empty. Ask me about courses, code, maths, administration or anything else."
               if state["category"] == "EMPTY" else "Sorry, I could not process that. Please try again.")
        return {"messages": [AIMessage(content=msg)]}

    def after_classifier(state):
        return AGENT_OF.get(state["category"], "fallback")

    def after_agent(state):
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    def after_tools(state):
        return AGENT_OF.get(state["category"], "general_agent")

    g = StateGraph(State)
    g.add_node("classifier", classifier, retry_policy=retry)
    g.add_node("fallback", fallback)
    g.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    for c in CATEGORIES:
        g.add_node(AGENT_OF[c], make_agent(c), retry_policy=retry)
        g.add_conditional_edges(AGENT_OF[c], after_agent, {"tools": "tools", END: END})
    g.add_edge(START, "classifier")
    g.add_conditional_edges("classifier", after_classifier,
                            {**{a: a for a in AGENT_OF.values()}, "fallback": "fallback"})
    g.add_conditional_edges("tools", after_tools, {a: a for a in AGENT_OF.values()})
    g.add_edge("fallback", END)
    return g.compile(checkpointer=checkpointer)


async def load_mcp_tools():
    """Start the campus MCP server (stdio) and return its tools as LangChain tools."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    client = MultiServerMCPClient({"campus": {
        "command": sys.executable, "args": [os.path.join(ROOT, "app", "mcp_server.py")], "transport": "stdio"}})
    return client, await client.get_tools()
