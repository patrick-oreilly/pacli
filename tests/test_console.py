import pytest
from textual.widgets import Input, RichLog
from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.orchestrator import Orchestrator


async def test_app_composes_input_and_output():
    app = Console()
    async with app.run_test() as pilot:
        assert isinstance(app.query_one("Input"), Input)
        assert isinstance(app.query_one("RichLog"), RichLog)


async def test_submitting_input_shows_hello_message():
    app = Console()
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")
        assert input_widget.value == ""
        output = app.query_one(RichLog)
        assert any("Hello from pacli!" in str(line) for line in output.lines)


async def test_console_streams_tokens_from_orchestrator():
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter)
    app = Console(orchestrator=orchestrator)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")
        output = app.query_one(RichLog)
        assert any("Hello" in str(line) for line in output.lines)
        assert any("MockAdapter" in str(line) for line in output.lines)
