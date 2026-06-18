import uuid

from sqlalchemy.orm import Session

from bedtimebuddy.db.models import ChildProfile, OnboardingState, OnboardingStep


def start_onboarding(state: OnboardingState) -> None:
    state.step = OnboardingStep.PENDING_KIDS_COUNT
    state.pending_data = {"children": [], "current_index": 0}
    state.updated_at = state.updated_at  # trigger onupdate if needed


def set_kids_count(state: OnboardingState, count: int) -> str:
    if count < 1 or count > 10:
        raise ValueError("Please enter a number between 1 and 10.")
    state.pending_data = {"kids_count": count, "children": [], "current_index": 0}
    state.step = OnboardingStep.PENDING_CHILD_DETAILS
    return _child_prompt(0)


def _child_prompt(index: int) -> str:
    return (
        f"*Child {index + 1}:* What's their name? "
        "(Reply with just the name, e.g. `Emma`)"
    )


def handle_child_name(state: OnboardingState, name: str) -> str:
    data = dict(state.pending_data)
    data["current_name"] = name.strip()
    state.pending_data = data
    return f"How old is {name.strip()}? (years, e.g. `3` or `3.5`)"


def handle_child_age(state: OnboardingState, age_text: str) -> str:
    data = dict(state.pending_data)
    name = data.get("current_name", "your child")
    try:
        age_years = float(age_text.strip())
        age_months = int(round(age_years * 12))
    except ValueError as exc:
        raise ValueError("Please enter a number like `3` or `3.5`.") from exc

    data["current_age_months"] = age_months
    state.pending_data = data
    return (
        f"Any interests for {name}? (comma-separated, or `skip`)\n"
        "e.g. `Bluey, dinosaurs, popsicles`"
    )


def handle_child_interests(state: OnboardingState, interests_text: str) -> tuple[str, bool]:
    data = dict(state.pending_data)
    name = data.get("current_name", "")
    age_months = data.get("current_age_months", 36)
    interests: list[str] = []
    if interests_text.strip().lower() != "skip":
        interests = [i.strip() for i in interests_text.split(",") if i.strip()]

    children = list(data.get("children", []))
    children.append({"name": name, "age_months": age_months, "interests": interests})
    data["children"] = children
    data.pop("current_name", None)
    data.pop("current_age_months", None)

    kids_count = data.get("kids_count", len(children))
    current_index = len(children)

    if current_index < kids_count:
        state.pending_data = data
        return _child_prompt(current_index), False

    state.pending_data = data
    state.step = OnboardingStep.READY
    names = ", ".join(c["name"] for c in children)
    return (
        f"All set! Profiles created for: {names}.\n"
        "Use `/bedtime story` to generate tonight's story."
    ), True


def persist_children(db: Session, household_id: uuid.UUID, state: OnboardingState) -> list[ChildProfile]:
    children_data = state.pending_data.get("children", [])
    profiles: list[ChildProfile] = []
    for child in children_data:
        profile = ChildProfile(
            household_id=household_id,
            name=child["name"],
            age_months=child["age_months"],
            interests=child.get("interests", []),
        )
        db.add(profile)
        profiles.append(profile)
    db.commit()
    for profile in profiles:
        db.refresh(profile)
    return profiles
