"""Model providers.

Two of them, for one reason: the pipeline must be verifiable by someone who
has no API key and will not spend money to read this repository.

  stub      -- deterministic, offline, free. Verifies the pipeline end to end.
               It is NOT evidence and cannot be: its behaviour is a hash of the
               item id, written by hand to be arm-sensitive so that the
               pipeline tests are non-vacuous. Every artefact it produces is
               stamped `provider=stub`, and `report.py` refuses to print a
               finding without saying so.
  anthropic -- the real measurement. Requires ANTHROPIC_API_KEY in the
               environment and an explicitly named model. There is no default
               model, deliberately: a recorded number must always name the
               thing that produced it.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from .arms import Arm

TEMPERATURE = 1.0

#: Large on purpose, and it costs nothing in practice: a compliant reply is
#: one to three tokens, and output is billed on tokens produced rather than
#: on the ceiling.
#:
#: Measured 2026-10-16, twice. At 32 the model truncated mid-word. At 64 it
#: returned THREE EMPTY REPLIES, each with `output_tokens` exactly 64 -- the
#: whole budget spent on non-text content (reasoning) with no answer emitted.
#: All three were flawed items, because a defective item is what makes a model
#: deliberate, so the loss concentrated on ONE POPULATION and would have
#: biased the arm comparison rather than just thinning it.
MAX_TOKENS = 1024


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    #: Why the model stopped. Recorded on every row because a reply that ran
    #: out of budget and a reply that was unreadable are different failures
    #: with different remedies, and an empty string looks identical either
    #: way. Guessing between them from `output_tokens` cost two pilot runs.
    stop_reason: str = ""


class ProviderRequestError(RuntimeError):
    """The API rejected the request for a reason other than the credential --
    an unsupported parameter, a bad model name, a rate limit. Raised instead
    of letting the SDK's exception surface as a traceback."""


class ProviderAuthError(RuntimeError):
    """The credential was rejected. Raised instead of letting the SDK's own
    exception reach the user as a traceback: a stack trace tells a reader that
    the failure was unexpected, and a rejected key is an expected failure with
    a known remedy."""


class StubProvider:
    """Offline. Abstains more readily as an arm offers more ways out."""

    name = "stub"
    is_stub = True
    model = "stub-deterministic-v1"

    #: Hand-written so that more affordance -> more declining. This encodes
    #: the expected direction so the pipeline can be tested; it is the reason
    #: stub output must never be read as a result.
    _THRESHOLD = {
        "a0_no_affordance": 0.95,
        "a1_bare_escape": 0.60,
        "a2_reason_menu": 0.45,
        "a3_category_menu": 0.35,
    }

    def complete(self, arm: Arm, prompt: str, item_id: str, population: str) -> Completion:
        digest = hashlib.sha256(item_id.encode("utf-8")).hexdigest()
        temptation = int(digest[:8], 16) / 0xFFFFFFFF
        if population == "flawed":
            temptation = min(1.0, temptation + 0.25)

        threshold = self._THRESHOLD.get(arm.arm_id, 0.5)
        if temptation > threshold:
            if arm.arm_id == "a0_no_affordance":
                text = "B"  # no way out was offered, so it forces a fit
            elif arm.arm_id == "a3_category_menu":
                text = "G"
            elif arm.arm_id == "a2_reason_menu":
                text = "UNANSWERABLE NO_CORRECT_OPTION"
            else:
                text = "UNANSWERABLE"
        else:
            text = "ACBD"[int(digest[8], 16) % 4]
        return Completion(
            text=text, input_tokens=0, output_tokens=0, stop_reason="end_turn"
        )


class AnthropicProvider:
    name = "anthropic"
    is_stub = False

    def __init__(self, model: str) -> None:
        if not model:
            raise ValueError("--model is required for the anthropic provider")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. This repository never reads a key "
                "from a file. Run the command under `with-anthropic-key`."
            )
        import anthropic  # imported here so `stub` runs with no SDK installed

        self.model = model
        self._client = anthropic.Anthropic()

    def complete(self, arm: Arm, prompt: str, item_id: str, population: str) -> Completion:
        import anthropic

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderAuthError(
                "the API rejected the credential (HTTP 401). The key in the "
                "environment is present but not valid. Nothing was recorded."
            ) from exc
        except anthropic.APIStatusError as exc:
            # Any other HTTP error from the API. Caught so that no SDK
            # exception reaches a reader as a stack trace: a traceback says
            # "this was unexpected", and a rejected request is a normal
            # failure with a message worth reading.
            raise ProviderRequestError(
                f"the API rejected the request (HTTP {exc.status_code}). "
                f"Nothing was recorded. The API said: {exc.message}"
            ) from exc
        text = "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
        return Completion(
            text=text.strip(),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason or "",
        )


def build_provider(name: str, model: str | None) -> StubProvider | AnthropicProvider:
    if name == "stub":
        return StubProvider()
    if name == "anthropic":
        return AnthropicProvider(model or "")
    raise ValueError(f"unknown provider {name!r}; expected 'stub' or 'anthropic'")
