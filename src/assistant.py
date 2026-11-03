"""Intelligent University Assistant (capstone) as a standalone LangGraph program.

    python src/assistant.py              # scripted demo (all categories, tools, memory, errors)
    python src/assistant.py --chat       # interactive chat with memory
    python src/assistant.py --diagram    # write diagrams/assistant.mmd and .png

LLM: a local Ollama model (default qwen3:8b, override with MODEL=...). If OPENAI_API_KEY is set
and PROVIDER=openai, gpt-4o-mini is used instead.
"""
import os
import sys
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools import calculator, course_lookup, current_datetime, init_db  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATEGORIES = ["COURSES", "PROGRAMMING", "MATHEMATICS", "ADMINISTRATION", "GENERAL"]
NODE_NAMES = {c: f"{c.lower()}_agent" for c in CATEGORIES}
TOOLS = [calculator, current_datetime, course_lookup]

SYSTEM_PROMPTS = {
    "COURSES": "You are a university courses advisor. Use the course_lookup tool for any question about the "
               "university's courses (topics, schedule, credits, instructor, prerequisites). "
               "If the catalogue has no answer, say so honestly.",
    "PROGRAMMING": "You are a programming tutor. Give clear explanations and correct Python code when appropriate.",
    "MATHEMATICS": "You are a mathematics tutor. Show steps. ALWAYS use the calculator tool for arithmetic.",
    "ADMINISTRATION": "You are a university administration assistant (enrollment, fees, certificates, procedures). "
                      "Never invent official rules or deadlines; recommend contacting the administration office when unsure.",
    "GENERAL": "You are a helpful university assistant. Use the date/time tool for questions about the current date or time.",
}


def make_llm():
    if os.environ.get("PROVIDER") == "openai" and os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    from langchain_ollama import ChatOllama
    return ChatOllama(model=os.environ.get("MODEL", "qwen3:8b"), temperature=0, seed=42, reasoning=False)


class AssistantState(TypedDict):
    messages: Annotated[list, add_messages]
    category: str


def build_assistant(llm=None, tools=TOOLS, checkpointer=None):
    llm = llm or make_llm()
    llm_with_tools = llm.bind_tools(tools)

    def classify(state: AssistantState):
        last = state["messages"][-1]
        text = (last.content if hasattr(last, "content") else str(last)).strip()
        if not text:                                         # error handling: empty question
            return {"category": "EMPTY"}
        prompt = f"""
        Classify the student's question into exactly one category:
        COURSES (course content, syllabus, schedules, exams, grading),
        PROGRAMMING, MATHEMATICS,
        ADMINISTRATION (enrollment, fees, certificates, procedures, deadlines),
        GENERAL (anything else).

        Question: {text}

        Return only the category name.
        """
        try:
            raw = llm.invoke(prompt).content.strip().upper()
        except Exception as e:                               # error handling: API errors
            print("Classifier API error:", e)
            return {"category": "ERROR"}
        return {"category": next((c for c in CATEGORIES if c in raw), "GENERAL")}  # unknown label -> GENERAL

    def make_agent(category):
        system = SystemMessage(content=SYSTEM_PROMPTS[category])

        def node(state: AssistantState):
            try:
                return {"messages": [llm_with_tools.invoke([system] + state["messages"])]}
            except Exception as e:                           # error handling: API errors
                return {"messages": [AIMessage(content="Sorry, I ran into a technical problem while answering "
                                                       f"({type(e).__name__}). Please try again.")]}
        return node

    def fallback(state: AssistantState):
        msg = ("Your question seems to be empty. Please type a question and I'll help."
               if state["category"] == "EMPTY" else
               "Sorry, I couldn't process your question right now. Please try again in a moment.")
        return {"messages": [AIMessage(content=msg)]}

    def route_after_classifier(state):
        return NODE_NAMES.get(state["category"], "fallback")

    def route_after_agent(state):
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    def route_after_tools(state):
        return NODE_NAMES.get(state["category"], "general_agent")

    b = StateGraph(AssistantState)
    b.add_node("classifier", classify)
    b.add_node("fallback", fallback)
    b.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    for c in CATEGORIES:
        b.add_node(NODE_NAMES[c], make_agent(c))
    b.add_edge(START, "classifier")
    b.add_conditional_edges("classifier", route_after_classifier,
                            {**{n: n for n in NODE_NAMES.values()}, "fallback": "fallback"})
    for c in CATEGORIES:
        b.add_conditional_edges(NODE_NAMES[c], route_after_agent, {"tools": "tools", END: END})
    b.add_conditional_edges("tools", route_after_tools, {n: n for n in NODE_NAMES.values()})
    b.add_edge("fallback", END)
    return b.compile(checkpointer=checkpointer or MemorySaver())


def ask(assistant, question, thread_id="demo"):
    result = assistant.invoke({"messages": [HumanMessage(content=question)]},
                              {"configurable": {"thread_id": thread_id}})
    used = [tc["name"] for m in result["messages"][-4:] for tc in (getattr(m, "tool_calls", None) or [])]
    print("=" * 70)
    print("USER     :", question)
    print("CATEGORY :", result["category"], "| tools:", ", ".join(dict.fromkeys(used)) or "none")
    print("ASSISTANT:", result["messages"][-1].content.strip())
    return result


def main():
    init_db()
    assistant = build_assistant()
    if "--diagram" in sys.argv:
        os.makedirs(f"{ROOT}/diagrams", exist_ok=True)
        open(f"{ROOT}/diagrams/assistant.mmd", "w").write(assistant.get_graph().draw_mermaid())
        open(f"{ROOT}/diagrams/assistant.png", "wb").write(assistant.get_graph().draw_mermaid_png())
        print("wrote diagrams/assistant.mmd and diagrams/assistant.png")
    elif "--chat" in sys.argv:
        print("University Assistant (type 'exit' to quit)")
        for line in sys.stdin if not sys.stdin.isatty() else iter(lambda: input("You: "), None):
            line = line.rstrip("\n")
            if line.strip().lower() in ("exit", "quit"):
                break
            ask(assistant, line, thread_id="chat")
    else:
        for q in ["Which course covers LangGraph agents, and when is it scheduled?",
                  "Write a Python function that computes the factorial of n.",
                  "What is 125 * 38 + 17?",
                  "How do I request an enrollment certificate?",
                  "What is today's date?",
                  "   "]:
            ask(assistant, q)
        ask(assistant, "My name is Ahmed.", thread_id="memory-test")
        ask(assistant, "What is my name?", thread_id="memory-test")


if __name__ == "__main__":
    main()
