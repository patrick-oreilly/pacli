# Frontend Style & Architecture Spec

## 1. Core Palette & Typography

### Background
- **Deep Space**: `#0A0A0F` — near-black base canvas.
- **Code Block Canvas**: `#0D0D14` — marginally lighter shade for code segments only.

### Accent
- **Electric Cyan**: `#00F0FF` — single accent color. Used exclusively for the cursor, the AI text left border, the input bottom line, the thinking spinner, key identifiers in code syntax highlighting, and success indicators. No second accent color in normal flow.

### Secondary Text
- **Dim Gray**: opaque gray for metadata, system events, tool call summaries, code block headers, scrollback timestamps, and the auto-scroll HUD.

### Error / Halt States
- **Amber**: Tool execution failures (collapsed single-line, replaces cyan).
- **Coral/Crimson**: Network / connection errors (actionable halt block that vanishes on retry).

### Syntax Highlighting
- **Restricted Palette**: Muted icy tones only — soft purples, pale blues, dim greens, stark whites. No full ANSI rainbow. Key identifiers pop in electric cyan.

### Typography
- No italics for body text (terminal anti-aliasing is poor). Bold for emphasis only.
- User prompts are crisp light gray, upright, `>` prefix. AI text is full opacity white.

---

## 2. Layout & Spacing

### Core Constraint
**Absolute ban on line-drawing borders, boxes, and heavy framing.** Whitespace and typography do all structural work.

### Input Area ("Floating Command Center")
- Frameless text area — no border box.
- Single glowing electric cyan bottom border line (`border-bottom: tall $accent` or equivalent).
- Floated with margin (not spanning 100% terminal width).
- Cursor: non-blinking vertical bar (`bar` style, `cursor-blink: false`).
- Sits above the bottom edge with breathing room.

### Scrollbar
- Hyper-minimal: 1-character wide vertical line.
- Dim by default, slightly brightens when actively scrolling.
- Implementation: `scrollbar-size-vertical: 0;` on RichLog, custom overlay.

### Vertical Rhythm
- **Within a turn**: zero blank lines between AI text, tool calls, and the next AI text segment. They are one thought.
- **Between turns**: exactly one blank line before the next user prompt. Negative space is the border.

---

## 3. The Multilogue Rhythm

### Conversation Turn Structure
Each turn = user prompt → continuous AI block (with zero or more tool call children).

### User Prompt (The Anchor)
- Crisp light gray, upright (no italic).
- Preceded by a minimalist `>` prefix.
- Anchors the timeline — never dimmed or italicized in current turn. Older turns may drop slightly in opacity.

### AI Stream (The Payload)
- Full opacity white text.
- Continuous solid electric cyan left border (vertical block character).
- Strict **one-character horizontal gap** between the cyan line and the text.
- The cyan border begins on the first `stream_started` and extends uninterrupted through the entire orchestration loop. It seals only when the agent yields control back to the user.

### Tool Calls (The "Sub-Loop")
- Muted gray, dim single-line summary.
- Indented further inward than the AI text — visually nested inside the AI's response block.
- Syntax: `▶ execute_shell("echo hi")`
- On success: result state dim (`→ [exit 0]`).
- On failure: result state in amber (`→ [exit 1]`).

### System Events
- Outcome-focused phrasing (`·· runtime · model switched to llama3.2`).
- Dim gray, centered or right-aligned.
- No raw command echo.

---

## 4. Interaction & Motion

### Boot Telemetry
- Compact metadata block on launch (no logo).
- `● pacli v0.1.0` in white + cyan dot.
- Context line in dim gray: `model: ...  ·  dir: ...  ·  branch: ...`
- Sits at the top of the scrollback. On first user prompt, scrolls away naturally — not pinned as a persistent header.

### Thinking Indicator
- High-framerate braille spinner in electric cyan.
- Sits flush at the bottom of the continuous AI block during tool execution.
- When the next `stream_started` fires, the spinner vanishes and text resumes seamlessly.

### Approval Gate
- Rendered as an inline amber block (not cyan) to signal a pause.
- Shows tool name, arguments, blast radius.
- Single keystroke resolution: `y` or `n` bound at Screen level — no Enter required.
- **State collapse**: On resolution, the amber block is removed from the scrollback and replaced with a standard dim tool-call line (`▶ execute_shell(...) → [approved]` or `→ [denied]`). No trace of the interactive gate remains.

### Policy Suppression
- Read-only tools (`ls`, `cat`, `git status`, `read_file`) execute silently without triggering the approval gate.
- Configured via `~/.config/pacli/config.toml`.
- Only state-mutating actions require approval.

### Network Errors (Loop Breakers)
- Muted coral/crimson inline block.
- Actionable message: `■ Connection Failed: Claude API unreachable. Press [Enter] to retry.`
- **State collapse**: on reconnection, the error block vanishes from the scrollback. No graveyard of retries.

### System Faults (Graceful Crash)
- If the orchestration loop dies due to an internal exception:
  - Clear the input box.
  - Print a single centered dim line: `·· System fault. Session saved to ~/.config/pacli/crash.log`
  - Never show a Python traceback.

### Auto-Scroll HUD
- Dim right-aligned indicator above the input area.
- When streaming and user scrolls up: `↓ 1,234 · scroll to resume` in dim text.
- When content is flowing below viewport: `● streaming below` in dim cyan.
- On scroll to bottom or Shift+G: indicator fades, viewport locks back to live tracking.
- The stream never pauses — the buffer grows silently behind the viewport.

---

## 5. Code Block Rendering

### Detection
- Heuristic backtick-pair tracking mid-stream. No deferred rendering.
- Fence language label captured on opening backtick sequence.

### Header
- Language or filename as a dim isolated header line: `▸ app.ts` or `◇ python`.
- No backticks rendered.
- Header indented slightly further than standard AI text.

### Canvas
- Background shifts to `#0D0D14` immediately after the header.
- Shift drops back to `#0A0A0F` on the closing fence.
- No borders or boxes around the code block — just the background color shift.

### Syntax Highlighting
- Restricted palette: muted icy tones only.
- Electric cyan for key identifiers / function names.

---

## Event-to-Render Map

| Orchestrator Event | Console Rendering |
|---|---|
| `stream_started` (first) | Begin continuous cyan left border. Start streaming text into AI block. |
| `stream_started` (subsequent) | Remove thinking spinner, resume streaming text into existing AI block. |
| `token_received` | Append to AI text block. Detect code fence pairs. |
| `stream_finished` | End of text segment within the continuous block. |
| `tool_result` (success) | Write dim indented tool-call line. |
| `tool_result` (error) | Write dim indented tool-call line in amber. |
| `tool_result` (denied) | Write dim indented tool-call line with `→ [denied]`. |
| `approval_required` | Render amber approval gate. Bind y/n keys. Await keystroke. |
| `approval_response` | Collapse gate → write resolved tool-call line. Unbind keys. |
| `prompt_error` | Write coral inline halt block with retry action. |
| `prompt_submitted` | Write user prompt line (`> {text}`). Start new turn. |
| System event (slash cmd) | Write centered dim log line (`·· runtime · model switched`). |
| Boot | Write telemetry block at top of scrollback. |
