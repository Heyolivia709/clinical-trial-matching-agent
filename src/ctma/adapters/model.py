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


def _decoding(configuration: ModelConfiguration) -> dict[str, Any]:
    """The decoding parameters that were actually requested, and no others.

    A configuration with no temperature sends none. Sending a default instead
    would make the request differ from what the run records, and some endpoints
    reject the parameter outright — a 400 that looks exactly like a malformed
    body until the response is read.
    """
    requested: dict[str, Any] = {}
    if configuration.temperature is not None:
        requested["temperature"] = configuration.temperature
    if configuration.top_p is not None:
        requested["top_p"] = configuration.top_p
    return requested


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
        pace_s: float = 0.0,
    ) -> None:
        self._configuration = configuration
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._pace_s = pace_s
        """Seconds to wait before each call. A recording run walks a whole
        scenario back to back, and firing every request as fast as urllib can
        open a socket is what turns a working endpoint into a row of reset
        connections."""

    @property
    def configuration(self) -> ModelConfiguration:
        return self._configuration

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self._pace_s:
            time.sleep(self._pace_s)
        payload: dict[str, Any] = {
            "model": self._configuration.model_id,
            "max_tokens": self._configuration.max_output_tokens,
            "messages": [{"role": "user", "content": request.prompt}],
            **_decoding(self._configuration),
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
        _refuse_if_truncated(body.get("stop_reason"), where="hosted")
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


TRANSPORT_ATTEMPTS = 4
"""How many times a dropped connection is retried before it becomes a failure.

Transport flakiness is a property of the network between here and the endpoint,
not of the model. A run reporting every reset connection as an Infrastructure
Failure would be publishing a measurement of someone's wifi; a run that retried
forever would hide a real outage. Four attempts with backoff is the line.

A refusal from the endpoint itself is never retried. An HTTP error means the
request arrived and was rejected, and sending it again changes nothing.
"""


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
    for attempt in range(1, TRANSPORT_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return cast(Mapping[str, Any], json.loads(response.read().decode()))
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:300]
            raise ModelUnavailableError(
                InfrastructureFailure(
                    kind=FailureKind.MODEL_UNAVAILABLE,
                    detail=f"HTTP {error.code}: {detail}",
                    where=where,
                )
            ) from error
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == TRANSPORT_ATTEMPTS:
                raise ModelUnavailableError(
                    InfrastructureFailure(
                        kind=FailureKind.MODEL_UNAVAILABLE,
                        detail=f"{type(error).__name__} after {attempt} attempts: {error}",
                        where=where,
                    )
                ) from error
            time.sleep(2.0 * attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def _refuse_if_truncated(stop_reason: object, *, where: str) -> None:
    """A reply cut off at the token limit is not a reply.

    Left alone it arrives downstream as malformed JSON, and the failure reads as
    "the model cannot produce valid output" when the real cause is a budget this
    code set. Naming it keeps a configuration mistake from being published as a
    model finding.
    """
    if stop_reason == "max_tokens":
        raise ModelUnavailableError(
            InfrastructureFailure(
                kind=FailureKind.MODEL_UNAVAILABLE,
                detail="the reply hit max_output_tokens and is incomplete",
                where=where,
            )
        )


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


class RecordingModel:
    """Wraps a real adapter and writes down every exchange it makes.

    A run against a hosted endpoint is worth nothing to a reader without a key
    unless it leaves a transcript, and the transcript format is the one
    `FrozenReplayModel` already reads — so a recorded run replays through the
    same path as an authored one, and every test, grading pass and report works
    on it unchanged.

    Failures are not recorded. A call that raised has no response to replay, and
    a transcript that pretended otherwise would turn an outage into an answer.
    """

    def __init__(self, inner: ModelClient) -> None:
        self._inner = inner
        self.calls: list[RecordedCall] = []

    @property
    def configuration(self) -> ModelConfiguration:
        return self._inner.configuration

    def complete(self, request: ModelRequest) -> ModelResponse:
        response = self._inner.complete(request)
        self.calls.append(
            RecordedCall(
                key=request.key,
                prompt=request.prompt,
                json_text=response.json_text,
                measurements=response.measurements,
            )
        )
        return response


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
