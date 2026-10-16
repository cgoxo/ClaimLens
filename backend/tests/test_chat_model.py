from types import SimpleNamespace

from google.genai import types

from claimlens.chat.model import FakeChat, Final, ToolCall, VertexChat, tool_turn, user_turn
from claimlens.chat.tools import TOOLS, ToolResult
from claimlens.models import ChatMessage


class StubModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append((model, contents, config))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def make_chat(*responses):
    chat = VertexChat.__new__(VertexChat)
    chat.model = "m"
    chat.client = SimpleNamespace(models=StubModels(responses))
    return chat


def reply(call=None, text=None):
    part = types.Part(function_call=types.FunctionCall(name=call[0], args=call[1])) if call else types.Part(text=text)
    content = types.Content(role="model", parts=[part])
    return SimpleNamespace(
        function_calls=[part.function_call] if call else None,
        text=text,
        candidates=[SimpleNamespace(content=content)],
    )


def test_fake_returns_script_in_order():
    chat = FakeChat([ToolCall("read_page", {"page": 1}), Final({"answer": "ok"})])
    turns = user_turn("hi")
    assert chat.step("sys", turns, TOOLS) == ToolCall("read_page", {"page": 1})
    assert chat.step("sys", turns, TOOLS) == Final({"answer": "ok"})
    assert len(chat.seen) == 2
    assert chat.step("sys", turns, TOOLS) == Final(
        {"answer": "No answer scripted.", "citations": [], "proposals": []})
    assert chat.summarise_thread([]) == "Summary."


def test_vertex_maps_function_call():
    chat = make_chat(reply(call=("read_page", {"page": 2})), reply(call=("final_answer", {"answer": "x"})))
    turns = user_turn("q")
    step = chat.step("sys", turns, TOOLS)
    assert step == ToolCall("read_page", {"page": 2})
    config = chat.client.models.calls[0][2]
    assert config.temperature == 0
    assert config.automatic_function_calling.disable is True
    assert len(config.tools[0].function_declarations) == len(TOOLS)
    # the model's own content is kept ahead of the function response
    turns += tool_turn(step, ToolResult("page text"))
    assert turns[1].role == "model" and turns[1].parts[0].function_call.name == "read_page"
    assert turns[2].parts[0].function_response.name == "read_page"
    assert chat.step("sys", turns, TOOLS) == Final({"answer": "x"})


def test_vertex_text_reply_becomes_final():
    chat = make_chat(reply(text="plain"))
    assert chat.step("sys", user_turn("q"), TOOLS) == Final(
        {"answer": "plain", "citations": [], "proposals": []})


def test_vertex_retries_429(monkeypatch):
    err = Exception("busy")
    err.code = 429
    chat = make_chat(err, reply(text="ok"))
    monkeypatch.setattr("claimlens.ai.time.sleep", lambda s: None)
    assert chat.step("sys", user_turn("q"), TOOLS).args["answer"] == "ok"


def test_tool_turn_adds_image_part():
    turns = tool_turn(ToolCall("view_region", {}), ToolResult("seen", b"png"))
    assert turns[-1].role == "user"
    assert turns[-1].parts[-1].inline_data.data == b"png"
    assert len(tool_turn(ToolCall("x", {}), ToolResult("t"))) == 1


def test_vertex_summarise_thread():
    chat = make_chat(reply(text=" short "))
    msg = ChatMessage(id="1", role="reviewer", text="why?", by="a")
    assert chat.summarise_thread([msg]) == "short"
    assert "why?" in chat.client.models.calls[0][1]
