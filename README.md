# Building AI Agents with LangGraph

A practical lab: from a one-node LangGraph workflow to an **Intelligent University Assistant**. The assistant has a classifier, five specialized agents, conditional routing, tools, memory and error handling. All of it runs on a **local LLM** (`qwen3:8b` served by Ollama), so no API key is needed.

![Architecture](diagrams/assistant.png)

## Deliverables

| Deliverable | File |
|---|---|
| Executed notebook (all parts, outputs, answers) | [`langgraph_lab.ipynb`](langgraph_lab.ipynb) |
| Source code | [`src/assistant.py`](src/assistant.py) (capstone), [`src/tools.py`](src/tools.py) (tools) |
| Architecture diagrams | [`diagrams/`](diagrams): `assistant`, `router_graph`, `tool_graph` (`.png` + Mermaid `.mmd`) |
| Screenshots | [`screenshots/`](screenshots) |
| Report (conceptual questions + results) | [`report.pdf`](report.pdf) (source [`report.md`](report.md)) |

## Setup

```bash
# 1. Local LLM
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b

# 2. Python environment
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name langgraph-lab
```

## How to run

```bash
jupyter lab langgraph_lab.ipynb          # the full lab, kernel "LangGraph lab"

python src/assistant.py                  # scripted demo: every category, both tools, memory, empty input
python src/assistant.py --chat           # interactive chat (memory kept for the whole session)
python src/assistant.py --diagram        # regenerate diagrams/assistant.{mmd,png}
MODEL=llama3.2:3b python src/assistant.py   # any other Ollama model with tool support
```

To use OpenAI instead of Ollama, set `PROVIDER=openai` and `OPENAI_API_KEY` in the environment. The key is never written in the code.

## Design choices

- **Local model instead of `gpt-4o-mini`.** `ChatOllama` has the same LangChain interface as `ChatOpenAI` (`invoke`, `bind_tools`, tool calls), so the lab code is unchanged. Settings: `temperature=0` and `seed=42` for reproducible runs, and `reasoning=False` to turn off qwen3's hidden thinking (faster, shorter answers).
- **Safe calculator.** The lab's `eval()` version is kept only for comparison. The tool used by the agents parses the expression with `ast` and allows only arithmetic operators, so `__import__('os')` returns *Invalid expression*.
- **One shared `ToolNode`, and control goes back to the same agent.** `route_after_tools` reads `state["category"]` and returns to the agent that asked for the tool, so this agent writes the final answer with its own system prompt.
- **Error handling at every level:**
  - an empty question goes to the `fallback` node, without calling the LLM;
  - an unknown classifier label is mapped to `GENERAL`;
  - an LLM or API exception in the classifier sends the flow to `fallback`, and in an agent it produces a polite error message;
  - invalid tool calls (unknown tool, bad arguments) are handled by `ToolNode(handle_tool_errors=True)`, which returns an error `ToolMessage` instead of crashing the graph.
- **Memory.** A `MemorySaver` checkpointer plus a `thread_id` keeps the history per conversation. Different threads are isolated.
- **Extension: a SQLite course catalogue.** `course_lookup` gives the COURSES agent real institutional data (code, ECTS, schedule, instructor, prerequisites) instead of invented answers. It needs no network.
- **Routing evaluation.** The free-text router scored 6/6 on the lab's cases and 9/9 on a harder set. A structured-output (enum) router always gave valid labels but scored 7/9. The analysis is in the notebook and the report.

## Results (qwen3:8b, local GPU)

| Test | Result |
|---|---|
| Router accuracy on the lab's 6 cases | 6/6 (100 %) |
| Extended set (9 cases): free-text vs structured router | 9/9 vs 7/9 |
| Tool agent: "What is 125 * 38?" | calls `calculator` → 4750 |
| Tool agent: "What is the capital of Morocco?" | no tool, answers Rabat |
| Memory without / with checkpointer | forgets / remembers "Ahmed"; another thread does not know the name |
| Capstone: 6 queries, every category + empty input | all routed correctly; `calculator`, `current_datetime`, `course_lookup` used where needed |
