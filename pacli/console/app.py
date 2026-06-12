import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.widgets import Input, RichLog, Static
from textual.timer import Timer

from pacli import __version__
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
        padding: 2 2;
        border: none;
        background: #0A0A0F;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 0;
        scrollbar-background: #0A0A0F;
        scrollbar-color: #2A2A2A;
        scrollbar-color-hover: #5A5A5A;
        scrollbar-color-active: #888888;
    }

    Input {
        dock: bottom;
        margin: 1 8;
        border: none;
        border-bottom: tall $accent;
    }

    Input > .input--cursor {
        background: $accent;
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
        model: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._event_bus = event_bus
        self._model = model or "mock"
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
        self._write_boot_telemetry()
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
            self._event_bus.on("prompt_submitted", self._on_prompt_submitted)

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
            self._rich_log.write(Text("─" * 40, style="dim #2A2A3A"))
            syntax = Syntax(
                code,
                lexer,
                theme=IcySyntaxStyle,
                background_color="#0D0D14",
                word_wrap=True,
            )
            self._rich_log.write(syntax)
            self._rich_log.write(Text("─" * 40, style="dim #2A2A3A"))
        except Exception:
            self._rich_log.write(Text("─" * 40, style="dim #2A2A3A"))
            self._rich_log.write(code)
            self._rich_log.write(Text("─" * 40, style="dim #2A2A3A"))

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

    @staticmethod
    def _truncate_arg(val: Any, max_len: int = 60) -> str:
        s = str(val)
        if len(s) <= max_len:
            return repr(val)
        head = max_len // 2 - 1
        tail = max_len // 2 - 2
        return s[:head] + "…" + s[-tail:]

    @staticmethod
    def _format_args(args: dict[str, Any]) -> str:
        parts = []
        for k, v in args.items():
            parts.append(f"{k}={Console._truncate_arg(v)}")
        return ", ".join(parts)

    def _on_tool_used(self, data):
        tool = data.get("tool", "unknown")
        args = data.get("args", {})
        args_repr = self._format_args(args)
        call_line = f"▸ {tool}({args_repr})" if args_repr else f"▸ {tool}"
        self._rich_log.write(Text(call_line, style="dim #6A6A6A"))

    def _on_tool_result(self, data):
        tool = data.get("tool", "unknown")
        if tool == "_loop":
            return
        args = data.get("args", {})
        args_repr = self._format_args(args)
        call_line = f"  ▶ {tool}" if not args_repr else f"  ▶ {tool}({args_repr})"

        if "error" in data:
            error = data["error"]
            is_denied = error == "Approval denied by user"
            if is_denied:
                line = f"{call_line}  [dim]→ denied[/dim]"
                self._rich_log.write(Text(line, style="#6A6A6A"))
            else:
                line = f"{call_line}  [#E06C75]✖ {error}[/#E06C75]"
                self._rich_log.write(Text.from_markup(line))
        else:
            line = f"{call_line}  [dim]→ ok[/dim]"
            self._rich_log.write(Text.from_markup(line))

    def _on_system_event(self, data: dict[str, Any]) -> None:
        message = data.get("message", "")
        text = Text(message, style="dim #5A5A6A")
        self._rich_log.write(text)

    def _on_prompt_error(self, data):
        self._error_active = True
        self._error_line_start = len(self._rich_log.lines)
        msg = data.get('error', 'Unknown error')
        self._rich_log.write(
            Text(f"  ✖ Connection failed: {msg}", style="#E06C75")
        )
        self._rich_log.write(
            Text("    Press Enter to retry", style="dim #6A6A6A")
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
            self._rich_log.write(
                Text(f"  System fault, saved to {crash_path}", style="dim #6A6A6A")
            )
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
        args_display = f" {command}" if command else ""
        self._rich_log.write(Text.assemble(
            ("⚠", "#FFB347"),
            (f" Approve ", "#FFB347"),
            (f"{tool}{args_display}", "#D0A060"),
        ))
        self._rich_log.write(
            Text("    [y] approve  [n] deny", style="dim #6A6A6A")
        )
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
        args_display = f" {command}" if command else ""
        status = "approved" if approved else "denied"
        self._rich_log.write(
            Text(f"{tool}{args_display} → {status}", style="dim #6A6A6A")
        )
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

    def _write_boot_telemetry(self) -> None:
        if not self._rich_log:
            return
        header = Text.assemble(
            ("●", "#00F0FF"),
            (f" pacli v{__version__}", "bold #D0D0D0"),
        )
        self._rich_log.write(header)

        cwd = os.getcwd()
        branch = self._get_git_branch()
        context = Text.assemble(
            ("model: ", "#6A6A6A"),
            (self._model, "#888888"),
            (" · dir: ", "#6A6A6A"),
            (cwd, "#888888"),
            (" · branch: ", "#6A6A6A"),
            (branch, "#888888"),
        )
        self._rich_log.write(context)

    @staticmethod
    def _get_git_branch() -> str:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            branch = result.stdout.strip()
            return branch or "unknown"
        except Exception:
            return "unknown"

    def _on_prompt_submitted(self, text: str) -> None:
        if not self._rich_log:
            return
        self._rich_log.write(Text(""))
        self._rich_log.write(Text(f"▸ {text}", style="bold #B0B0C0"))

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
