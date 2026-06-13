from pacli.adapters.mock import MockAdapter
from pacli.events import EventBus, EventType
from pacli.orchestrator import Orchestrator
from pacli.provider import Message, TextToken
from pacli.summarizer import Summarizer, estimate_tokens


def test_estimate_tokens_empty():
    assert estimate_tokens([]) == 0


def test_estimate_tokens_no_content():
    msgs = [Message(role="user", content=None)]
    assert estimate_tokens(msgs) == 0


def test_estimate_tokens_basic():
    msgs = [Message(role="user", content="hello world")]
    assert estimate_tokens(msgs) == len("hello world") // 4


def test_estimate_tokens_multiple():
    msgs = [
        Message(role="user", content="first message"),
        Message(role="assistant", content="second reply"),
    ]
    expected = (len("first message") // 4) + (len("second reply") // 4)
    assert estimate_tokens(msgs) == expected


async def test_summarizer_compresses_input():
    """Summary should be shorter than input (fewer estimated tokens)."""

    class ShortSummaryProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            yield TextToken(text="short summary")

    provider = ShortSummaryProvider()
    summarizer = Summarizer(provider, "test-model")

    messages = [
        Message(role="user", content="long " * 500),
        Message(role="assistant", content="reply " * 500),
    ]

    result = await summarizer.summarize(messages)
    input_tokens = estimate_tokens(messages)
    output_tokens = estimate_tokens(result)

    assert len(result) == 1
    assert result[0].role == "assistant"
    assert output_tokens < input_tokens


async def test_summarizer_empty_input_returns_empty():
    """Summarizing empty input should return empty list."""

    class EmptyProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            yield TextToken(text="")

    provider = EmptyProvider()
    summarizer = Summarizer(provider, "test-model")
    result = await summarizer.summarize([])
    assert result == []


async def test_summarizer_produces_single_assistant_message():
    """Output should be a single Message with role='assistant'."""

    class Provider:
        async def stream_completion(self, messages, tool_schemas=None):
            yield TextToken(text="This is a summary.")

    summarizer = Summarizer(Provider(), "test-model")
    result = await summarizer.summarize(
        [Message(role="user", content="hello")]
    )

    assert len(result) == 1
    assert result[0].role == "assistant"
    assert result[0].content == "This is a summary."


async def test_summarizer_disabled_when_summary_provider_none():
    """When summary_provider is None, summarization should be skipped entirely."""
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        summary_provider=None,
        summary_model="",
        max_chat_history_tokens=0,
    )

    await orchestrator.process_prompt("hello")

    summary_events = [e for e in system_events if "summarizing" in e.get("message", "")]
    assert len(summary_events) == 0
    orchestrator.cleanup()


async def test_threshold_guard_skips_when_under_limit():
    """When token count is under threshold, summarization is skipped."""
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        summary_provider=MockAdapter(),
        summary_model="test-model",
        max_chat_history_tokens=10_000_000,
    )

    await orchestrator.process_prompt("short prompt")

    summary_events = [e for e in system_events if "summarizing" in e.get("message", "")]
    assert len(summary_events) == 0
    orchestrator.cleanup()


async def test_summarizer_emits_system_event():
    """System event emitted during summarization."""
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        summary_provider=MockAdapter(),
        summary_model="test-model",
        max_chat_history_tokens=0,
    )

    await orchestrator.process_prompt("hello")

    summary_events = [e for e in system_events if "summarizing" in e.get("message", "")]
    assert len(summary_events) == 1
    assert "·· runtime · summarizing conversation" in summary_events[0]["message"]
    orchestrator.cleanup()


async def test_summarizer_stores_in_history_and_clears_conversation():
    """Summary goes into history layer and conversation is cleared."""
    bus = EventBus()

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        summary_provider=MockAdapter(),
        summary_model="test-model",
        max_chat_history_tokens=0,
    )

    await orchestrator.process_prompt("hello")

    assert len(orchestrator._chunks.history) > 0
    assert orchestrator._chunks.conversation == []
    orchestrator.cleanup()


async def test_summarizer_failure_preserves_conversation():
    """On summarizer failure, conversation is preserved and error is logged."""

    class FailingProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            raise RuntimeError("provider down")

    bus = EventBus()

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        summary_provider=FailingProvider(),
        summary_model="test-model",
        max_chat_history_tokens=0,
    )

    await orchestrator.process_prompt("hello")

    assert len(orchestrator._chunks.conversation) > 0
    assert orchestrator._chunks.history == []
    assert orchestrator._chunks.conversation[0].role == "user"
    assert orchestrator._chunks.conversation[0].content == "hello"
    orchestrator.cleanup()


async def test_summarizer_disabled_with_empty_summary_model():
    """When summary_model is empty, summarization is disabled even with a provider."""
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        summary_provider=MockAdapter(),
        summary_model="",
        max_chat_history_tokens=0,
    )

    await orchestrator.process_prompt("hello")

    summary_events = [e for e in system_events if "summarizing" in e.get("message", "")]
    assert len(summary_events) == 0
    orchestrator.cleanup()


async def test_summarizer_multi_turn_includes_history():
    """After summarization, history is included in subsequent all_messages()."""
    bus = EventBus()
    captured_messages = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_messages.append(list(messages))
            yield TextToken(text="response")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
        summary_provider=MockAdapter(),
        summary_model="test-model",
        max_chat_history_tokens=0,
    )

    await orchestrator.process_prompt("first")
    await orchestrator.process_prompt("second")

    assert len(captured_messages) == 2
    msgs1 = captured_messages[0]
    msgs2 = captured_messages[1]
    assert len(msgs1) == 1
    assert msgs1[0].role == "user"
    assert msgs1[0].content == "first"
    assert len(msgs2) >= 2
    roles2 = [m.role for m in msgs2]
    assert "assistant" in roles2
    assert "user" in roles2
    history_msg = next(m for m in msgs2 if m.role == "assistant")
    assert history_msg.content is not None
    assert len(history_msg.content) > 0
    orchestrator.cleanup()
