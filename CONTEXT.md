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
