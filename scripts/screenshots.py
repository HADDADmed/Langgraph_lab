"""End-to-end UI run + screenshots with Playwright (uses the installed Chrome).

    uvicorn app.server:app --port 8777 &
    python scripts/screenshots.py http://127.0.0.1:8777
"""
import os
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8777"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "screenshots", "ui")
os.makedirs(OUT, exist_ok=True)


def unclip(page):
    """main scrolls inside a 100vh shell; let the page grow so full_page captures everything."""
    page.evaluate("document.querySelector('.app').style.height='auto';"
                  "document.querySelector('main').style.overflow='visible';"
                  "document.querySelector('.side').style.alignSelf='start';"
                  "document.querySelector('.side').style.position='sticky';"
                  "document.querySelector('.side').style.top='0';"
                  "document.querySelector('.side').style.height='100vh'")


def ask(page, q):
    n = page.evaluate("window.runsDone || 0")
    page.fill("#q", q)
    page.press("#q", "Enter")
    page.wait_for_function(f"(window.runsDone || 0) > {n}", timeout=180_000)
    page.wait_for_timeout(400)
    print("  asked:", q)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    page.goto(URL + "/#chat")
    page.evaluate("localStorage.setItem('thread', 't-demo' + Date.now().toString(36).slice(-4))")
    page.reload()
    page.wait_for_selector(".sugg button")
    page.screenshot(path=f"{OUT}/01_home.png")

    ask(page, "What is 125 * 38 + 17?")
    page.screenshot(path=f"{OUT}/02_math_calculator.png")
    ask(page, "Who teaches Deep Learning, and in which room?")
    page.screenshot(path=f"{OUT}/03_courses_mcp_tool.png")
    ask(page, "How do I request an enrollment certificate?")
    page.screenshot(path=f"{OUT}/04_administration.png")

    page.click("#new-thread")
    ask(page, "My name is Sara and I love computer vision.")
    ask(page, "What is my name, and what do I love?")
    ask(page, "Which course of the university fits that interest?")      # follow-up: routed with context
    page.screenshot(path=f"{OUT}/05_memory.png")
    page.reload()                                           # conversation restored from the SQLite checkpointer
    page.wait_for_selector(".m-ai")
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUT}/06_restored_after_reload.png")

    page.click("#new-thread")
    ask(page, "Write a Python function that checks if a string is a palindrome.")
    page.screenshot(path=f"{OUT}/07_programming.png")
    ask(page, "   ")
    page.screenshot(path=f"{OUT}/08_empty_input_fallback.png")

    page.click("[data-view=arch]")
    unclip(page)
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}/09_architecture.png", full_page=True)
    for el, name in [("#d-system", "system"), ("#d-graph", "agent_graph"), ("#d-seq", "request_lifecycle")]:
        page.locator(el).screenshot(path=f"{ROOT}/diagrams/hand_{name}.png")

    page.click("[data-view=docs]")
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUT}/10_docs.png", full_page=True)

    page.click("[data-view=eval]")
    page.click("#run-eval")
    page.wait_for_function("document.querySelector('#run-eval').textContent.startsWith('Re-run')", timeout=600_000)
    page.wait_for_timeout(500)
    page.screenshot(path=f"{OUT}/11_evaluation.png", full_page=True)
    browser.close()
print("screenshots written to", OUT)
