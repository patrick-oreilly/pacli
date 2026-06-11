from typing import Optional

from textual.app import App
from textual.widgets import Input, RichLog, Static

from pacli.events import EventBus
from pacli.orchestrator import Orchestrator


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
        orchestrator: Optional[Orchestrator] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        super().__init__()
        self._orchestrator = orchestrator
        if event_bus:
            event_bus.on("stream_started", self._on_stream_started)
            event_bus.on("token_received", self._on_token_received)
            event_bus.on("stream_finished", self._on_stream_finished)

    def compose(self):
        yield Static(id="thinking", classes="hidden")
        yield RichLog()
        yield Input()

    def _on_stream_started(self, data):
        self.query_one("#thinking").remove_class("hidden")

    def _on_token_received(self, token):
        self.query_one(RichLog).write(token)

    def _on_stream_finished(self, data):
        self.query_one("#thinking").add_class("hidden")

    async def on_input_submitted(self, event: Input.Submitted):
        if self._orchestrator:
            await self._orchestrator.process_prompt(event.value)
        else:
            self.query_one(RichLog).write("Hello from pacli!")
        event.input.value = ""
