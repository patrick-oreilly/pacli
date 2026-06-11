from pacli.events import EventBus


async def test_eventbus_emits_to_subscribed_handlers():
    bus = EventBus()
    received = []
    bus.on("test_event", lambda d: received.append(d))
    bus.emit("test_event", "hello")
    assert received == ["hello"]
