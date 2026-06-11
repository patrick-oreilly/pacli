from pathlib import Path

from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.events import EventBus
from pacli.local_sandbox import LocalSandbox
from pacli.orchestrator import Orchestrator
from pacli.policy import Policy
from pacli.tools.read_file import ReadFileTool


def main():
    workspace_root = str(Path(__file__).resolve().parent.parent)

    bus = EventBus()
    sandbox = LocalSandbox(workspace_root=workspace_root)
    policy = Policy(workspace_root=workspace_root)
    read_file_tool = ReadFileTool(sandbox=sandbox, policy=policy)

    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    orchestrator.register_tool(read_file_tool)

    app = Console(orchestrator=orchestrator, event_bus=bus)
    app.run()
