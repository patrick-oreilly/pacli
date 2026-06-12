from textual.widgets import Input, RichLog, Static
from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.events import EventBus
from pacli.orchestrator import Orchestrator


def _collect_events(bus: EventBus) -> list:
    events = []
    bus.on("approval_response", lambda d: events.append(d))
    return events


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
    bus.on("prompt_submitted", orchestrator.process_prompt)
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")
        output = app.query_one(RichLog)
        assert any("Hello" in str(line) for line in output.lines)
        assert any("MockAdapter" in str(line) for line in output.lines)


async def test_console_displays_tool_result():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "read_file", "result": "file content here"})
        output = app.query_one(RichLog)
        assert any("file content here" in str(line) for line in output.lines)


async def test_thinking_indicator_shows_during_streaming_and_hides_after():
    bus = EventBus()
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        thinking = app.query_one("#thinking")
        assert "hidden" in thinking.classes

        visible_during_stream = False

        def check_visible(data):
            nonlocal visible_during_stream
            visible_during_stream = "hidden" not in thinking.classes

        bus.on("stream_started", check_visible)
        bus.on("prompt_submitted", orchestrator.process_prompt)

        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")
        assert visible_during_stream, "thinking indicator should be visible during streaming"
        assert "hidden" in thinking.classes


async def test_console_shows_approval_prompt_when_approval_required():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit(
            "approval_required",
            {"id": "test-1", "tool": "execute_shell", "command": "echo hi"},
        )
        output = app.query_one(RichLog)
        assert any("approval required" in str(line).lower() for line in output.lines)
        assert any("echo hi" in str(line) for line in output.lines)


async def test_console_emits_approved_on_y_input():
    bus = EventBus()
    responses = _collect_events(bus)
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit(
            "approval_required",
            {"id": "test-2", "tool": "execute_shell", "command": "echo hi"},
        )
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "y"
        await pilot.press("enter")

        assert len(responses) == 1
        assert responses[0]["id"] == "test-2"
        assert responses[0]["approved"] is True


async def test_console_emits_denied_on_n_input():
    bus = EventBus()
    responses = _collect_events(bus)
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit(
            "approval_required",
            {"id": "test-3", "tool": "execute_shell", "command": "echo hi"},
        )
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "n"
        await pilot.press("enter")

        assert len(responses) == 1
        assert responses[0]["id"] == "test-3"
        assert responses[0]["approved"] is False


async def test_hud_widget_exists_and_starts_hidden():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        hud = app.query_one("#hud")
        assert isinstance(hud, Static)
        assert "hidden" in hud.classes


async def test_hud_shows_streaming_below_during_stream_when_at_bottom():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        hud = app.query_one("#hud")
        await bus.emit("stream_started")
        assert "hidden" not in hud.classes
        assert "streaming below" in str(hud.render())
        assert "hud-streaming" in hud.classes


async def test_hud_hides_after_stream_finished():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        hud = app.query_one("#hud")
        await bus.emit("stream_started")
        assert "hidden" not in hud.classes
        await bus.emit("stream_finished")
        assert "hidden" in hud.classes
        assert "hud-streaming" not in hud.classes


async def test_hud_shows_offset_when_scrolled_up_during_stream():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        hud = app.query_one("#hud")
        rich_log = app.query_one(RichLog)
        for i in range(100):
            rich_log.write(f"Line {i}\n")
        # scroll to top so we are not at bottom
        rich_log.scroll_home(animate=False)
        app._check_scroll()
        await bus.emit("stream_started")
        assert "hidden" not in hud.classes
        assert "scroll to resume" in str(hud.render())
        assert "hud-streaming" not in hud.classes


async def test_hud_shift_g_binding_registered():
    app = Console()
    async with app.run_test() as pilot:
        assert any(b.key == "shift+g" for b in app.BINDINGS)
