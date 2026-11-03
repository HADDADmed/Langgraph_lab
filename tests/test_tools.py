"""Unit tests for the tools (no LLM needed)."""
from app.agent import calculator, current_datetime
from app.campus_data import init_db
from app import mcp_server as campus


def test_calculator_arithmetic():
    assert calculator.invoke({"expression": "125 * 38 + 17"}) == "4767"
    assert calculator.invoke({"expression": "(15 + 27) * 3 - 2 ** 5"}) == "94"
    assert calculator.invoke({"expression": "2^10"}) == "1024"          # ^ accepted as power


def test_calculator_is_safe():
    for attack in ["__import__('os').system('ls')", "open('/etc/passwd').read()", "[1,2][0]", "x + 1"]:
        assert calculator.invoke({"expression": attack}) == "Invalid expression"


def test_datetime_has_year():
    assert "20" in current_datetime.invoke({})


def test_campus_tools():
    init_db()
    assert "Dr. Amrani" in campus.course_lookup("deep learning")
    assert "AI503" in campus.course_lookup("langgraph")
    assert "No course found" in campus.course_lookup("quantum basket weaving")
    assert "2027-01-11" in campus.academic_calendar("exam")
    assert "student portal" in campus.admin_procedure("How do I get an enrollment certificate?")
    assert "contact the administration" in campus.admin_procedure("parking permit")
