from pacli.adapters.mock import MockAdapter
from pacli.events import EventBus
from pacli.orchestrator import Orchestrator


async def test_orchestrator_emits_event_sequence():
    bus = EventBus()
    events = []
    bus.on("stream_started", lambda d: events.append("stream_started"))
    bus.on("token_received", lambda d: events.append(("token_received", d)))
    bus.on("stream_finished", lambda d: events.append("stream_finished"))

    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    await orchestrator.process_prompt("hello")
    assert events == [
        "stream_started",
        ("token_received", "Hello"),
        ("token_received", " from"),
        ("token_received", " MockAdapter!"),
        "stream_finished",
    ]
