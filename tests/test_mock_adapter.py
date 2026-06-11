from pacli.adapters.mock import MockAdapter


async def test_mock_adapter_streams_tokens():
    adapter = MockAdapter()
    tokens = []
    async for token in adapter.stream_completion("hello"):
        tokens.append(token)
    assert tokens == ["Hello", " from", " MockAdapter!"]
