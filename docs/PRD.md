# PRD: pacli - The Out-of-This-World Coding Agent CLI

## Problem Statement

Developers lack a highly polished, "alive," and extensible coding agent CLI that feels "out of this world" while providing a secure and effective harness for tool execution across various LLM providers. Current solutions often feel static, are difficult to extend with new endpoints, or lack a clear separation between the UI and the execution logic.

## Solution

**pacli** is a Textual-based TUI coding agent featuring a **Reactive** **Orchestrator**, pluggable **Provider** **Adapters**, and a robust **Sandboxed** execution environment with human-in-the-loop (**HITL**) safety **Policies**. It prioritizes an "Alive" feel through real-time feedback and a sophisticated, elegant **Console**.

## User Stories

1. As a developer, I want a beautiful TUI (**Console**), so that my coding environment feels modern and "out of this world."
2. As a developer, I want real-time token streaming, so that I can see the agent's "thinking" as it happens (Alive feel).
3. As a developer, I want to plug in any LLM **Provider** (OpenAI, Anthropic, Ollama), so that I am not locked into a single intelligence source.
4. As a developer, I want a secure **Sandbox**, so that I can run agent-generated commands without risking my host system.
5. As a developer, I want human-in-the-loop (**HITL**) approval for destructive commands, so that I maintain control over my machine.
6. As a developer, I want "AcceptEdits" mode, so that I can move quickly through safe file modifications without constant prompts.
7. As a developer, I want a clear project context (**Workspace**), so that the agent understands the files it's working on.
8. As a developer, I want persistent **Sessions**, so that I can continue a task across multiple turns.
9. As a developer, I want to see pulsing status indicators for background tasks, so that I know the agent is busy even when not typing.
10. As a developer, I want easy configuration via environment variables or config files, so that I can set up my providers quickly.
11. As a developer, I want the **Orchestrator** to emit granular events, so that the UI stays **Reactive** and non-blocking.
12. As a developer, I want to switch between Local and Docker sandboxes, so that I can balance performance and isolation.

## Implementation Decisions

- **Modules**: 
    - **Console**: Built with Textual for a high-fidelity, CSS-styled TUI.
    - **Orchestrator**: An asynchronous state machine managing the intelligence loop.
    - **Provider Protocol & Adapters**: A strict protocol defining how the Orchestrator talks to LLMs, with concrete Adapters for major providers.
    - **Sandbox**: A pluggable execution layer (Local Shell, Docker).
    - **Policy Engine**: A rule-based system for gating tool execution.
- **Interfaces**: 
    - The `Provider` Protocol will be the primary extensibility point.
    - The `Sandbox` Protocol will allow for different execution backends.
- **Architectural Decision**: Asynchronous event-driven architecture using an internal event bus to decoupled the Orchestrator from the Console (see ADR-0004).
- **Security**: Mandatory HITL for shell commands by default, configurable via Policy.

## Testing Decisions

- **Seams**:
    - **Orchestrator Logic**: Tested by mocking Provider/Sandbox inputs and asserting on emitted event sequences.
    - **Adapter Translation**: Unit tests for each Adapter to ensure protocol compliance.
    - **Policy Enforcement**: Integration tests simulating high-risk actions to verify HITL triggers.
- **Standards**: Tests will focus on external behavior and contract adherence rather than internal state.

## Out of Scope

- Multi-user/Multi-tenant support.
- Native GUI applications (focused strictly on TUI/CLI).
- Cloud-hosted execution environments (focus on local/Docker-based execution).

## Further Notes

The development will follow the domain language established in `CONTEXT.md` and the architectural decisions in `docs/adr/`.
