WORDS_PER_MINUTE = 140


def duration_to_word_count(duration_minutes: int) -> int:
    """Estimate read-aloud word count from target duration (~140 wpm)."""
    return max(100, duration_minutes * WORDS_PER_MINUTE)
