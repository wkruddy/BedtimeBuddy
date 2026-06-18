import uuid

from sqlalchemy.orm import Session

from bedtimebuddy.db.models import (
    ChildProfile,
    Household,
    OnboardingState,
    OnboardingStep,
    User,
    Workspace,
)


def get_or_create_workspace(db: Session, slack_team_id: str, team_name: str | None = None) -> Workspace:
    workspace = db.query(Workspace).filter_by(slack_team_id=slack_team_id).one_or_none()
    if workspace:
        return workspace
    workspace = Workspace(slack_team_id=slack_team_id, name=team_name)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def get_or_create_user(
    db: Session,
    workspace: Workspace,
    slack_user_id: str,
    display_name: str | None = None,
) -> User:
    user = (
        db.query(User)
        .filter_by(workspace_id=workspace.id, slack_user_id=slack_user_id)
        .one_or_none()
    )
    if user:
        if display_name and not user.display_name:
            user.display_name = display_name
            db.commit()
        return user

    household = Household(workspace_id=workspace.id, display_name=display_name or "My Family")
    db.add(household)
    db.flush()

    onboarding = OnboardingState(household_id=household.id, step=OnboardingStep.PENDING_KIDS_COUNT)
    db.add(onboarding)

    user = User(
        workspace_id=workspace.id,
        household_id=household.id,
        slack_user_id=slack_user_id,
        display_name=display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_household(db: Session, user: User) -> Household | None:
    if not user.household_id:
        return None
    return db.query(Household).filter_by(id=user.household_id).one_or_none()


def get_onboarding(db: Session, household_id: uuid.UUID) -> OnboardingState | None:
    return db.query(OnboardingState).filter_by(household_id=household_id).one_or_none()


def list_children(db: Session, household_id: uuid.UUID) -> list[ChildProfile]:
    return (
        db.query(ChildProfile)
        .filter_by(household_id=household_id)
        .order_by(ChildProfile.created_at)
        .all()
    )


def is_onboarding_complete(db: Session, household_id: uuid.UUID) -> bool:
    state = get_onboarding(db, household_id)
    return state is not None and state.step == OnboardingStep.READY
