import uuid
from enum import Enum

from pydantic import BaseModel, Field


class StoryFormat(str, Enum):
    BULLETED = "bulleted"
    DETAILED = "detailed"


class IpPolicy(str, Enum):
    FAN_FICTION = "fan_fiction"
    ORIGINAL_ONLY = "original_only"


class WorkflowType(str, Enum):
    BEDTIME_STORY = "bedtime_story"
    BOOK_PROJECT = "book_project"


class ChildContext(BaseModel):
    id: uuid.UUID
    name: str
    age_months: int
    interests: list[str] = Field(default_factory=list)


class StoryRequest(BaseModel):
    workspace_id: uuid.UUID
    household_id: uuid.UUID
    child_profile_id: uuid.UUID
    child: ChildContext
    duration_minutes: int = Field(ge=1, le=30)
    format: StoryFormat = StoryFormat.DETAILED
    topics: list[str] = Field(default_factory=list)
    ip_policy: IpPolicy = IpPolicy.FAN_FICTION
    workflow_type: WorkflowType = WorkflowType.BEDTIME_STORY


class StoryResult(BaseModel):
    story_text: str
    target_word_count: int
    session_id: uuid.UUID | None = None
    research_notes: str | None = None
