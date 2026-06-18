import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from sqlalchemy.orm import Session

from bedtimebuddy.agents.brain import BedtimeBrain
from bedtimebuddy.config import get_settings
from bedtimebuddy.db.models import ChildProfile, Household, Workspace
from bedtimebuddy.db.session import get_session_factory
from bedtimebuddy.schemas.story import ChildContext, StoryFormat, StoryRequest

app = typer.Typer(help="BedtimeBuddy — bedtime story orchestration")
story_app = typer.Typer(help="Story generation commands")
db_app = typer.Typer(help="Database commands")
slack_app = typer.Typer(help="Slack bot commands")

app.add_typer(story_app, name="story")
app.add_typer(db_app, name="db")
app.add_typer(slack_app, name="slack")

console = Console()


def _get_db() -> Session:
    return get_session_factory()()


def _ensure_dev_household(db: Session) -> tuple[Workspace, Household, ChildProfile]:
    """Create a local dev workspace/household/child if none exist."""
    workspace = db.query(Workspace).filter_by(slack_team_id="local-dev").one_or_none()
    if not workspace:
        workspace = Workspace(slack_team_id="local-dev", name="Local Dev")
        db.add(workspace)
        db.flush()

    household = (
        db.query(Household).filter_by(workspace_id=workspace.id).first()
    )
    if not household:
        household = Household(workspace_id=workspace.id, display_name="Dev Family")
        db.add(household)
        db.flush()

    child = (
        db.query(ChildProfile).filter_by(household_id=household.id).first()
    )
    if not child:
        child = ChildProfile(
            household_id=household.id,
            name="Emma",
            age_months=42,
            interests=["Bluey", "dinosaurs"],
        )
        db.add(child)
        db.commit()
        db.refresh(child)
    else:
        db.commit()

    return workspace, household, child


@story_app.command("generate")
def story_generate(
    child_name: str = typer.Option("Emma", help="Child name (uses dev profile if exists)"),
    age_months: int = typer.Option(42, help="Child age in months"),
    duration: int = typer.Option(5, "--duration", "-d", help="Target duration in minutes"),
    fmt: str = typer.Option("detailed", "--format", "-f", help="bulleted or detailed"),
    topics: str = typer.Option("", help="Comma-separated topics"),
    interests: str = typer.Option("Bluey,dinosaurs", help="Comma-separated interests"),
    no_persist: bool = typer.Option(False, help="Skip saving to database"),
):
    """Generate a bedtime story locally (no Slack required)."""
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    interest_list = [i.strip() for i in interests.split(",") if i.strip()]

    db = _get_db()
    try:
        workspace, household, child = _ensure_dev_household(db)
        if child_name != child.name:
            child = ChildProfile(
                household_id=household.id,
                name=child_name,
                age_months=age_months,
                interests=interest_list,
            )
            db.add(child)
            db.commit()
            db.refresh(child)
        else:
            age_months = child.age_months
            interest_list = list(child.interests or interest_list)

        request = StoryRequest(
            workspace_id=workspace.id,
            household_id=household.id,
            child_profile_id=child.id,
            child=ChildContext(
                id=child.id,
                name=child_name,
                age_months=age_months,
                interests=interest_list,
            ),
            duration_minutes=duration,
            format=StoryFormat(fmt),
            topics=topic_list,
        )

        brain = BedtimeBrain()
        console.print(f"[dim]Generating story via Ollama ({get_settings().ollama_model})...[/dim]")
        result = brain.generate_story(request, db=db if not no_persist else None, persist=not no_persist)

        console.print(
            Panel(
                result.story_text,
                title=f"Bedtime story for {child_name}",
                subtitle=f"~{result.target_word_count} words",
            )
        )
        if result.session_id:
            console.print(f"[dim]Saved as session {result.session_id}[/dim]")
    finally:
        db.close()


@db_app.command("migrate")
def db_migrate(
    revision: str = typer.Option("head", help="Alembic revision target"),
):
    """Run Alembic database migrations."""
    root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "alembic", "upgrade", revision]
    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]")
    result = subprocess.run(cmd, cwd=root, check=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)
    console.print("[green]Migrations applied.[/green]")


@slack_app.command("run")
def slack_run():
    """Start the Slack bot (socket mode)."""
    from bedtimebuddy.slack.app import run_socket_mode

    if not get_settings().slack_configured:
        console.print("[red]Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env[/red]")
        raise typer.Exit(1)
    console.print("[dim]Starting Slack bot (socket mode)...[/dim]")
    run_socket_mode()


if __name__ == "__main__":
    app()
