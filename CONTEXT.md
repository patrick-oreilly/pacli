# pacli: Domain Context

The coding agent CLI with an "out of this world" UI and extensible provider support.

## Language

**Provider**:
The intelligence source that powers the agent (e.g., OpenAI, Anthropic, Ollama). It consumes prompts and produces completions or tool calls.
_Avoid_: Endpoint, Backend, Model

**Adapter**:
A concrete implementation that translates between the Orchestrator's internal protocol and a specific Provider's API.
_Avoid_: Plugin, Connector, Driver

**Orchestrator**:
The state machine that manages the interaction loop between the Provider and the local environment.
_Avoid_: Loop, Manager, Driver

**Runtime**:
The underlying infrastructure that manages the lifecycle of the agent, its state, and its resources.
_Avoid_: Harness, Environment, System

**Console**:
The visual terminal interface through which the user interacts with the agent.
_Avoid_: UI, Terminal, Interface

**Session**:
A single, isolated conversation or sequence of tasks between the user and the agent.
_Avoid_: Chat, Conversation, Interaction

**Workspace**:
The collection of files, context, and environment that the agent is currently authorized to access.
_Avoid_: Project, Directory, Root

**Sandbox**:
The isolated environment where the agent executes tools and commands (e.g., Local Shell, Docker, Remote SSH).
_Avoid_: Environment, Container, Shell

**Policy**:
The set of rules and permissions that govern what the agent is allowed to do autonomously versus what requires human approval.
_Avoid_: Rules, Config, Permissions

**Reactive**:
The design philosophy where the Console responds immediately to granular events from the Orchestrator, ensuring the UI feels "alive" through streaming and animations.
_Avoid_: Synchronous, Blocking, Batch

**Message**:
A single entry in the conversation history exchanged between the user and the Provider. Each Message has a `role` (e.g., "user", "assistant", "tool") and `content`.
_Avoid_: Prompt, Turn, Entry

**Slash Command**:
A console command prefixed with `/` (e.g., `/provider ollama`, `/model llama3.2`) that changes runtime configuration mid-session without restarting pacli.
_Avoid_: Shortcut, Hotkey, Meta-command

**ToolCall**:
A request from the Provider to execute a named Tool with specific arguments. Contains `id`, `name`, and `args` matching the OpenAI tool-call schema. The Orchestrator halts token streaming, executes the Tool, and feeds the result back to the Provider as a new Message with `role: "tool"`.
_Avoid_: Function call, Action, Command

**Orchestration Loop**:
The single-shot `while True` loop in the Orchestrator that alternates between streaming completions from the Provider and executing ToolCalls. Each iteration counts as one call to the Provider. The loop terminates when the Provider emits a final text response with no ToolCalls. Default max iterations is 20, configurable via `loop_max_iterations`. On tool failure, the full error string is appended as a `role: "tool"` Message, letting the Provider self-correct. The Console's thinking indicator spans the entire loop; inline tool-call summaries appear between text blocks via `tool_used`/`tool_result` events.
_Avoid_: Recursion, Agent loop, Turn cycle

**Theme**:
The visual identity of pacli. "Deep Space" theme: near-black background (`#0A0A0F`) with a single electric cyan accent (`#00F0FF`). Stark, hyper-modern Vercel/Linear aesthetic. No box borders anywhere — whitespace and typography do all structural work.
_Avoid_: Catppuccin, Dracula, presets

**Cursor**:
A non-blinking vertical bar cursor (`bar` style, no blink). Avoids the visual noise of a flashing block.
_Avoid_: Block, Blink

**Conversation Turn**:
A single user prompt followed by zero or more AI text blocks with interleaved tool-call sub-loops. The user prompt anchors the timeline in crisp light gray with a `>` prefix. The AI text block has a continuous electric cyan left border with strict 1-character gap. Tool calls are indented as nested children inside the AI block. Exactly one blank line separates turns; no blank lines within a turn.
_Avoid_: Chat bubble, Message card

**Thinking Indicator**:
A high-framerate braille spinner or horizontal pulsing dot sequence in the electric cyan accent, displayed while the Orchestration Loop is active. Replaces the static "Loading..." or "Thinking..." label.
_Avoid_: Loading, Busy

**System Event**:
A line in the scrollback recording a Slash Command or runtime state change. Does not echo the raw command — instead shows the outcome in dim gray: `·· runtime · model switched to llama3.2`. Uses a dim technical glyph prefix. Rendered as a quiet structural fact that recedes visually when scanning for conversation. Should feel like Linear's change log, not a chat message.
_Avoid_: Command echo, Chat log, Verbose confirmation

**Tool Error**:
A failed ToolCall rendered as an inline amber line with the same structure as a successful tool call: `▶ execute_shell(...) → [exit 1]`. Collapsed single-line by default; stderr is fed to the AI but hidden from the user's scrollback. Should feel like a test failure in a CI dashboard — a datapoint, not a crash.
_Avoid_: Traceback, Stack dump, Red alert

**Connection Error**:
A halt-state inline block in muted coral/crimson when a network or provider error breaks the orchestration loop. Rendered as an actionable message (`■ Connection Failed: ... Press [Enter] to retry`) that vanishes from the scrollback once the connection resumes — no graveyard of retries.
_Avoid_: Timeout screen, Raw API error, Persistent error block

**Code Block**:
A multi-line code segment in the AI's response rendered with a dim metadata header (`▸ app.ts` or `◇ python`), a marginally lighter background (`#0D0D14`), and a restricted syntax palette that excludes jarring ANSI colors — muted icy tones (soft purples, pale blues, dim greens, stark whites) with key identifiers in electric cyan. Backticks are stripped and not rendered. Detected mid-stream via heuristic backtick-pair tracking — no deferred rendering.
_Avoid_: Plain text code, Full-ANSI rainbow, Border-boxed blocks

**Auto-Scroll HUD**:
A dim right-aligned indicator above the input area showing scroll state when the user has scrolled up during an active stream. Shows `↓ 1,234 · scroll to resume` or `● streaming below` in dim cyan when content is flowing below the viewport. Fades away when the user scrolls to max_scroll_y or presses Shift+G. The stream never pauses — the buffer grows silently behind the frozen viewport.
_Avoid_: Flash banner, Loud telemetry, Centered toast

**Continuous Turn Block**:
The rendering model for the AI's response during the Orchestration Loop. A single unbroken electric cyan left border that begins with the first `stream_started` and extends until the loop yields control back to the user. AI text sits one character from the border. Tool calls are indented further inward as child processes. The thinking spinner sits flush at the bottom of the block during tool execution; on the next `stream_started` the spinner vanishes and text resumes seamlessly. The mental model: one commit message with inline file changes.
_Avoid_: Fragmented blocks, Per-iteration separation, Chat bubbles

**System Fault**:
The graceful crash state when an internal exception halts the Orchestrator. A single centered dim line: `·· System fault. Session saved to ~/.config/pacli/crash.log`. Never shows a Python traceback to the user.
_Avoid_: Traceback, Stack dump, Crash screen

**Boot Telemetry**:
The compact metadata block shown on launch before the first conversation turn. Left-aligned, no logo. Contains a glowing cyan dot `●` followed by `pacli v<version>` in white, then a dim gray context line showing operational state (`model: ...  ·  dir: ...  ·  branch: ...`). Scrolls away naturally on the first prompt — not pinned as a persistent header.
_Avoid_: Welcome screen, Splash, Hero banner

**Approval Gate**:
The interactive inline element displayed when a ToolCall requires human approval. Rendered in vivid amber/orange (not the cyan accent) to signal a momentary pause. Shows the tool name, arguments, and blast radius. Resolved by a single keystroke (`y` or `n`) bound at the Screen level — no Enter required. After resolution, the amber gate is removed from the scrollback and replaced with a standard dim tool-call line (`▶ tool_name(args) → [approved]` or `→ [denied]`), so the scrollback history remains clean.
_Avoid_: Modal, Dialog, Confirmation prompt

**Policy Suppression**:
The practice of executing read-only tools (`ls`, `cat`, `git status`, `read_file`) silently without triggering the Approval Gate, defined via `~/.config/pacli/config.toml`. Only state-mutating actions (write file, run script, git push) require approval. The best UI is no UI.
_Avoid_: Whitelist, Allowlist, Silent mode
