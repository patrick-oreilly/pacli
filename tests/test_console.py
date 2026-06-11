import pytest
from textual.widgets import Input, RichLog, Static
from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.events import EventBus
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


async def test_console_streams_tokens_via_events():
    bus = EventBus()
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    app = Console(orchestrator=orchestrator, event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")
        output = app.query_one(RichLog)
        assert any("Hello" in str(line) for line in output.lines)
        assert any("MockAdapter" in str(line) for line in output.lines)


async def test_thinking_indicator_starts_and_ends_hidden():
    bus = EventBus()
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    app = Console(orchestrator=orchestrator, event_bus=bus)
    async with app.run_test() as pilot:
        thinking = app.query_one("#thinking")
        assert "hidden" in thinking.classes
        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")
        assert "hidden" in thinking.classes
