from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from sqlalchemy.orm import Session

from bedtimebuddy.agents.brain import BedtimeBrain
from bedtimebuddy.config import get_settings
from bedtimebuddy.db.session import get_session_factory
from bedtimebuddy.schemas.story import ChildContext, StoryFormat, StoryRequest
from bedtimebuddy.services.tenant import (
    get_onboarding,
    get_or_create_user,
    get_or_create_workspace,
    get_user_household,
    is_onboarding_complete,
    list_children,
)
from bedtimebuddy.db.models import OnboardingStep
from bedtimebuddy.slack import onboarding as onboarding_flow
from bedtimebuddy.slack.story_flow import clear_flow, get_flow

_active_onboarding: set[str] = set()
_active_story: set[str] = set()


def _active_onboarding_users() -> set[str]:
    return _active_onboarding


def create_slack_app() -> App:
    settings = get_settings()
    app = App(token=settings.slack_bot_token)
    session_factory = get_session_factory()
    brain = BedtimeBrain()

    def db_session() -> Session:
        return session_factory()

    @app.command("/bedtime")
    def bedtime_command(ack, body, client, respond, logger):
        ack()
        text = (body.get("text") or "").strip().lower()
        subcommand = text.split()[0] if text else ""

        if subcommand == "setup":
            _handle_setup(body, respond, db_session)
        elif subcommand == "story":
            _handle_story_start(body, respond, db_session)
        else:
            respond(
                "Hi! I'm BedtimeBuddy.\n"
                "• `/bedtime setup` — set up your household\n"
                "• `/bedtime story` — generate a bedtime story"
            )

    @app.event("message")
    def handle_message(event, say, logger):
        if event.get("bot_id") or event.get("subtype"):
            return
        channel_type = event.get("channel_type")
        slack_user_id = event["user"]
        text = (event.get("text") or "").strip()
        if not text:
            return

        # DM always; channels only when user has an active story/onboarding flow
        in_dm = channel_type in ("im", "mpim")
        has_flow = (
            slack_user_id in _active_onboarding_users()
            or slack_user_id in _active_story
            or get_flow(slack_user_id).step != "pick_child"
        )
        if not in_dm and not has_flow:
            return

        session = db_session()
        try:
            team_id = event.get("team") or "local"
            workspace = get_or_create_workspace(session, team_id)
            user = get_or_create_user(session, workspace, slack_user_id)
            household = get_user_household(session, user)
            if not household:
                say("Please run `/bedtime setup` first.")
                return

            onboarding = get_onboarding(session, household.id)
            if onboarding and onboarding.step != OnboardingStep.READY:
                _continue_onboarding(session, onboarding, text, say, household.id, slack_user_id)
                return

            flow = get_flow(slack_user_id)
            if flow.step != "pick_child":
                _continue_story_flow(session, workspace, household, user, flow, text, say, brain)
        finally:
            session.close()

    return app


def _handle_setup(body, respond, session_factory):
    session = session_factory()
    try:
        team = body.get("team_id") or body.get("team", {}).get("id") or "local"
        slack_user_id = body["user_id"]
        workspace = get_or_create_workspace(session, team)
        user = get_or_create_user(session, workspace, slack_user_id)
        household = get_user_household(session, user)
        if not household:
            respond("Something went wrong creating your household. Try again.")
            return

        onboarding = get_onboarding(session, household.id)
        if onboarding and onboarding.step == OnboardingStep.READY:
            children = list_children(session, household.id)
            names = ", ".join(c.name for c in children)
            respond(f"You're already set up! Children: {names}\nUse `/bedtime story` to generate.")
            return

        if onboarding:
            onboarding_flow.start_onboarding(onboarding)
            session.commit()
        _active_onboarding.add(slack_user_id)
        respond(
            "Welcome to BedtimeBuddy! Let's set up your household.\n"
            "How many children? (Reply with a number, e.g. `2`)"
        )
    finally:
        session.close()


def _continue_onboarding(session, onboarding, text, say, household_id, slack_user_id):
    try:
        if onboarding.step == OnboardingStep.PENDING_KIDS_COUNT:
            msg = onboarding_flow.set_kids_count(onboarding, int(text))
            session.commit()
            say(msg)
        elif onboarding.step == OnboardingStep.PENDING_CHILD_DETAILS:
            data = onboarding.pending_data
            if "current_name" not in data:
                msg = onboarding_flow.handle_child_name(onboarding, text)
                session.commit()
                say(msg)
            elif "current_age_months" not in data:
                msg = onboarding_flow.handle_child_age(onboarding, text)
                session.commit()
                say(msg)
            else:
                msg, done = onboarding_flow.handle_child_interests(onboarding, text)
                if done:
                    onboarding_flow.persist_children(session, household_id, onboarding)
                    _active_onboarding.discard(slack_user_id)
                session.commit()
                say(msg)
    except ValueError as exc:
        say(str(exc))


def _handle_story_start(body, respond, session_factory):
    session = session_factory()
    try:
        team = body.get("team_id") or body.get("team", {}).get("id") or "local"
        slack_user_id = body["user_id"]
        workspace = get_or_create_workspace(session, team)
        user = get_or_create_user(session, workspace, slack_user_id)
        household = get_user_household(session, user)
        if not household or not is_onboarding_complete(session, household.id):
            respond("Please complete `/bedtime setup` first.")
            return

        children = list_children(session, household.id)
        if not children:
            respond("No children found. Run `/bedtime setup` again.")
            return

        clear_flow(slack_user_id)
        flow = get_flow(slack_user_id)
        flow.step = "pick_child"
        _active_story.add(slack_user_id)
        lines = ["*Which child tonight?* Reply with the number:\n"]
        for i, child in enumerate(children, 1):
            age_y = child.age_months // 12
            age_m = child.age_months % 12
            lines.append(f"{i}. {child.name} ({age_y}y {age_m}mo)")
        respond("\n".join(lines))
    finally:
        session.close()


def _continue_story_flow(session, workspace, household, user, flow, text, say, brain):
    children = list_children(session, household.id)

    if flow.step == "pick_child":
        try:
            idx = int(text) - 1
            child = children[idx]
        except (ValueError, IndexError):
            say("Please reply with a valid number from the list.")
            return
        flow.child_profile_id = child.id
        flow.step = "duration"
        say("How long? Reply with minutes (e.g. `5`, `10`, or `15`).")
        return

    if flow.step == "duration":
        try:
            minutes = int(text)
            if minutes < 1 or minutes > 30:
                raise ValueError
        except ValueError:
            say("Please enter a number between 1 and 30.")
            return
        flow.duration_minutes = minutes
        flow.step = "format"
        say("Format? Reply `bulleted` for cliff notes or `detailed` for full read-aloud text.")
        return

    if flow.step == "format":
        fmt = text.lower()
        if fmt not in ("bulleted", "detailed"):
            say("Reply `bulleted` or `detailed`.")
            return
        flow.story_format = fmt
        flow.step = "topics"
        say("Any topics tonight? (comma-separated, or `skip` — e.g. `Bluey, popsicle walk`)")
        return

    if flow.step == "topics":
        if text.lower() != "skip":
            flow.topics = [t.strip() for t in text.split(",") if t.strip()]

        child = next(c for c in children if c.id == flow.child_profile_id)
        say(f"Generating a story for {child.name}... this may take a minute.")

        request = StoryRequest(
            workspace_id=workspace.id,
            household_id=household.id,
            child_profile_id=child.id,
            child=ChildContext(
                id=child.id,
                name=child.name,
                age_months=child.age_months,
                interests=list(child.interests or []),
            ),
            duration_minutes=flow.duration_minutes or 5,
            format=StoryFormat(flow.story_format or "detailed"),
            topics=flow.topics,
        )

        try:
            result = brain.generate_story(request, db=session, persist=True)
            clear_flow(user.slack_user_id)
            _active_story.discard(user.slack_user_id)
            say(f"*Bedtime story for {child.name}*\n\n{result.story_text}")
        except Exception as exc:
            clear_flow(user.slack_user_id)
            _active_story.discard(user.slack_user_id)
            say(f"Sorry, story generation failed: {exc}")


def run_socket_mode():
    settings = get_settings()
    if not settings.slack_configured:
        raise RuntimeError("SLACK_BOT_TOKEN and SLACK_APP_TOKEN are required for the Slack bot.")
    app = create_slack_app()
    handler = SocketModeHandler(app, settings.slack_app_token)
    handler.start()
