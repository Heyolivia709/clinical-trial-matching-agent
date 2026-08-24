"""Model inference behind one interface, with three adapters.

Specification sections 12 and 16. The adapter interface is the engineering
claim, not the model choice: a run made against a hosted model has to be
replayable months later by someone with no key, and a published trace that
cannot be re-run is a screenshot.

`FrozenReplayModel` is what makes that true. It answers from a recorded
transcript and raises when a request was never recorded, so a prompt change
breaks replay loudly rather than quietly producing something new.

**Keyed by request identity, not by prompt text.** Replay looks a response up by
what was being asked — purpose, criterion, proposition, attempt — rather than by
a hash of the prompt. Hashing would be stricter and would make every prompt
edit invalidate every recorded run, which turns a transcript into something
nobody re-records. The prompt is recorded beside the response, so a drift is
visible; it just is not fatal.

A model call that fails is an Infrastructure Failure and is raised as one. It
never becomes a Criterion State: scoring a broken endpoint as correct
uncertainty would pay the benchmark for its own outages, and that is a release
gate.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol, cast

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.run import ModelAdapter, ModelConfiguration
from ctma.domain.trace import FailureKind, InfrastructureFailure, Measurements


class ModelPurpose(StrEnum):
    """What a call is for. Part of the replay key, and recorded in the trace."""

    TOOL_SELECTION = "tool_selection"
    ASSESSMENT = "assessment"
    CORRECTION = "correction"


class ModelRequest(Frozen):
    """One call: what is being asked, about what, and on which attempt."""

    purpose: ModelPurpose
    criterion_id: str = Field(min_length=1)
    proposition_id: str = Field(min_length=1)
    attempt: int = Field(default=1, ge=1)
    prompt: str = Field(min_length=1)

    @property
    def key(self) -> str:
        """The replay key: readable, stable, and independent of prompt wording."""
        return f"{self.purpose.value}|{self.criterion_id}|{self.proposition_id}|{self.attempt}"


class ModelResponse(Frozen):
    """What came back, and what it cost."""

    json_text: str = Field(min_length=1)
    measurements: Measurements = Measurements()


class ModelUnavailableError(RuntimeError):
    """The model could not be reached or would not answer.

    Carries an `InfrastructureFailure` rather than a Criterion State, because
    the two must not travel through the same channel (section 8.2).
    """

    def __init__(self, failure: InfrastructureFailure) -> None:
        super().__init__(failure.detail)
        self.failure = failure


class ModelClient(Protocol):
    """The whole model surface the agent may use."""

    @property
    def configuration(self) -> ModelConfiguration: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...


class RecordedCall(Frozen):
    """One request and its response, as a run recorded them."""

    key: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    json_text: str = Field(min_length=1)
    measurements: Measurements = Measurements()


class FrozenReplayModel:
    """Answers from a recorded transcript, and only from one."""

    def __init__(
        self, calls: Mapping[str, RecordedCall], *, configuration: ModelConfiguration
    ) -> None:
        self._calls = dict(calls)
        self._configuration = configuration
        self.requests: list[ModelRequest] = []
        """Every request made, in order. The prompts the model was handed are
        what a test asserts against when it checks that the packet withheld the
        Bundle, the trial record, and the manifest."""

    @property
    def configuration(self) -> ModelConfiguration:
        return self._configuration

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        recorded = self._calls.get(request.key)
        if recorded is None:
            raise ModelUnavailableError(
                InfrastructureFailure(
                    kind=FailureKind.MODEL_UNAVAILABLE,
                    detail=f"no recorded response for {request.key}",
                    where="frozen_replay",
                )
            )
        return ModelResponse(json_text=recorded.json_text, measurements=recorded.measurements)

    @classmethod
    def from_transcript(
        cls, calls: tuple[RecordedCall, ...], *, configuration: ModelConfiguration
    ) -> FrozenReplayModel:
        return cls({call.key: call for call in calls}, configuration=configuration)


class HostedModel:
    """A hosted chat endpoint, spoken to over plain HTTP.

    Two small JSON posts do not need a vendor SDK, and the dependency the
    specification cares about is the interface above, not the transport.
    """

    def __init__(
        self,
        *,
        configuration: ModelConfiguration,
        endpoint: str,
        api_key: str,
        timeout_s: float = 60.0,
    ) -> None:
        self._configuration = configuration
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout_s = timeout_s

    @property
    def configuration(self) -> ModelConfiguration:
        return self._configuration

    def complete(self, request: ModelRequest) -> ModelResponse:
        payload = {
            "model": self._configuration.model_id,
            "max_tokens": self._configuration.max_output_tokens,
            "temperature": self._configuration.temperature,
            "top_p": self._configuration.top_p,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }
        started = time.monotonic()
        body = _post_json(self._endpoint, payload, headers, self._timeout_s, where="hosted")
        content = cast(list[Any], body.get("content") or [])
        blocks = [cast(Mapping[str, Any], part) for part in content if isinstance(part, dict)]
        text = "".join(str(block.get("text", "")) for block in blocks).strip()
        usage = cast(Mapping[str, Any], body.get("usage") or {})
        return _response(text, usage, started, where="hosted")


class LocalModel:
    """An OpenAI-compatible endpoint on this machine, for the local run."""

    def __init__(
        self,
        *,
        configuration: ModelConfiguration,
        endpoint: str = "http://127.0.0.1:11434/v1/chat/completions",
        timeout_s: float = 120.0,
    ) -> None:
        self._configuration = configuration
        self._endpoint = endpoint
        self._timeout_s = timeout_s

    @property
    def configuration(self) -> ModelConfiguration:
        return self._configuration

    def complete(self, request: ModelRequest) -> ModelResponse:
        payload = {
            "model": self._configuration.model_id,
            "temperature": self._configuration.temperature,
            "top_p": self._configuration.top_p,
            "max_tokens": self._configuration.max_output_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        started = time.monotonic()
        body = _post_json(
            self._endpoint,
            payload,
            {"content-type": "application/json"},
            self._timeout_s,
            where="local",
        )
        choices = cast(list[Any], body.get("choices") or [])
        first = cast(Mapping[str, Any], choices[0] if choices else {})
        message = cast(Mapping[str, Any], first.get("message") or {})
        usage = cast(Mapping[str, Any], body.get("usage") or {})
        return _response(str(message.get("content", "")).strip(), usage, started, where="local")


def _post_json(
    endpoint: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_s: float,
    *,
    where: str,
) -> Mapping[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return cast(Mapping[str, Any], json.loads(response.read().decode()))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ModelUnavailableError(
            InfrastructureFailure(
                kind=FailureKind.MODEL_UNAVAILABLE,
                detail=f"{type(error).__name__}: {error}",
                where=where,
            )
        ) from error


def _response(text: str, usage: Mapping[str, Any], started: float, *, where: str) -> ModelResponse:
    if not text:
        raise ModelUnavailableError(
            InfrastructureFailure(
                kind=FailureKind.MODEL_UNAVAILABLE,
                detail="the endpoint returned an empty completion",
                where=where,
            )
        )
    return ModelResponse(
        json_text=text,
        measurements=Measurements(
            latency_ms=int((time.monotonic() - started) * 1000),
            model_calls=1,
            prompt_tokens=int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            completion_tokens=int(
                usage.get("output_tokens") or usage.get("completion_tokens") or 0
            ),
        ),
    )


REPLAY_CONFIGURATION = ModelConfiguration(
    adapter=ModelAdapter.FROZEN_REPLAY,
    model_id="frozen-replay",
    revision="transcript",
    temperature=0.0,
    top_p=1.0,
    max_output_tokens=1024,
    prompt_version="agent-prompts-v1",
    schema_version="proposed-assessment-v1",
)
"""The configuration a replayed run records. Named here so a test and a
recorded transcript cannot disagree about what produced the answers."""
