"""API tests against the real local model (Ollama must be running)."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.server import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def stream(client, message, thread):
    with client.stream("POST", "/api/chat", json={"message": message, "thread_id": thread}) as r:
        return [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]


def test_info(client):
    info = client.get("/api/info").json()
    names = {t["name"] for t in info["tools"]}
    assert info["mcp"] is True and {"calculator", "course_lookup", "admin_procedure"} <= names


def test_math_uses_calculator(client):
    ev = stream(client, "What is 125 * 38 + 17?", f"test-{uuid.uuid4()}")
    route = next(e for e in ev if e["type"] == "route")
    assert route["category"] == "MATHEMATICS"
    assert any(e["type"] == "tool_call" and e["name"] == "calculator" for e in ev)
    assert "4767" in ev[-1]["answer"] and ev[-1]["type"] == "done"


def test_mcp_course_tool(client):
    ev = stream(client, "Who teaches Deep Learning?", f"test-{uuid.uuid4()}")
    assert any(e["type"] == "tool_result" and e["name"] == "course_lookup" for e in ev)
    assert "Amrani" in ev[-1]["answer"]


def test_memory_persists_in_thread(client):
    t = f"test-{uuid.uuid4()}"
    stream(client, "My name is Sara.", t)
    assert "Sara" in stream(client, "What is my name?", t)[-1]["answer"]
    assert len(client.get(f"/api/threads/{t}").json()["messages"]) == 4
    client.delete(f"/api/threads/{t}")
    assert client.get(f"/api/threads/{t}").json()["messages"] == []
