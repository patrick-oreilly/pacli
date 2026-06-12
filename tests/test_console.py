from pathlib import Path
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
        await bus.emit("tool_result", {"tool": "read_file", "args": {"path": "test.txt"}, "result": "file content here"})
        output = app.query_one(RichLog)
        output_text = "\n".join(line.text for line in output.lines)
        assert "▶ read_file(path='test.txt')" in output_text
        assert "→ ok" in output_text


async def test_tool_result_success_shows_dim_exit_zero():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "execute_shell", "args": {"command": "echo hi"}, "result": "hi\n"})
        output = app.query_one(RichLog)
        output_text = "\n".join(line.text for line in output.lines)
        assert "▶ execute_shell(command='echo hi')" in output_text
        assert "→ ok" in output_text


async def test_tool_result_error_shows_amber_exit_one():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "execute_shell", "args": {"command": "rm --no-preserve-root /"}, "error": "Permission denied"})
        output = app.query_one(RichLog)
        output_text = "\n".join(line.text for line in output.lines)
        assert "▶ execute_shell(command='rm --no-preserve-root /')" in output_text
        assert "✖ Permission denied" in output_text


async def test_tool_result_denied_shows_dim_denied():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "execute_shell", "args": {"command": "rm -rf /"}, "error": "Approval denied by user"})
        output = app.query_one(RichLog)
        output_text = "\n".join(line.text for line in output.lines)
        assert "▶ execute_shell(command='rm -rf /')" in output_text
        assert "→ denied" in output_text


async def test_tool_result_no_args_shows_tool_name_only():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "unknown_tool", "result": "ok"})
        output = app.query_one(RichLog)
        output_text = "\n".join(line.text for line in output.lines)
        assert "▶ unknown_tool" in output_text
        assert "→ ok" in output_text


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

        # After streaming finishes, the spinner should be hidden
        assert "hidden" in thinking.classes, "thinking indicator should be hidden after stream finished"

        # Spinner should show when the next stream_started fires
        shown_on_stream_started = False

        def check_shown(data):
            nonlocal shown_on_stream_started
            shown_on_stream_started = "hidden" not in thinking.classes

        bus.on("stream_started", check_shown)

        input_widget.focus()
        input_widget.value = "again"
        await pilot.press("enter")
        assert shown_on_stream_started, "thinking indicator should show on stream_started"


async def test_console_shows_approval_prompt_when_approval_required():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit(
            "approval_required",
            {"id": "test-1", "tool": "execute_shell", "command": "echo hi"},
        )
        output = app.query_one(RichLog)
        assert any("Approve" in line.text for line in output.lines)
        assert any("echo hi" in line.text for line in output.lines)


async def test_console_emits_approved_on_y_input():
    bus = EventBus()
    responses = _collect_events(bus)
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit(
            "approval_required",
            {"id": "test-2", "tool": "execute_shell", "command": "echo hi"},
        )
        await pilot.press("y")

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
        await pilot.press("n")

        assert len(responses) == 1
        assert responses[0]["id"] == "test-3"
        assert responses[0]["approved"] is False


async def test_slash_command_intercepts_and_emits_event():
    bus = EventBus()
    slash_events = []
    prompt_events = []

    def on_slash(data):
        slash_events.append(data)

    def on_prompt(data):
        prompt_events.append(data)

    bus.on("slash_command", on_slash)
    bus.on("prompt_submitted", on_prompt)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "/provider ollama"
        await pilot.press("enter")

        assert len(slash_events) == 1
        assert slash_events[0] == "/provider ollama"
        assert len(prompt_events) == 0


async def test_slash_command_provider_switches_and_displays_system_event():
    bus = EventBus()
    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        provider_factory={"mock": (MockAdapter,), "ollama": (MockAdapter,)},
    )
    bus.on("slash_command", orchestrator._on_slash_command)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "/provider ollama"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "provider switched to ollama" in output_text


async def test_slash_command_model_displays_system_event():
    bus = EventBus()
    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    bus.on("slash_command", orchestrator._on_slash_command)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "/model llama3.2"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "model switched to llama3.2" in output_text


async def test_slash_command_help_displays_available_commands():
    bus = EventBus()
    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    bus.on("slash_command", orchestrator._on_slash_command)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "/help"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "available commands" in output_text


async def test_non_slash_input_still_routes_as_prompt():
    bus = EventBus()
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    bus.on("prompt_submitted", orchestrator.process_prompt)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "hello world"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "Hello" in output_text
        assert "MockAdapter" in output_text


async def test_slash_command_unknown_provider_shows_error():
    bus = EventBus()
    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        provider_factory={"mock": (MockAdapter,)},
    )
    bus.on("slash_command", orchestrator._on_slash_command)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "/provider none"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "unknown provider" in output_text


async def test_slash_command_unknown_displays_message():
    bus = EventBus()
    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    bus.on("slash_command", orchestrator._on_slash_command)

    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.focus()
        input_widget.value = "/foobar"
        await pilot.press("enter")

        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "unknown command" in output_text


async def test_tool_used_renders_compact_inline():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_used", {"tool": "execute_shell", "args": {"command": "npm test"}, "id": "tc1"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "▸ execute_shell(command='npm test')" in output_text


async def test_tool_result_skips_loop_events():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        await bus.emit("tool_result", {"tool": "_loop", "args": {}, "error": "Exceeded max iterations (20)"})
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "Exceeded max iterations" not in output_text


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


async def test_system_fault_displays_dim_line(tmp_path: Path):
    crash_log = tmp_path / "crash.log"
    original = Console._crash_log_path
    Console._crash_log_path = staticmethod(lambda: crash_log)
    try:
        bus = EventBus()
        app = Console(event_bus=bus)
        async with app.run_test() as pilot:
            await bus.emit("system_fault", {"traceback": "Traceback (most recent call last):\n  ...\nRuntimeError: test crash"})
            output = app.query_one(RichLog)
            messages = [str(line) for line in output.lines]
            assert any("System fault" in msg for msg in messages)
            input_widget = app.query_one(Input)
            assert input_widget.value == ""
    finally:
        Console._crash_log_path = original


async def test_system_fault_writes_traceback_to_crash_log(tmp_path: Path):
    crash_log = tmp_path / "crash.log"
    original = Console._crash_log_path
    Console._crash_log_path = staticmethod(lambda: crash_log)
    try:
        bus = EventBus()
        app = Console(event_bus=bus)
        async with app.run_test() as pilot:
            await bus.emit("system_fault", {"traceback": "RuntimeError: boom"})
        assert crash_log.exists()
        assert "RuntimeError: boom" in crash_log.read_text()
    finally:
        Console._crash_log_path = original


async def test_system_fault_clears_input_box(tmp_path: Path):
    crash_log = tmp_path / "crash.log"
    original = Console._crash_log_path
    Console._crash_log_path = staticmethod(lambda: crash_log)
    try:
        bus = EventBus()
        app = Console(event_bus=bus)
        async with app.run_test() as pilot:
            input_widget = app.query_one(Input)
            input_widget.focus()
            input_widget.value = "some pending text"
            await bus.emit("system_fault", {"traceback": "crash"})
            assert input_widget.value == ""
    finally:
        Console._crash_log_path = original


async def test_user_prompt_renders_with_prefix_and_color():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.value = "hello world"
        await input_widget.action_submit()
        await pilot.pause()
        output = app.query_one(RichLog)
        assert any("▸ hello world" in line.text for line in output.lines)


async def test_user_prompt_has_blank_line_separator():
    bus = EventBus()
    app = Console(event_bus=bus)
    async with app.run_test() as pilot:
        input_widget = app.query_one(Input)
        input_widget.value = "first"
        await input_widget.action_submit()
        await pilot.pause()
        input_widget.value = "second"
        await input_widget.action_submit()
        await pilot.pause()
        output = app.query_one(RichLog)
        output_text = "\n".join(line.text for line in output.lines)
        assert "▸ first" in output_text
        assert "▸ second" in output_text


async def test_boot_telemetry_writes_header_with_cyan_dot():
    app = Console()
    async with app.run_test() as pilot:
        output = app.query_one(RichLog)
        output_text = "\n".join(str(line) for line in output.lines)
        assert "pacli v0.1.0" in output_text


async def test_boot_telemetry_writes_context_line_with_model_dir_branch():
    app = Console(model="MockAdapter")
    async with app.run_test() as pilot:
        output = app.query_one(RichLog)
        output_text = "".join(line.text for line in output.lines)
        assert "model: MockAdapter" in output_text
        assert "·  dir:" in output_text
        assert "branch:" in output_text
