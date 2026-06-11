from textual.app import App
from textual.widgets import Input, RichLog


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

    def compose(self):
        yield RichLog()
        yield Input()

    def on_input_submitted(self, event: Input.Submitted):
        output = self.query_one(RichLog)
        output.write("Hello from pacli!")
        event.input.value = ""
