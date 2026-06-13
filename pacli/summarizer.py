import logging

from pacli.provider import Message, Provider, TextToken

logger = logging.getLogger(__name__)

SUMMARIZATION_PROMPT = """Summarize the conversation so far, preserving:
- The user's original request
- Key decisions made
- File paths read or modified
- Errors encountered and how they were resolved
Be brief. Return a single paragraph."""


def estimate_tokens(messages: list[Message]) -> int:
    total = 0
    for msg in messages:
        if msg.content:
            total += len(msg.content) // 4
    return total


class Summarizer:
    def __init__(self, provider: Provider, model: str) -> None:
        self._provider = provider
        self._model = model

    async def summarize(self, messages: list[Message]) -> list[Message]:
        if hasattr(self._provider, "_model"):
            self._provider._model = self._model

        conversation_text = self._messages_to_text(messages)

        request = [
            Message(role="system", content=SUMMARIZATION_PROMPT),
            Message(role="user", content=conversation_text),
        ]

        text_chunks: list[str] = []
        async for event in self._provider.stream_completion(request, tool_schemas=None):
            if isinstance(event, TextToken):
                text_chunks.append(event.text)

        summary_text = "".join(text_chunks).strip()
        if not summary_text:
            return []

        return [Message(role="assistant", content=summary_text)]

    @staticmethod
    def _messages_to_text(messages: list[Message]) -> str:
        lines: list[str] = []
        for msg in messages:
            role = msg.role
            content = msg.content or ""
            lines.append(f"[{role}]: {content}")
        return "\n".join(lines)
