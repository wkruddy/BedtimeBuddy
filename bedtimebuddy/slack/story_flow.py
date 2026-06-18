"""In-memory story request flow state keyed by Slack user ID."""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class StoryFlowState:
    step: str = "pick_child"
    child_profile_id: UUID | None = None
    duration_minutes: int | None = None
    story_format: str | None = None
    topics: list[str] = field(default_factory=list)


_flows: dict[str, StoryFlowState] = {}


def get_flow(slack_user_id: str) -> StoryFlowState:
    if slack_user_id not in _flows:
        _flows[slack_user_id] = StoryFlowState()
    return _flows[slack_user_id]


def clear_flow(slack_user_id: str) -> None:
    _flows.pop(slack_user_id, None)
