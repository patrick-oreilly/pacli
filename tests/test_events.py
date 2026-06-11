from pacli.events import EventBus


async def test_eventbus_emits_to_subscribed_handlers():
    bus = EventBus()
    received = []
    bus.on("test_event", lambda d: received.append(d))
    await bus.emit("test_event", "hello")
    assert received == ["hello"]


async def test_error_isolation_continues_after_exception():
    bus = EventBus()
    results = []

    def failing(_data):
        raise ValueError("boom")

    def succeeding(data):
        results.append(data)

    bus.on("test", failing)
    bus.on("test", succeeding)

    await bus.emit("test", "ok")
    assert results == ["ok"]


async def test_error_isolation_async_handler():
    bus = EventBus()
    results = []

    async def failing(_data):
        raise RuntimeError("async boom")

    def succeeding(data):
        results.append(data)

    bus.on("test", failing)
    bus.on("test", succeeding)

    await bus.emit("test", "ok")
    assert results == ["ok"]


async def test_error_isolation_does_not_propagate():
    bus = EventBus()
    bus.on("test", lambda d: (_ for _ in ()).throw(ValueError("boom")))
    await bus.emit("test", "x")
    # no exception should propagate to the caller
    assert True


async def test_concurrent_dispatch_runs_all_handlers():
    bus = EventBus()
    results = set()

    async def handler_a(data):
        results.add("a")

    async def handler_b(data):
        results.add("b")

    bus.on("test", handler_a)
    bus.on("test", handler_b)

    await bus.emit("test", "", concurrent=True)
    assert results == {"a", "b"}
