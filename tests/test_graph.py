"""Structure and routing tests of the LangGraph assistant."""
import asyncio

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent import AGENT_OF, LOCAL_TOOLS, TOOLS_OF, build_graph


def test_graph_nodes_and_edges():
    g = build_graph(LOCAL_TOOLS).get_graph()
    nodes = set(g.nodes)
    assert {"classifier", "tools", "fallback", *AGENT_OF.values()} <= nodes
    edges = {(e.source, e.target) for e in g.edges}
    for agent in AGENT_OF.values():
        assert ("classifier", agent) in edges and ("tools", agent) in edges and (agent, "tools") in edges


def test_least_privilege_tools():
    assert TOOLS_OF["PROGRAMMING"] == []
    assert TOOLS_OF["MATHEMATICS"] == ["calculator"]


def test_empty_input_goes_to_fallback_without_llm():
    class NoLLM:                                    # any call to the model would fail the test
        def with_structured_output(self, *a, **k): return self
        def bind_tools(self, *a, **k): return self
        async def ainvoke(self, *a, **k): raise AssertionError("LLM must not be called")
    g = build_graph(LOCAL_TOOLS, MemorySaver(), llm=NoLLM())
    r = asyncio.run(g.ainvoke({"messages": [HumanMessage("   ")]}, {"configurable": {"thread_id": "x"}}))
    assert r["category"] == "EMPTY" and "empty" in r["messages"][-1].content.lower()
