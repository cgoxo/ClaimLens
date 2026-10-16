"""The chat model client. It owns the turn format: callers build turns only with user_turn / tool_turn."""
from dataclasses import dataclass, field
from typing import Any, Protocol

from claimlens.ai import with_retries
from claimlens.chat.tools import ToolResult
from claimlens.models import ChatMessage


@dataclass
class ToolCall:
    name: str
    args: dict
    raw: Any = field(default=None, compare=False, repr=False)  # the model's own reply, kept for the next turn


@dataclass
class Final:
    args: dict  # what final_answer was called with


Step = ToolCall | Final

SUMMARY_PROMPT = """Summarise this case chat in at most 150 words, for a reviewer who will continue it later.
Keep: the facts that were established, which proposals were applied or ignored, and the open questions.
Use only what the chat says."""


class ChatModel(Protocol):
    def step(self, system: str, turns: list, tools: list[dict]) -> Step: ...
    def summarise_thread(self, messages: list[ChatMessage]) -> str: ...


def user_turn(text: str, image: bytes | None = None) -> list:
    """Turns to add for a user message (extend the turn list with it)."""
    from google.genai import types

    parts = [types.Part.from_text(text=text)]
    if image is not None:
        parts.append(types.Part.from_bytes(data=image, mime_type="image/png"))
    return [types.Content(role="user", parts=parts)]


def tool_turn(call: ToolCall, result: ToolResult) -> list:
    """Turns to add after a tool ran: the model's call, then the result (an image goes in a user part)."""
    from google.genai import types

    turns = []
    if call.raw is not None:
        turns.append(call.raw)
    turns.append(types.Content(role="user", parts=[
        types.Part.from_function_response(name=call.name, response={"result": result.text})]))
    if result.image is not None:
        turns.append(types.Content(role="user", parts=[
            types.Part.from_bytes(data=result.image, mime_type="image/png")]))
    return turns


class FakeChat:
    """Plays a script of steps in order and records the turns it was shown."""

    def __init__(self, script: list[Step]):
        self.script = list(script)
        self.seen: list[list] = []

    def step(self, system: str, turns: list, tools: list[dict]) -> Step:
        self.seen.append(list(turns))
        if self.script:
            return self.script.pop(0)
        return Final({"answer": "No answer scripted.", "citations": [], "proposals": []})

    def summarise_thread(self, messages: list[ChatMessage]) -> str:
        return "Summary."


class VertexChat:
    def __init__(self, project: str, location: str, model: str):
        from google import genai

        self.client = genai.Client(vertexai=True, project=project, location=location)
        self.model = model

    def _generate(self, contents, config):
        return with_retries(
            lambda: self.client.models.generate_content(model=self.model, contents=contents, config=config))

    def step(self, system: str, turns: list, tools: list[dict]) -> Step:
        from google.genai import types

        declarations = [types.FunctionDeclaration(
            name=t["name"], description=t["description"], parameters_json_schema=t["parameters"]) for t in tools]
        config = types.GenerateContentConfig(
            system_instruction=system, temperature=0, tools=[types.Tool(function_declarations=declarations)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        response = self._generate(turns, config)
        calls = response.function_calls or []
        if not calls:
            return Final({"answer": response.text or "", "citations": [], "proposals": []})
        call = calls[0]
        args = dict(call.args or {})
        if call.name == "final_answer":
            return Final(args)
        return ToolCall(call.name, args, raw=response.candidates[0].content)

    def summarise_thread(self, messages: list[ChatMessage]) -> str:
        from google.genai import types

        text = "\n".join(f"{m.role}: {m.text}" for m in messages)
        config = types.GenerateContentConfig(system_instruction=SUMMARY_PROMPT, temperature=0)
        return (self._generate(text, config).text or "").strip()
