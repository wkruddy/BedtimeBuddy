import httpx

from bedtimebuddy.config import get_settings
from bedtimebuddy.schemas.story import ChildContext, StoryFormat


def research_story_context(
    child: ChildContext,
    topics: list[str],
    story_format: StoryFormat,
) -> str:
    """
    Web research skill for Story Generation agent.
    Uses configurable WEB_SEARCH_URL or returns a graceful stub.
    """
    settings = get_settings()
    query_parts = [
        f"bedtime story age {child.age_months // 12} years",
        f"interests: {', '.join(child.interests)}" if child.interests else "",
        f"topics: {', '.join(topics)}" if topics else "",
        f"format: {story_format.value}",
    ]
    query = " ".join(p for p in query_parts if p).strip()

    if settings.web_search_url:
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(settings.web_search_url, params={"q": query})
                response.raise_for_status()
                data = response.json()
            if isinstance(data, dict):
                return data.get("summary") or data.get("results") or str(data)
            return str(data)
        except httpx.HTTPError:
            pass

    age_years = child.age_months / 12
    if age_years < 1:
        age_guidance = (
            "Use simple sensory language, repetition, and soothing rhythm. "
            "Very short sentences. Focus on warmth and calm."
        )
    elif age_years < 3:
        age_guidance = (
            "Use toddler-friendly vocabulary, gentle humor, and familiar routines. "
            "Named characters from kids' shows are welcome if topics suggest them."
        )
    else:
        age_guidance = (
            "Use preschool vocabulary with light adventure and gentle humor. "
            "Named characters OK for fan-fiction bedtime stories."
        )

    topic_note = ""
    if topics:
        topic_note = f" Weave in these topics naturally: {', '.join(topics)}."

    return (
        f"[Research stub — set WEB_SEARCH_URL for live search]\n"
        f"{age_guidance}{topic_note}\n"
        f"Target format: {story_format.value}."
    )
