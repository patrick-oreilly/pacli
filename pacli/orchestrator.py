from pacli.events import EventBus
from pacli.provider import Provider


class Orchestrator:
    def __init__(self, provider: Provider, event_bus: EventBus) -> None:
        self._provider = provider
        self._event_bus = event_bus

    async def process_prompt(self, prompt: str) -> None:
        self._event_bus.emit("stream_started")
        try:
            async for token in self._provider.stream_completion(prompt):
                self._event_bus.emit("token_received", token)
        finally:
            self._event_bus.emit("stream_finished")
