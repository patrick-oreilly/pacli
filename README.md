# pacli &middot; the out-of-this-world coding agent CLI

<p align="center">
  <img src="https://img.shields.io/badge/python-3.13+-blue.svg" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/status-active%20development-orange.svg" alt="Status">
</p>

A reactive, event-driven coding agent with a beautiful terminal UI. **pacli** combines the power of LLMs with tool execution — file reads, shell commands — through a polished Textual TUI featuring real-time token streaming, inline approval gates, and a "deep space" theme.

```ascii
                    ▄██████████████▄
                 ▄████████████████████▄
               ▄████████████████████████▄
              █████████████████████████████
             ████████████        ████████████
            ██████████   pacli    ██████████
            █████████   v0.1.0    █████████
             ████████   · · · ·   ████████
              █████████          █████████
               ▀████████████████████████▀
                 ▀████████████████████▀
                    ▀██████████████▀
```

---

## Features

- **Real-time token streaming** — LLM responses appear character by character with a braille spinner thinking indicator. Feels alive.
- **Pluggable providers** — `Provider` protocol with adapter pattern. Bring your own backend: Ollama, OpenAI, Anthropic, or anything that speaks the protocol.
- **Sandboxed tool execution** — Tools (read_file, execute_shell) run confined to a workspace root with configurable timeouts and output limits.
- **Human-in-the-loop approval** — A policy engine gates destructive tools. `execute_shell` requires a single keystroke (`y`/`n`) to approve. `read_file` runs silently.
- **Deep space themed console** — Near-black background with electric cyan accents, cyan left-border AI response blocks, and color-coded tool call summaries.
- **Slash commands** — Switch models (`/model <name>`) mid-session without restarting.
- **Smart auto-scroll** — Scroll up during a stream and a dim HUD shows `↓ N · scroll to resume`. The buffer grows behind the frozen viewport.
- **Graceful failure** — Connection errors render as dismissable coral blocks. System faults write to `~/.config/pacli/crash.log` — never a Python traceback in the UI.
- **Clean architecture** — EventBus decouples the Orchestrator (AI interaction loop) from the Console (Textual TUI). Every state transition is an event. Easy to test, easy to extend.

## Architecture

```
                              ┌──────────────────┐
                              │     Console      │  Textual TUI
                              │                  │  RichLog + Input
                              └────────┬─────────┘
                                       │ subscribes        emits
                                       ▼                   │
                              ┌──────────────────┐         │
                              │    EventBus      │◄────────┘
                              │                  │
                              └────────┬─────────┘
                                       │ subscribes        emits
                                       ▼                   │
                              ┌──────────────────┐         │
                              │   Orchestrator   │─────────┘
                              │  (state machine) │
                              └──┬───────┬───────┘
                                 │       │
                    ┌────────────┘       └────────────┐
                    ▼                                  ▼
           ┌───────────────┐               ┌──────────────────┐
           │   Provider    │               │  ToolRegistry     │
           │   (Adapter)   │               │  + Policy         │
           │               │               │  + Sandbox        │
           └───────────────┘               └──────────────────┘
```

**Data flow:** User prompt → Orchestrator → Provider (LLM) → stream tokens → check for tool calls → Policy gate → Sandbox execution → loop until done.

## Installation

**Requirements:** Python 3.13+, [uv](https://github.com/astral-sh/uv)

```bash
git clone https://github.com/patrick-oreilly/pacli.git
cd pacli
uv venv
source .venv/bin/activate
uv pip install -e .
```

Or run without activating a venv:

```bash
uv run pacli
```

## Usage

```bash
pacli        # launch the TUI
```

Inside the console:

| Action | How |
|--------|-----|
| Submit a prompt | Type and press **Enter** |
| Approve a tool call | Press **y** or **n** (no Enter) |
| Switch model | `/model <name>` |
| Show help | `/help` |

## Configuration

Configuration lives in `~/.config/pacli/config.toml` (coming soon). Currently, the policy is:

| Tool | Requires approval |
|------|:---:|
| `read_file` | No |
| `execute_shell` | Yes |

## Development

```bash
uv run pytest           # run tests
uv run pytest -v        # verbose output
```

### Project structure

```
pacli/
├── main.py                 # top-level entry point
├── pyproject.toml          # project metadata, deps, entry point
├── pacli/                  # main package
│   ├── main.py             # composition root
│   ├── events.py           # EventBus — async pub/sub
│   ├── provider.py         # Provider protocol, ToolCall/Message models
│   ├── orchestrator.py      # AI interaction state machine
│   ├── sandbox.py          # Sandbox protocol
│   ├── local_sandbox.py    # local filesystem + shell sandbox
│   ├── policy.py           # tool approval policy engine
│   ├── tool_registry.py    # registered tools lookup & execution
│   ├── tools/              # pluggable tools
│   │   ├── read_file.py
│   │   └── execute_shell.py
│   ├── adapters/           # provider adapter implementations
│   │   └── mock.py         # MockAdapter (dev/testing)
│   └── console/            # Textual TUI
│       └── app.py          # Console App
├── tests/                  # test suite (pytest, 33 tests)
└── docs/                   # documentation
    ├── PRD.md
    ├── FRONTEND-SPEC.md
    ├── adr/                # architecture decision records
    └── agents/             # agent workflow docs
```

## Tech Stack

| Area | Technology |
|------|-----------|
| Language | Python 3.13+ |
| TUI | [Textual](https://textual.textualize.io/) ≥ 8.0 |
| Async | asyncio |
| Package manager | [uv](https://docs.astral.sh/uv/) |
| Testing | pytest ≥ 9.0, pytest-asyncio ≥ 1.4 |

## Roadmap

- [x] Streaming token responses
- [x] Tool execution with sandboxing & approval gates
- [x] Slash commands (`/model`, `/help`)
- [ ] Real LLM provider adapters (Ollama, OpenAI, Anthropic)
- [ ] Persistent config file (`~/.config/pacli/config.toml`)
- [ ] Docker sandbox backend
- [ ] Session persistence & history
- [ ] Multi-turn conversation context management

## License

MIT
