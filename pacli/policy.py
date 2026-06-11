class Policy:
    def requires_approval(self, tool_name: str) -> bool:
        return tool_name == "execute_shell"
