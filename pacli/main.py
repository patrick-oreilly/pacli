from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.orchestrator import Orchestrator


def main():
    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter)
    app = Console(orchestrator=orchestrator)
    app.run()
