from types import SimpleNamespace as NS

import llm


def test_reasoning_effort_only_for_gpt_oss():
    assert llm.model_options("openai/gpt-oss-120b") == {"extra_body": {"reasoning_effort": "low"}}
    assert llm.model_options("qwen/qwen3.6-27b") == {}


class FakeClient:
    """Records the kwargs passed to chat.completions.create and returns canned data."""

    def __init__(self, result):
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))
        self._result = result

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._result


def _chunk(text):
    return NS(choices=[NS(delta=NS(content=text))])


def test_chat_stream_skips_empty_chunks_and_passes_reasoning_option():
    stream = [NS(choices=[]), _chunk("Hel"), _chunk(None), _chunk("lo")]
    client = FakeClient(stream)
    assert "".join(llm.chat_stream(client, "openai/gpt-oss-120b", [])) == "Hello"
    assert client.calls[0]["stream"] is True
    assert client.calls[0]["extra_body"] == {"reasoning_effort": "low"}


def test_chat_once_returns_empty_string_when_content_is_none():
    client = FakeClient(NS(choices=[NS(message=NS(content=None))]))
    assert llm.chat_once(client, "some-other-model", []) == ""
    assert "extra_body" not in client.calls[0]
