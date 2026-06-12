from pacli.adapters.mock import MockAdapter
from pacli.provider import Message, TextToken


async def test_mock_adapter_streams_tokens():
    adapter = MockAdapter()
    tokens = []
    async for event in adapter.stream_completion([Message(role="user", content="hello")]):
        tokens.append(event)
    assert tokens == [TextToken("Hello"), TextToken(" from"), TextToken(" MockAdapter!")]
