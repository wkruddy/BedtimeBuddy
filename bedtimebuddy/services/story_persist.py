import uuid

from sqlalchemy.orm import Session

from bedtimebuddy.db.models import IpPolicy, StorySession, WorkflowType
from bedtimebuddy.schemas.story import StoryRequest, StoryResult


def persist_story(session: Session, request: StoryRequest, result: StoryResult) -> StorySession:
    record = StorySession(
        workspace_id=request.workspace_id,
        household_id=request.household_id,
        child_profile_id=request.child_profile_id,
        workflow_type=WorkflowType(request.workflow_type.value),
        ip_policy=IpPolicy(request.ip_policy.value),
        request_params={
            "duration_minutes": request.duration_minutes,
            "format": request.format.value,
            "topics": request.topics,
            "target_word_count": result.target_word_count,
        },
        story_text=result.story_text,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    result.session_id = record.id
    return record
