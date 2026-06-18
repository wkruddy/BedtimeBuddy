import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bedtimebuddy.db.base import Base


class OnboardingStep(str, enum.Enum):
    PENDING_KIDS_COUNT = "pending_kids_count"
    PENDING_CHILD_DETAILS = "pending_child_details"
    READY = "ready"


class StoryFormat(str, enum.Enum):
    BULLETED = "bulleted"
    DETAILED = "detailed"


class IpPolicy(str, enum.Enum):
    FAN_FICTION = "fan_fiction"
    ORIGINAL_ONLY = "original_only"


class WorkflowType(str, enum.Enum):
    BEDTIME_STORY = "bedtime_story"
    BOOK_PROJECT = "book_project"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slack_team_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    households: Mapped[list["Household"]] = relationship(back_populates="workspace")
    users: Mapped[list["User"]] = relationship(back_populates="workspace")


class Household(Base):
    __tablename__ = "households"
    __table_args__ = (Index("ix_households_workspace_id", "workspace_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["Workspace"] = relationship(back_populates="households")
    users: Mapped[list["User"]] = relationship(back_populates="household")
    children: Mapped[list["ChildProfile"]] = relationship(back_populates="household")
    story_sessions: Mapped[list["StorySession"]] = relationship(back_populates="household")
    onboarding_state: Mapped["OnboardingState | None"] = relationship(back_populates="household")
    book_projects: Mapped[list["BookProject"]] = relationship(back_populates="household")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slack_user_id", name="uq_users_workspace_slack_user"),
        Index("ix_users_workspace_household", "workspace_id", "household_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="SET NULL")
    )
    slack_user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["Workspace"] = relationship(back_populates="users")
    household: Mapped["Household | None"] = relationship(back_populates="users")


class ChildProfile(Base):
    __tablename__ = "children_profiles"
    __table_args__ = (Index("ix_children_household_id", "household_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    age_months: Mapped[int] = mapped_column(Integer, nullable=False)
    interests: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    bedroom: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    household: Mapped["Household"] = relationship(back_populates="children")
    story_sessions: Mapped[list["StorySession"]] = relationship(back_populates="child_profile")


class StorySession(Base):
    __tablename__ = "story_sessions"
    __table_args__ = (
        Index("ix_story_sessions_household_created", "household_id", "created_at"),
        Index("ix_story_sessions_workspace_household", "workspace_id", "household_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    child_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("children_profiles.id", ondelete="CASCADE"), nullable=False
    )
    workflow_type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, name="workflow_type", values_callable=lambda x: [e.value for e in x]),
        default=WorkflowType.BEDTIME_STORY,
        nullable=False,
    )
    ip_policy: Mapped[IpPolicy] = mapped_column(
        Enum(IpPolicy, name="ip_policy", values_callable=lambda x: [e.value for e in x]),
        default=IpPolicy.FAN_FICTION,
        nullable=False,
    )
    request_params: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    story_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    household: Mapped["Household"] = relationship(back_populates="story_sessions")
    child_profile: Mapped["ChildProfile"] = relationship(back_populates="story_sessions")


class OnboardingState(Base):
    __tablename__ = "onboarding_state"
    __table_args__ = (Index("ix_onboarding_household_id", "household_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    step: Mapped[OnboardingStep] = mapped_column(
        Enum(OnboardingStep, name="onboarding_step", values_callable=lambda x: [e.value for e in x]),
        default=OnboardingStep.PENDING_KIDS_COUNT,
        nullable=False,
    )
    pending_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    household: Mapped["Household"] = relationship(back_populates="onboarding_state")


class ArtStyle(Base):
    """Stub table for Phase 2 Illustrator Agent."""

    __tablename__ = "art_styles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    comfyui_workflow_json: Mapped[dict | None] = mapped_column(JSONB)
    checkpoint_ref: Mapped[str | None] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BookProject(Base):
    """Stub table for Phase 2 book pipeline."""

    __tablename__ = "book_projects"
    __table_args__ = (Index("ix_book_projects_household_id", "household_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    art_style_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("art_styles.id", ondelete="SET NULL")
    )
    title: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="draft")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    household: Mapped["Household"] = relationship(back_populates="book_projects")
    art_style: Mapped["ArtStyle | None"] = relationship()
