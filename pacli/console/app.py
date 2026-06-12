import asyncio
from pathlib import Path
from typing import Any, Optional

from rich.align import Align
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.widgets import Input, RichLog, Static
from textual.timer import Timer

from pacli.events import EventBus

BRAILLE_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Console(App):
    CSS = """
    $accent: #00F0FF;
    $secondary: #888888;

    Screen {
        layout: vertical;
        background: #0A0A0F;
        border: none;
    }

    RichLog {
        height: 1fr;
        padding: 1;
        border: none;
        background: #0A0A0F;
    }

    Input {
        dock: bottom;
        margin: 1 8;
        border: none;
        border-bottom: tall $accent;
    }

    #thinking {
        dock: bottom;
        height: 1;
        color: $accent;
        padding: 0 1;
    }

    #hud {
        dock: bottom;
        height: 1;
        text-align: right;
        text-style: dim;
        padding: 0 2;
        color: #888888;
    }

    .hidden {
        display: none;
    }

    .hud-streaming {
        color: #00AAAA;
    }
    """

    BINDINGS = [
        Binding("shift+g", "scroll_to_bottom", "Return to live"),
    ]

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        super().__init__()
        self._event_bus = event_bus
        self._rich_log: Optional[RichLog] = None
        self._thinking: Optional[Static] = None
        self._hud: Optional[Static] = None
        self._spinner_timer: Optional[Timer] = None
        self._spinner_frame = 0
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._is_streaming = False
        self._was_at_bottom = True
        self._in_code_block = False
        self._code_lang = ""
        self._code_lines: list[str] = []
        self._text_buf = ""
        self._error_active = False
        self._last_prompt = ""
        self._error_line_start = 0
        self._approval_pending = False
        self._approval_data: dict[str, Any] = {}
        self._approval_line_start = 0

    def compose(self):
        yield RichLog()
        yield Static(id="thinking", classes="hidden")
        yield Static(id="hud", classes="hidden")
        yield Input()

    def on_mount(self):
        self._rich_log = self.query_one(RichLog)
        self._thinking = self.query_one("#thinking")
        self._hud = self.query_one("#hud")
        self.set_interval(0.2, self._check_scroll)
        if self._event_bus:
            self._event_bus.on("stream_started", self._on_stream_started)
            self._event_bus.on("token_received", self._on_token_received)
            self._event_bus.on("stream_finished", self._on_stream_finished)
            self._event_bus.on("tool_used", self._on_tool_used)
            self._event_bus.on("tool_result", self._on_tool_result)
            self._event_bus.on("approval_required", self._on_approval_required)
            self._event_bus.on("prompt_error", self._on_prompt_error)
            self._event_bus.on("system_event", self._on_system_event)
            self._event_bus.on("system_fault", self._on_system_fault)

    def _check_scroll(self):
        if not self._rich_log:
            return
        at_bottom = self._rich_log.scroll_y >= self._rich_log.max_scroll_y
        changed = at_bottom != self._was_at_bottom
        if changed:
            if at_bottom:
                self._rich_log.auto_scroll = True
            elif not at_bottom and self._is_streaming:
                self._rich_log.auto_scroll = False
        if changed or (not at_bottom and self._is_streaming):
            self._update_hud()
        self._was_at_bottom = at_bottom

    def _update_hud(self):
        if not self._hud or not self._rich_log:
            return
        if not self._is_streaming:
            self._hud.add_class("hidden")
            return
        at_bottom = self._rich_log.scroll_y >= self._rich_log.max_scroll_y
        if at_bottom:
            self._hud.update("● streaming below")
            self._hud.add_class("hud-streaming")
            self._hud.remove_class("hidden")
        else:
            offset = self._rich_log.max_scroll_y - self._rich_log.scroll_y
            self._hud.update(f"↓ {offset:,} · scroll to resume")
            self._hud.remove_class("hud-streaming")
            self._hud.remove_class("hidden")

    def action_scroll_to_bottom(self):
        if self._rich_log:
            self._rich_log.scroll_end(animate=False)
            self._rich_log.auto_scroll = True
            self._was_at_bottom = True
            self._update_hud()

    def _on_stream_started(self, data):
        self._is_streaming = True
        self._text_buf = ""
        self._in_code_block = False
        self._code_lang = ""
        self._code_lines = []
        self._error_active = False
        self._start_spinner()
        self._update_hud()

    def _on_token_received(self, token):
        if hasattr(token, 'text'):
            token = token.text
        self._text_buf += token
        while "\n" in self._text_buf:
            newline_idx = self._text_buf.index("\n")
            line = self._text_buf[:newline_idx]
            remainder = self._text_buf[newline_idx + 1:]
            self._text_buf = remainder
            self._process_line(line + "\n")

    def _process_line(self, line: str) -> None:
        if not self._in_code_block:
            stripped = line.lstrip()
            if not stripped.startswith("```"):
                self._rich_log.write(line)
                return
            after_fence = stripped[3:]
            lang = after_fence.strip() if after_fence else ""
            self._code_lang = lang
            self._in_code_block = True
            label = lang if lang else "code"
            self._rich_log.write(f"[dim]▸ {label}[/dim]\n")
            return

        stripped = line.strip()
        if stripped == "```":
            self._flush_code_block()
            self._in_code_block = False
            self._code_lang = ""
            return

        self._code_lines.append(line)

    def _flush_code_block(self) -> None:
        if not self._code_lines:
            return
        code = "".join(self._code_lines)
        self._code_lines = []
        if not code.strip():
            return
        try:
            from rich.syntax import Syntax
            from pacli.console.syntax_theme import IcySyntaxStyle

            lexer = self._code_lang or "text"
            syntax = Syntax(
                code,
                lexer,
                theme=IcySyntaxStyle,
                background_color="#0D0D14",
                word_wrap=False,
            )
            self._rich_log.write(syntax)
        except Exception:
            self._rich_log.write(code)

    def _on_stream_finished(self, data):
        if self._text_buf:
            self._rich_log.write(self._text_buf)
            self._text_buf = ""
        if self._in_code_block:
            self._flush_code_block()
            self._in_code_block = False
            self._code_lang = ""
        self._is_streaming = False
        self._stop_spinner()
        self._hud.add_class("hidden")
        self._hud.remove_class("hud-streaming")

    def _on_tool_used(self, data):
        tool = data.get("tool", "unknown")
        args = data.get("args", {})
        args_repr = ", ".join(f"{k}={v!r}" for k, v in args.items())
        call_line = f"▸ {tool}({args_repr})" if args_repr else f"▸ {tool}"
        self._rich_log.write(Text(call_line, style="dim #888888"))

    def _on_tool_result(self, data):
        tool = data.get("tool", "unknown")
        if tool == "_loop":
            return
        args = data.get("args", {})
        args_repr = ", ".join(f"{k}={v!r}" for k, v in args.items())
        call_line = f"  ▶ {tool}({args_repr})" if args_repr else f"  ▶ {tool}"

        if "error" in data:
            error = data["error"]
            is_denied = error == "Approval denied by user"
            if is_denied:
                line = f"{call_line} → [denied]"
                self._rich_log.write(Text(line, style="dim #888888"))
            else:
                line = f"{call_line} → [exit 1]"
                self._rich_log.write(Text(line, style="bold #FF8C00"))
        else:
            line = f"{call_line} → [exit 0]"
            self._rich_log.write(Text(line, style="dim #888888"))

    def _on_system_event(self, data: dict[str, Any]) -> None:
        message = data.get("message", "")
        text = Text(message, style="dim #888888")
        centered = Align.center(text)
        self._rich_log.write(centered)

    def _on_prompt_error(self, data):
        self._error_active = True
        self._error_line_start = len(self._rich_log.lines)
        msg = data.get('error', 'Unknown error')
        self._rich_log.write(
            f"[#FF6B6B]■ Connection Failed: {msg}. Press [Enter] to retry.[/#FF6B6B]"
        )

    def _vanish_error(self) -> None:
        if not self._error_active:
            return
        all_lines = list(self._rich_log.lines)
        kept = all_lines[:self._error_line_start]
        self._rich_log.clear()
        for line in kept:
            if line.cell_length > 0:
                self._rich_log.write(line.text + "\n")
        self._error_active = False

    @staticmethod
    def _crash_log_path() -> Path:
        return Path.home() / ".config" / "pacli" / "crash.log"

    def _on_system_fault(self, data):
        tb = data.get("traceback", "")
        crash_path = self._crash_log_path()
        crash_path.parent.mkdir(parents=True, exist_ok=True)
        crash_path.write_text(tb)
        if self._rich_log:
            self._rich_log.write(f"[dim]·· System fault. Session saved to {crash_path}[/dim]")
        if input_widget := self.query_one(Input):
            input_widget.value = ""

    def _on_approval_required(self, data: dict[str, Any]) -> None:
        if self._approval_pending:
            return
        tool = data.get("tool", "unknown")
        command = data.get("command", "")
        self._approval_pending = True
        self._approval_data = data
        self._approval_line_start = len(self._rich_log.lines)
        args_display = f'"{command}"' if command else ""
        self._rich_log.write(f"[#FFB347]⚠ Approval required[/#FFB347]")
        self._rich_log.write(f"[#FFB347]  Tool: {tool}({args_display})[/#FFB347]")
        self._rich_log.write(f"[#FFB347]  Blast radius: may modify filesystem state[/#FFB347]")
        self._rich_log.write(f"[#FFB347]  [y] approve  [n] deny[/#FFB347]")
        self._bindings.bind("y", "approval_yes", "Approve", priority=True)
        self._bindings.bind("n", "approval_no", "Deny", priority=True)

    def action_approval_yes(self) -> None:
        self._resolve_approval(True)

    def action_approval_no(self) -> None:
        self._resolve_approval(False)

    def _resolve_approval(self, approved: bool) -> None:
        all_lines = list(self._rich_log.lines)
        kept = all_lines[:self._approval_line_start]
        self._rich_log.clear()
        for line in kept:
            self._rich_log.write(line.text)
        tool = self._approval_data.get("tool", "unknown")
        command = self._approval_data.get("command", "")
        args_display = f'"{command}"' if command else ""
        status = "approved" if approved else "denied"
        self._rich_log.write(f"[dim]▶ {tool}({args_display}) → [{status}][/dim]")
        approval_id = self._approval_data.get("id")
        if self._event_bus:
            asyncio.get_running_loop().create_task(
                self._event_bus.emit(
                    "approval_response",
                    {"id": approval_id, "approved": approved},
                )
            )
        self._bindings.key_to_bindings.pop("y", None)
        self._bindings.key_to_bindings.pop("n", None)
        self._approval_pending = False
        self._approval_data = {}

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
        if self._error_active:
            self._vanish_error()
            new_prompt = event.value.strip()
            if new_prompt:
                self._last_prompt = new_prompt
            if self._event_bus and self._last_prompt:
                await self._event_bus.emit("prompt_submitted", self._last_prompt)
        elif self._event_bus:
            if event.value.startswith("/"):
                await self._event_bus.emit("slash_command", event.value)
            else:
                self._last_prompt = event.value
                await self._event_bus.emit("prompt_submitted", event.value)
        else:
            self._rich_log.write("Hello from pacli!")
        event.input.value = ""
