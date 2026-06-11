# 0003: Pluggable Sandboxing and Safety Policy

To provide the "most effective harness," **pacli** will use a pluggable **Sandbox** architecture. This allows the agent to switch between high-performance **Local** execution (similar to Claude Code) and high-security **Docker** execution (similar to OpenHands). 

A dedicated **Policy** engine will manage safety gates, enabling "AcceptEdits" modes for fluid workflows while enforcing **Human-in-the-Loop** (HITL) approval for destructive or high-risk commands.
