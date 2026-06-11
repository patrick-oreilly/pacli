from typing import Optional

from textual.app import App
from textual.widgets import Input, RichLog

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
    """

    def __init__(self, orchestrator: Optional[Orchestrator] = None) -> None:
        super().__init__()
        self._orchestrator = orchestrator

    def compose(self):
        yield RichLog()
        yield Input()

    async def on_input_submitted(self, event: Input.Submitted):
        output = self.query_one(RichLog)
        if self._orchestrator:
            async for token in self._orchestrator.process_prompt(event.value):
                output.write(token)
        else:
            output.write("Hello from pacli!")
        event.input.value = ""
