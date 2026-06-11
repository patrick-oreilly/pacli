# 0002: Define Provider Interface via Protocols

To support "plugging in any endpoint," we will define a strict `Provider` protocol that the **Orchestrator** consumes. This allows us to ship first-class **Adapters** (OpenAI, Anthropic, etc.) while enabling future extensibility via a plugin system without modifying the core state machine.
