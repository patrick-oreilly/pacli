# 0004: Asynchronous Event-Driven Architecture for "Alive" UI

To achieve the "out of this world" and "alive" feel, we will implement an asynchronous, event-driven architecture. The **Orchestrator** will emit granular events (e.g., `token_received`, `tool_started`, `plan_updated`) over an internal bus. The **Console** will subscribe to these events to update the UI reactively without blocking the core intelligence loop. This ensures smooth animations and real-time streaming even during heavy computation or tool execution.
