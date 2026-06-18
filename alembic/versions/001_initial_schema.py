"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-06-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slack_team_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slack_team_id"),
    )
    op.create_table(
        "art_styles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("comfyui_workflow_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("checkpoint_ref", sa.String(length=255), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "households",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_households_workspace_id", "households", ["workspace_id"], unique=False)
    op.create_table(
        "children_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("age_months", sa.Integer(), nullable=False),
        sa.Column("interests", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("bedroom", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_children_household_id", "children_profiles", ["household_id"], unique=False)
    op.create_table(
        "onboarding_state",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=False),
        sa.Column(
            "step",
            sa.Enum(
                "pending_kids_count",
                "pending_child_details",
                "ready",
                name="onboarding_step",
            ),
            nullable=False,
        ),
        sa.Column("pending_data", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id"),
    )
    op.create_index("ix_onboarding_household_id", "onboarding_state", ["household_id"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=True),
        sa.Column("slack_user_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "slack_user_id", name="uq_users_workspace_slack_user"),
    )
    op.create_index("ix_users_workspace_household", "users", ["workspace_id", "household_id"], unique=False)
    op.create_table(
        "book_projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=False),
        sa.Column("art_style_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["art_style_id"], ["art_styles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_projects_household_id", "book_projects", ["household_id"], unique=False)
    op.create_table(
        "story_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=False),
        sa.Column("child_profile_id", sa.UUID(), nullable=False),
        sa.Column(
            "workflow_type",
            sa.Enum("bedtime_story", "book_project", name="workflow_type"),
            nullable=False,
        ),
        sa.Column(
            "ip_policy",
            sa.Enum("fan_fiction", "original_only", name="ip_policy"),
            nullable=False,
        ),
        sa.Column("request_params", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("story_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["child_profile_id"], ["children_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["household_id"], ["households.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_story_sessions_household_created",
        "story_sessions",
        ["household_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_story_sessions_workspace_household",
        "story_sessions",
        ["workspace_id", "household_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_story_sessions_workspace_household", table_name="story_sessions")
    op.drop_index("ix_story_sessions_household_created", table_name="story_sessions")
    op.drop_table("story_sessions")
    op.drop_index("ix_book_projects_household_id", table_name="book_projects")
    op.drop_table("book_projects")
    op.drop_index("ix_users_workspace_household", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_onboarding_household_id", table_name="onboarding_state")
    op.drop_table("onboarding_state")
    op.drop_index("ix_children_household_id", table_name="children_profiles")
    op.drop_table("children_profiles")
    op.drop_index("ix_households_workspace_id", table_name="households")
    op.drop_table("households")
    op.drop_table("art_styles")
    op.drop_table("workspaces")
    op.execute("DROP TYPE IF EXISTS workflow_type")
    op.execute("DROP TYPE IF EXISTS ip_policy")
    op.execute("DROP TYPE IF EXISTS onboarding_step")
