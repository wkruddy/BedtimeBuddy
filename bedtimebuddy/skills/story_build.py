from bedtimebuddy.schemas.story import ChildContext, StoryFormat, StoryRequest
from bedtimebuddy.services.ollama import OllamaClient
from bedtimebuddy.skills.web_research import research_story_context
from bedtimebuddy.utils.duration import duration_to_word_count
from bedtimebuddy.utils.souls import load_story_souls


def build_story_prompt(request: StoryRequest, research_notes: str) -> tuple[str, str]:
    child = request.child
    target_words = duration_to_word_count(request.duration_minutes)
    age_display = f"{child.age_months // 12}y {child.age_months % 12}mo"

    format_instruction = (
        "Provide bullet-point cliff notes (5-8 bullets) the parent can skim before reading aloud."
        if request.format == StoryFormat.BULLETED
        else "Write the full story text ready for a parent to read aloud at bedtime."
    )

    topics_line = (
        f"Topics to include: {', '.join(request.topics)}."
        if request.topics
        else "No specific topics — choose something cozy and age-appropriate."
    )

    interests_line = (
        f"Child interests: {', '.join(child.interests)}."
        if child.interests
        else "No recorded interests yet."
    )

    system = load_story_souls()
    user = f"""Generate a bedtime story for {child.name} ({age_display}).

{interests_line}
{topics_line}

Target duration: {request.duration_minutes} minutes (~{target_words} words).
Format: {format_instruction}
IP policy: {request.ip_policy.value} — named characters from shows/books are allowed.

Research notes:
{research_notes}

Write only the story (or bullets). No preamble or meta-commentary."""

    return system, user


def generate_story(request: StoryRequest, ollama: OllamaClient | None = None) -> tuple[str, str, int]:
    """Story-build skill: research + LLM generation."""
    research_notes = research_story_context(request.child, request.topics, request.format)
    system, user = build_story_prompt(request, research_notes)
    client = ollama or OllamaClient()
    story_text = client.chat(system=system, user=user, temperature=0.8)
    target_words = duration_to_word_count(request.duration_minutes)
    return story_text, research_notes, target_words
