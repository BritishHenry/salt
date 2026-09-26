"""Values returned by the Browser Use API v4."""

from dataclasses import dataclass

ACTIVE_STATUSES = frozenset({"queued", "dispatching", "running"})
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
MESSAGE_DONE_STATUSES = frozenset({"cancelled", "superseded", "failed"})

# Model ids accepted by POST /runs. Omit model to use the API default.
MODELS = (
    "glm-5.2",
    "grok-4.5",
    "grok-4.6",
    "glm-5.3-flash",
    "deepseek-v4-flash-vision",
    "kimi-k3",
    "minimax-m3",
    "claude-opus-4.7",
    "claude-opus-4.8",
    "claude-opus-5",
    "claude-fable-5",
    "claude-sonnet-5",
    "gpt-5.5",
    "gpt-5.6",
    "gpt-6-astra",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.1-pro",
    "gemini-3-flash",
)


class _UnsetType:
    def __repr__(self):
        return "UNSET"


# Distinguishes "caller did not pass this" from an explicit null.
UNSET = _UnsetType()


def _tuple(value):
    if not value:
        return ()
    return tuple(value)


@dataclass(frozen=True)
class Run:
    """A created run, or the full summary fetched after it finishes."""

    id: str
    status: str
    model: str | None = None
    session_id: str | None = None
    workspace_id: str | None = None
    events_url: str | None = None
    task: str | None = None
    title: str | None = None
    result: str | None = None
    error: str | None = None
    output: object = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_cost_usd: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    missing_file_ids: tuple[str, ...] = ()

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES

    @property
    def is_terminal(self):
        return self.status in TERMINAL_STATUSES

    @classmethod
    def from_api(cls, payload):
        return cls(
            id=payload["id"],
            status=payload["status"],
            model=payload.get("model"),
            session_id=payload.get("sessionId"),
            workspace_id=payload.get("workspaceId"),
            events_url=payload.get("eventsUrl"),
            task=payload.get("task"),
            title=payload.get("title"),
            result=payload.get("result"),
            error=payload.get("error"),
            output=payload.get("output"),
            total_input_tokens=payload.get("totalInputTokens"),
            total_output_tokens=payload.get("totalOutputTokens"),
            total_cost_usd=payload.get("totalCostUsd"),
            created_at=payload.get("createdAt"),
            updated_at=payload.get("updatedAt"),
            missing_file_ids=_tuple(payload.get("missingFileIds")),
        )


@dataclass(frozen=True)
class Session:
    """Slim view of a conversation: its latest run, without the result text."""

    session_id: str
    workspace_id: str | None
    latest_run_id: str
    task: str
    title: str | None
    status: str
    created_at: str
    updated_at: str

    @property
    def is_busy(self):
        return self.status in ACTIVE_STATUSES

    @classmethod
    def from_api(cls, payload):
        return cls(
            session_id=payload["sessionId"],
            workspace_id=payload.get("workspaceId"),
            latest_run_id=payload["latestRunId"],
            task=payload["task"],
            title=payload.get("title"),
            status=payload["status"],
            created_at=payload["createdAt"],
            updated_at=payload["updatedAt"],
        )


@dataclass(frozen=True)
class QueuedMessage:
    """A follow-up waiting on a session, or already handed to a run."""

    id: int
    session_id: str
    run_id: str | None
    mode: str
    status: str
    text: str
    created_at: str
    attached_file_ids: tuple[str, ...] = ()

    @classmethod
    def from_api(cls, payload):
        return cls(
            id=payload["id"],
            session_id=payload["sessionId"],
            run_id=payload.get("runId"),
            mode=payload["mode"],
            status=payload["status"],
            text=payload["text"],
            created_at=payload["createdAt"],
            attached_file_ids=_tuple(payload.get("attachedFileIds")),
        )


@dataclass(frozen=True)
class RunEvent:
    """One ordered event from a run."""

    id: int
    run_id: str
    ts: str
    type: str
    data: dict

    @classmethod
    def from_api(cls, payload):
        return cls(
            id=payload["id"],
            run_id=payload["runId"],
            ts=payload["ts"],
            type=payload["type"],
            data=payload.get("data") or {},
        )


@dataclass(frozen=True)
class EventPage:
    events: tuple[RunEvent, ...]
    next_after: int | None
    has_more: bool

    @classmethod
    def from_api(cls, payload):
        return cls(
            events=tuple(RunEvent.from_api(item) for item in payload.get("events", ())),
            next_after=payload.get("nextAfter"),
            has_more=bool(payload.get("hasMore", False)),
        )


@dataclass(frozen=True)
class CloudBrowser:
    """A managed browser attached to an agent session."""

    id: str
    status: str
    live_url: str | None = None
    cdp_url: str | None = None
    agent_session_id: str | None = None
    recording_url: str | None = None
    recording_available: bool = True

    @classmethod
    def from_api(cls, payload):
        return cls(
            id=payload["id"],
            status=payload["status"],
            live_url=payload.get("liveUrl"),
            cdp_url=payload.get("cdpUrl"),
            agent_session_id=payload.get("agentSessionId"),
            recording_url=payload.get("recordingUrl"),
            recording_available=payload.get("recordingAvailable", True),
        )


@dataclass(frozen=True)
class Assignment:
    """A task handed to a browser agent, either as a run or a queued message."""

    session_id: str
    run: Run | None = None
    message: QueuedMessage | None = None
