import json
from unittest.mock import AsyncMock, MagicMock, patch

from pacli.adapters.ollama import OllamaAdapter
from pacli.provider import Message, TextToken, ToolCall


def make_chunk(content=None, tool_calls=None, finish_reason=None):
    from openai.types.chat import ChatCompletionChunk
    from openai.types.chat.chat_completion_chunk import (
        Choice,
        ChoiceDelta,
        ChoiceDeltaToolCall,
        ChoiceDeltaToolCallFunction,
    )

    delta_kwargs: dict = {}
    if content is not None:
        delta_kwargs["content"] = content
    if tool_calls is not None:
        delta_kwargs["tool_calls"] = [
            ChoiceDeltaToolCall(
                index=tc["index"],
                id=tc.get("id"),
                function=ChoiceDeltaToolCallFunction(
                    name=tc.get("function", {}).get("name"),
                    arguments=tc.get("function", {}).get("arguments"),
                ),
            )
            for tc in tool_calls
        ]

    delta = ChoiceDelta(**delta_kwargs)
    choice = Choice(
        delta=delta,
        finish_reason=finish_reason,
        index=0,
    )
    return ChatCompletionChunk(
        id="test-id",
        choices=[choice],
        created=123456,
        model="test-model",
        object="chat.completion.chunk",
    )


async def test_ollama_adapter_constructor():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")
    assert adapter._model == "llama3.2"
    assert adapter._client.api_key == "ollama"


async def test_ollama_adapter_implements_provider_protocol():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")
    assert hasattr(adapter, "stream_completion")
    # Verify async generator protocol: the method should be callable and return
    # an async iterator when invoked with valid arguments.
    messages = [Message(role="user", content="test")]
    result = adapter.stream_completion(messages)
    import inspect
    assert inspect.isasyncgen(result) or hasattr(result, "__aiter__")


async def test_stream_completion_yields_text_tokens():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    chunks = [
        make_chunk(content="Hello"),
        make_chunk(content=" world"),
        make_chunk(finish_reason="stop"),
    ]

    mock_stream = MagicMock()
    mock_stream.__aiter__.return_value = chunks

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    with patch.object(adapter, "_client", mock_client):
        events = []
        async for event in adapter.stream_completion(
            [Message(role="user", content="Hi")]
        ):
            events.append(event)

    assert events == [TextToken("Hello"), TextToken(" world")]


async def test_stream_completion_translates_messages():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    chunks = [make_chunk(content="ok", finish_reason="stop")]
    mock_stream = MagicMock()
    mock_stream.__aiter__.return_value = chunks

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    messages = [
        Message(role="system", content="You are helpful"),
        Message(role="user", content="Hello"),
    ]

    with patch.object(adapter, "_client", mock_client):
        events = [e async for e in adapter.stream_completion(messages)]

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "llama3.2"
    assert call_kwargs["stream"] is True
    assert call_kwargs["messages"] == [
        {"role": "system", "content": "You are helpful"},
        {"role": "user", "content": "Hello"},
    ]

    assert events == [TextToken("ok")]


async def test_stream_completion_passes_tool_schemas():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    chunks = [make_chunk(content="done", finish_reason="stop")]
    mock_stream = MagicMock()
    mock_stream.__aiter__.return_value = chunks

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    tool_schemas = [{"type": "function", "function": {"name": "get_weather"}}]

    with patch.object(adapter, "_client", mock_client):
        _ = [e async for e in adapter.stream_completion(
            [Message(role="user", content="weather?")],
            tool_schemas=tool_schemas,
        )]

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["tools"] == tool_schemas


async def test_stream_completion_yields_tool_calls():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    chunks = [
        make_chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call_",
                    "function": {"name": "get_", "arguments": None},
                }
            ]
        ),
        make_chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "abc123",
                    "function": {"name": "weather", "arguments": '{"city": "'},
                }
            ]
        ),
        make_chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": None,
                    "function": {"name": None, "arguments": 'London"}'},
                }
            ]
        ),
        make_chunk(finish_reason="tool_calls"),
    ]

    mock_stream = MagicMock()
    mock_stream.__aiter__.return_value = chunks

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    with patch.object(adapter, "_client", mock_client):
        events = []
        async for event in adapter.stream_completion(
            [Message(role="user", content="weather in London?")]
        ):
            events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], ToolCall)
    assert events[0].id == "call_abc123"
    assert events[0].name == "get_weather"
    assert events[0].args == {"city": "London"}


async def test_translate_messages_content_null_on_tool_calls():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    messages = [
        Message(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="tc1", name="search", args={"q": "test"})],
        ),
    ]
    result = adapter._translate_messages(messages)

    assert len(result) == 1
    assert result[0]["role"] == "assistant"
    assert result[0]["content"] is None
    assert result[0]["tool_calls"][0]["id"] == "tc1"


async def test_translate_messages_tool_role():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    messages = [
        Message(role="tool", content="result text", tool_call_id="tc1"),
    ]
    result = adapter._translate_messages(messages)

    assert result[0]["role"] == "tool"
    assert result[0]["content"] == "result text"
    assert result[0]["tool_call_id"] == "tc1"


async def test_stream_completion_with_tool_call_and_text():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1", model="llama3.2")

    chunks = [
        make_chunk(content="Let me check "),
        make_chunk(
            tool_calls=[
                {
                    "index": 0,
                    "id": "call_x",
                    "function": {"name": "calc", "arguments": '{"expr": "2+2"}'},
                }
            ]
        ),
        make_chunk(finish_reason="tool_calls"),
    ]

    mock_stream = MagicMock()
    mock_stream.__aiter__.return_value = chunks

    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_stream

    with patch.object(adapter, "_client", mock_client):
        events = []
        async for event in adapter.stream_completion(
            [Message(role="user", content="what is 2+2?")]
        ):
            events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], TextToken)
    assert events[0].text == "Let me check "
    assert isinstance(events[1], ToolCall)
    assert events[1].id == "call_x"
    assert events[1].name == "calc"
    assert events[1].args == {"expr": "2+2"}
