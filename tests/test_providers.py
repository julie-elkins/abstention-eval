"""Auth failure is an expected failure with a known remedy, so it must
surface as a refusal and an exit code -- never as a traceback."""

import pytest

from abstention_eval.providers import (
    AnthropicProvider,
    ProviderAuthError,
    ProviderRequestError,
    build_provider,
)


def test_anthropic_provider_refuses_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="with-anthropic-key"):
        AnthropicProvider("some-model")


def test_anthropic_provider_requires_a_named_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(ValueError, match="--model is required"):
        AnthropicProvider("")


def test_a_rejected_key_raises_the_domain_error_not_the_sdk_error(monkeypatch):
    import anthropic

    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-credential")
    provider = AnthropicProvider("some-model")

    import httpx

    def reject(*args, **kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.AuthenticationError(
            message="invalid x-api-key",
            response=httpx.Response(401, request=request),
            body=None,
        )

    monkeypatch.setattr(provider._client.messages, "create", reject)
    from abstention_eval.arms import ARMS

    with pytest.raises(ProviderAuthError, match="HTTP 401"):
        provider.complete(ARMS[0], "prompt", "i1", "sound")


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError, match="unknown provider"):
        build_provider("gpt", None)


def test_a_rejected_request_is_a_refusal_not_a_traceback(monkeypatch):
    """The 2026-10-16 pilot hit HTTP 400 on an unsupported parameter and the
    SDK exception reached the terminal as a stack trace. It must not."""
    import anthropic
    import httpx

    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    provider = AnthropicProvider("some-model")

    def reject(*args, **kwargs):
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        raise anthropic.BadRequestError(
            message="This model does not support assistant message prefill.",
            response=httpx.Response(400, request=request),
            body=None,
        )

    monkeypatch.setattr(provider._client.messages, "create", reject)
    from abstention_eval.arms import ARMS

    with pytest.raises(ProviderRequestError) as caught:
        provider.complete(ARMS[0], "prompt", "i1", "sound")
    assert "HTTP 400" in str(caught.value)
    assert "Nothing was recorded" in str(caught.value)
