from typing import Any, Optional

from textual.app import App
from textual.widgets import Input, RichLog, Static

from pacli.events import EventBus


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
        margin: 1 2;
    }

    #thinking {
        dock: top;
        height: 1;
        text-style: italic;
        color: #888888;
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

    def compose(self):
        yield Static(id="thinking", classes="hidden")
        yield RichLog()
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

    def _on_stream_started(self, data):
        self._thinking.remove_class("hidden")

    def _on_token_received(self, token):
        self._rich_log.write(token)

    def _on_stream_finished(self, data):
        self._thinking.add_class("hidden")

    def _on_tool_result(self, data):
        if "error" in data:
            self._rich_log.write(f"[error] {data['error']}")
        else:
            self._rich_log.write(f"[tool] {data['result']}")

    def _on_prompt_error(self, data):
        self._rich_log.write(f"[error] {data.get('error', 'Unknown error')}")

    def _on_approval_required(self, data: dict[str, Any]) -> None:
        tool = data.get("tool", "unknown")
        command = data.get("command", "")
        detail = f"'{command}'" if command else tool
        self._rich_log.write(f"! Approval required: {detail}? (y/n)")
        if approval_id := data.get("id"):
            self._pending_approvals[approval_id] = data

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
