import json
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from pacli.provider import Message, ProviderEvent, TextToken, ToolCall


class OllamaAdapter:
    def __init__(self, base_url: str, model: str) -> None:
        self._client = AsyncOpenAI(base_url=base_url, api_key="ollama")
        self._model = model

    def _translate_messages(
        self, messages: list[Message]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                entry["content"] = msg.content
            elif msg.role == "assistant":
                entry["content"] = None
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result

    async def stream_completion(
        self,
        messages: list[Message],
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        openai_messages = self._translate_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": False},
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        stream = await self._client.chat.completions.create(**kwargs)

        tool_call_buffers: dict[int, dict[str, Any]] = {}

        async for chunk in stream:
            choices = chunk.choices
            if not choices:
                continue
            delta = choices[0].delta
            finish_reason = choices[0].finish_reason

            if delta is None:
                continue

            if delta.content:
                yield TextToken(text=delta.content)

            if delta.tool_calls:
                for tc_chunk in delta.tool_calls:
                    idx = tc_chunk.index
                    if idx not in tool_call_buffers:
                        tool_call_buffers[idx] = {
                            "id": "",
                            "name": "",
                            "args_str": "",
                        }
                    buf = tool_call_buffers[idx]
                    if tc_chunk.id:
                        buf["id"] += tc_chunk.id
                    func = tc_chunk.function
                    if func:
                        if func.name:
                            buf["name"] += func.name
                        if func.arguments:
                            buf["args_str"] += func.arguments

            if finish_reason == "tool_calls":
                for buf in tool_call_buffers.values():
                    try:
                        args = json.loads(buf["args_str"])
                    except json.JSONDecodeError:
                        args = {}
                    yield ToolCall(
                        id=buf["id"],
                        name=buf["name"],
                        args=args,
                    )
                tool_call_buffers.clear()
