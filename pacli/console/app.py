import asyncio
from pathlib import Path
from typing import Any, Optional

from rich.align import Align
from rich.text import Text
from textual.app import App
from textual.widgets import Input, RichLog, Static
from textual.timer import Timer

from pacli.events import EventBus

BRAILLE_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Console(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    RichLog {
        height: 1fr;
        padding: 1;
        border: none;
    }

    Input {
        dock: bottom;
        margin: 1 8;
        border: none;
        border-bottom: tall #00F0FF;
    }

    #thinking {
        dock: bottom;
        height: 1;
        color: #00F0FF;
        padding: 0 1;
    }

    .hidden {
        display: none;
    }
    """

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        super().__init__()
        self._event_bus = event_bus
        self._rich_log: Optional[RichLog] = None
        self._thinking: Optional[Static] = None
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._spinner_timer: Optional[Timer] = None
        self._spinner_frame = 0

    def compose(self):
        yield RichLog()
        yield Static(id="thinking", classes="hidden")
        yield Input()

    def on_mount(self):
        self._rich_log = self.query_one(RichLog)
        self._thinking = self.query_one("#thinking")
        if self._event_bus:
            self._event_bus.on("stream_started", self._on_stream_started)
            self._event_bus.on("token_received", self._on_token_received)
            self._event_bus.on("stream_finished", self._on_stream_finished)
            self._event_bus.on("tool_result", self._on_tool_result)
            self._event_bus.on("approval_required", self._on_approval_required)
            self._event_bus.on("prompt_error", self._on_prompt_error)
            self._event_bus.on("system_event", self._on_system_event)

    def _on_stream_started(self, data):
        self._stop_spinner()

    def _on_token_received(self, token):
        self._rich_log.write(token)

    def _on_stream_finished(self, data):
        self._start_spinner()

    def _on_tool_result(self, data):
        tool = data.get("tool", "unknown")
        args = data.get("args", {})
        args_repr = ", ".join(f"{k}={v!r}" for k, v in args.items())
        call_line = f"▶ {tool}({args_repr})" if args_repr else f"▶ {tool}"

        if "error" in data:
            error = data["error"]
            is_denied = error == "Approval denied by user"
            if is_denied:
                line = f"  {call_line} → [denied]"
                self._rich_log.write(Text(line, style="dim #888888"))
            else:
                line = f"  {call_line} → [exit 1]"
                self._rich_log.write(Text(line, style="bold #FF8C00"))
        else:
            line = f"  {call_line} → [exit 0]"
            self._rich_log.write(Text(line, style="dim #888888"))

    def _on_system_event(self, data: dict[str, Any]) -> None:
        message = data.get("message", "")
        text = Text(message, style="dim #888888")
        centered = Align.center(text)
        self._rich_log.write(centered)

    def _on_prompt_error(self, data):
        self._rich_log.write(f"[error] {data.get('error', 'Unknown error')}")

    def _on_approval_required(self, data: dict[str, Any]) -> None:
        tool = data.get("tool", "unknown")
        command = data.get("command", "")
        detail = f"'{command}'" if command else tool
        self._rich_log.write(f"! Approval required: {detail}? (y/n)")
        if approval_id := data.get("id"):
            self._pending_approvals[approval_id] = data

    def _start_spinner(self) -> None:
        if not self._thinking or self._spinner_timer is not None:
            return
        self._spinner_frame = 0
        self._thinking.remove_class("hidden")
        self._spinner_timer = self.set_interval(
            1 / 15, self._tick_spinner
        )

    def _stop_spinner(self) -> None:
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self._spinner_frame = 0
        if self._thinking:
            self._thinking.add_class("hidden")

    def _tick_spinner(self) -> None:
        if not self._thinking or self._spinner_timer is None:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(BRAILLE_FRAMES)
        self._thinking.update(BRAILLE_FRAMES[self._spinner_frame])

    async def on_input_submitted(self, event: Input.Submitted):
        if self._pending_approvals:
            text = event.value.strip().lower()
            if text in ("y", "yes", "n", "no"):
                approved = text in ("y", "yes")
                first_id = next(iter(self._pending_approvals))
                self._pending_approvals.pop(first_id)
                if self._event_bus:
                    await self._event_bus.emit(
                        "approval_response",
                        {"id": first_id, "approved": approved},
                    )
            else:
                self._rich_log.write("! Answer y/n to approve or deny the pending request")
        elif self._event_bus:
            await self._event_bus.emit("prompt_submitted", event.value)
        else:
            self._rich_log.write("Hello from pacli!")
        event.input.value = ""
