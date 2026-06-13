from pathlib import Path

from pacli.adapters.mock import MockAdapter
from pacli.adapters.ollama import OllamaAdapter
from pacli.config import load_config
from pacli.console.app import Console
from pacli.events import EventBus, EventType
from pacli.local_sandbox import LocalSandbox
from pacli.orchestrator import Orchestrator
from pacli.policy import Policy
from pacli.tool_registry import ToolRegistry
from pacli.tools.execute_shell import ExecuteShellTool
from pacli.tools.read_file import ReadFileTool


def main():
    cfg = load_config()
    workspace_root = str(Path(__file__).resolve().parent.parent)

    bus = EventBus()
    sandbox = LocalSandbox(workspace_root=workspace_root)
    read_file_tool = ReadFileTool(sandbox=sandbox)
    shell_tool = ExecuteShellTool(sandbox=sandbox)
    policy = Policy(requires_approval_list=cfg.approval_required_tools)

    tool_registry = ToolRegistry()
    tool_registry.register_tool(read_file_tool)
    tool_registry.register_tool(shell_tool)

    if cfg.provider == "ollama":
        provider = OllamaAdapter(base_url=cfg.base_url, model=cfg.model)
    else:
        provider = MockAdapter()

    orchestrator = Orchestrator(
        provider=provider,
        event_bus=bus,
        tool_registry=tool_registry,
        policy=policy,
        provider_factory={
            "mock": (MockAdapter,),
            "ollama": (OllamaAdapter, cfg.base_url, cfg.model),
        },
        loop_max_iterations=cfg.loop_max_iterations,
        max_reflections=cfg.max_reflections,
        system_prompt=cfg.load_system_prompt(),
        provider_name=cfg.provider,
        model_name=cfg.model,
        tools_enabled=cfg.tools_enabled,
    )

    bus.on(EventType.PROMPT_SUBMITTED, orchestrator.process_prompt)

    app = Console(event_bus=bus, model=cfg.model)
    app.run()
    orchestrator.cleanup()
