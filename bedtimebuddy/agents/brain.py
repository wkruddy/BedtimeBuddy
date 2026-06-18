from sqlalchemy.orm import Session

from bedtimebuddy.schemas.story import IpPolicy, StoryRequest, StoryResult, WorkflowType
from bedtimebuddy.services.ollama import OllamaClient
from bedtimebuddy.services.story_persist import persist_story
from bedtimebuddy.skills.story_build import generate_story


class StoryGenerationAgent:
    """Story Generation agent with story-build and web-research skills."""

    def __init__(self, ollama: OllamaClient | None = None):
        self.ollama = ollama or OllamaClient()

    def run(self, request: StoryRequest) -> StoryResult:
        story_text, research_notes, target_words = generate_story(request, self.ollama)
        return StoryResult(
            story_text=story_text,
            target_word_count=target_words,
            research_notes=research_notes,
        )


class BedtimeBrain:
    """Orchestrator: routes bedtime story requests with IP policy enforcement."""

    def __init__(self, ollama: OllamaClient | None = None):
        self.story_agent = StoryGenerationAgent(ollama)

    def generate_story(
        self,
        request: StoryRequest,
        db: Session | None = None,
        persist: bool = True,
    ) -> StoryResult:
        if request.workflow_type == WorkflowType.BEDTIME_STORY:
            request.ip_policy = IpPolicy.FAN_FICTION
        elif request.workflow_type == WorkflowType.BOOK_PROJECT:
            request.ip_policy = IpPolicy.ORIGINAL_ONLY

        result = self.story_agent.run(request)

        if persist and db is not None:
            persist_story(db, request, result)

        return result
