import os
import types
import unittest
from unittest import mock

from tests import _paths  # noqa: F401
from pipeline import anthropic_chat


def fake_sdk(response=None, error=None):
    sdk = types.SimpleNamespace()

    class APIError(Exception):
        pass

    class APIStatusError(APIError):
        def __init__(self, msg="", status_code=400, headers=None):
            super().__init__(msg)
            self.status_code = status_code
            self.response = types.SimpleNamespace(headers=headers or {})

    for name in ("RateLimitError", "InternalServerError", "AuthenticationError",
                 "PermissionDeniedError", "BadRequestError"):
        setattr(sdk, name, type(name, (APIStatusError,), {}))
    sdk.APIStatusError = APIStatusError
    sdk.APIConnectionError = type("APIConnectionError", (APIError,), {})
    sdk.APITimeoutError = type("APITimeoutError", (sdk.APIConnectionError,), {})
    calls = []

    class Messages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if error is not None:
                raise error(sdk)
            return response

    class Anthropic:
        def __init__(self, **kwargs):
            self.init = kwargs
            self.messages = Messages()

    sdk.Anthropic = Anthropic
    sdk.calls = calls
    return sdk


def ok_response(text='```json\n{"a": 1}\n```', stop="end_turn"):
    return types.SimpleNamespace(
        id="msg_1", _request_id="req_1", model="claude-haiku-4-5", stop_reason=stop,
        content=[types.SimpleNamespace(type="text", text=text)],
        usage=types.SimpleNamespace(input_tokens=100, output_tokens=20,
                                    cache_read_input_tokens=30, cache_creation_input_tokens=0))


class AnthropicChatTests(unittest.TestCase):
    def test_no_key_returns_none(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertIsNone(anthropic_chat.build_anthropic_chat({}))

    def test_success_maps_usage_and_strips_fences(self):
        sdk = fake_sdk(ok_response())
        chat = anthropic_chat.build_anthropic_chat({"api_key": "k"}, sdk=sdk)
        result = chat.complete([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}],
                               max_tokens=64, response_format="json")
        self.assertEqual(result.text, '{"a": 1}')
        self.assertEqual((result.input_tokens, result.cached_input_tokens, result.output_tokens), (130, 30, 20))
        self.assertEqual(result.request_id, "req_1")
        self.assertEqual(result.model, "claude-haiku-4-5")
        sent = sdk.calls[0]
        self.assertEqual(sent["model"], "claude-haiku-4-5")
        self.assertNotIn("thinking", sent)
        self.assertTrue(sent["system"].startswith("S"))
        self.assertEqual(sent["messages"], [{"role": "user", "content": "U"}])

    def test_sdk_retries_disabled(self):
        chat = anthropic_chat.build_anthropic_chat({"api_key": "k"}, sdk=fake_sdk(ok_response()))
        self.assertEqual(chat._client.init["max_retries"], 0)

    def test_error_mapping(self):
        _, Transient, Invalid = anthropic_chat._errors()
        Base = anthropic_chat._errors()[0]
        cases = [
            (lambda s: s.RateLimitError("slow", 429, {"retry-after": "7"}), Transient),
            (lambda s: s.InternalServerError("boom", 500), Transient),
            (lambda s: s.APITimeoutError("t"), Transient),
            (lambda s: s.BadRequestError("bad json", 400), Invalid),
            (lambda s: s.BadRequestError("Your credit balance is too low", 400), Base),
            (lambda s: s.AuthenticationError("no", 401), Base),
        ]
        for make, expected in cases:
            chat = anthropic_chat.build_anthropic_chat({"api_key": "k"}, sdk=fake_sdk(error=make))
            with self.assertRaises(expected) as ctx:
                chat.complete([{"role": "user", "content": "x"}], max_tokens=8)
            if expected is Base:
                self.assertNotIsInstance(ctx.exception, (Transient, Invalid))
        chat = anthropic_chat.build_anthropic_chat({"api_key": "k"},
                                                   sdk=fake_sdk(error=cases[0][0]))
        with self.assertRaises(Transient) as ctx:
            chat.complete([{"role": "user", "content": "x"}], max_tokens=8)
        self.assertEqual(ctx.exception.retry_after, 7.0)

    def test_truncation_is_invalid(self):
        _, _, Invalid = anthropic_chat._errors()
        chat = anthropic_chat.build_anthropic_chat({"api_key": "k"}, sdk=fake_sdk(ok_response(stop="max_tokens")))
        with self.assertRaises(Invalid):
            chat.complete([{"role": "user", "content": "x"}], max_tokens=8)


if __name__ == "__main__":
    unittest.main()
