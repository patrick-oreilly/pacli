from dataclasses import dataclass, field

from pacli.provider import Message


@dataclass
class ChatChunks:
    system: list[Message] = field(default_factory=list)
    context: list[Message] = field(default_factory=list)
    history: list[Message] = field(default_factory=list)
    conversation: list[Message] = field(default_factory=list)
    reminder: list[Message] = field(default_factory=list)

    def all_messages(self) -> list[Message]:
        return self.system + self.context + self.history + self.conversation + self.reminder
