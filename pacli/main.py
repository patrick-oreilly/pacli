from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.events import EventBus
from pacli.orchestrator import Orchestrator


def main():
    bus = EventBus()
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    app = Console(orchestrator=orchestrator, event_bus=bus)
    app.run()
