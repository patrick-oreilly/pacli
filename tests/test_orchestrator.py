from pacli.adapters.mock import MockAdapter
from pacli.orchestrator import Orchestrator


async def test_orchestrator_pipes_prompt_through_provider():
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter)
    tokens = []
    async for token in orchestrator.process_prompt("hello"):
        tokens.append(token)
    assert tokens == ["Hello", " from", " MockAdapter!"]
