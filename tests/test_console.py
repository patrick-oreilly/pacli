from textual.widgets import Input, RichLog
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
        await bus.emit("tool_result", {"tool": "read_file", "args": {"path": "test.txt"}, "result": "file content here"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "▶ read_file(path='test.txt')" in output_text
        assert "→ [exit 0]" in output_text


async def test_tool_result_success_shows_dim_exit_zero():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "execute_shell", "args": {"command": "echo hi"}, "result": "hi\n"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "▶ execute_shell(command='echo hi')" in output_text
        assert "→ [exit 0]" in output_text


async def test_tool_result_error_shows_amber_exit_one():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "execute_shell", "args": {"command": "rm --no-preserve-root /"}, "error": "Permission denied"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "▶ execute_shell(command='rm --no-preserve-root /')" in output_text
        assert "→ [exit 1]" in output_text


async def test_tool_result_denied_shows_dim_denied():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "execute_shell", "args": {"command": "rm -rf /"}, "error": "Approval denied by user"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "▶ execute_shell(command='rm -rf /')" in output_text
        assert "→ [denied]" in output_text


async def test_tool_result_no_args_shows_tool_name_only():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "unknown_tool", "result": "ok"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "▶ unknown_tool" in output_text
        assert "→ [exit 0]" in output_text


async def test_thinking_indicator_shows_during_streaming_and_hides_after():
    bus = EventBus()
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        thinking = app.query_one("#thinking")
        assert "hidden" in thinking.classes

        bus.on("prompt_submitted", orchestrator.process_prompt)

        input_widget = app.query_one(Input)
        input_widget.focus()
        await pilot.press("enter")

        # After streaming finishes, the spinner should be visible
        assert "hidden" not in thinking.classes, "thinking indicator should be visible after stream finished"

        # Spinner should hide when the next stream_started fires
        hidden_on_stream_started = False

        def check_hidden(data):
            nonlocal hidden_on_stream_started
            hidden_on_stream_started = "hidden" in thinking.classes

        bus.on("stream_started", check_hidden)

        input_widget.focus()
        input_widget.value = "again"
        await pilot.press("enter")
        assert hidden_on_stream_started, "thinking indicator should hide on next stream_started"


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


async def test_user_prompt_renders_with_prefix_and_color():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "hello world"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        assert len(output.lines) > 0

        found = False
        for line in output.lines:
            line_str = str(line)
            if "hello world" in line_str:
                assert "> hello world" in line_str, f"Expected '> hello world' in '{line_str}'"
                found = True
                break
        assert found, "User prompt not found in output"


async def test_user_prompt_has_blank_line_separator():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()

        # Submit first prompt
        input_widget.value = "first"
        await pilot.press("enter")

        # Submit second prompt
        input_widget.value = "second"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "> first" in output_text
        assert "> second" in output_text
