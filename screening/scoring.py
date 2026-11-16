"""
Server-side scoring for every screening tool.

All scoring, the safety check and the choice of band happen here on the
server, so nothing can be skipped or changed from the browser.
"""

from dataclasses import dataclass

from .models import ScoreBand, ScreeningTool


class ScoringError(ValueError):
    """Raised when the submitted answers are missing or invalid."""


@dataclass
class ScoreResult:
    tool: ScreeningTool
    raw_score: int
    final_score: int
    band: ScoreBand
    safety_flag: bool

    def as_session_dict(self):
        """A small dictionary used to keep an anonymous result in the session only."""
        return {
            "tool_id": self.tool.pk,
            "raw_score": self.raw_score,
            "final_score": self.final_score,
            "band_id": self.band.pk,
            "safety_flag": self.safety_flag,
        }


def validate_answers(tool, answers):
    """
    answers is a dict {question_number: value}.
    Every question must be answered with one of the tool's allowed values.
    Returns a clean dict of ints, or raises ScoringError.
    """
    questions = list(tool.questions.all())
    allowed = set(tool.choices.values_list("value", flat=True))
    if not questions or not allowed:
        raise ScoringError(f"{tool.short_name} is not set up correctly.")

    clean = {}
    for q in questions:
        value = answers.get(q.number)
        if value is None or value == "":
            raise ScoringError(f"Please answer question {q.number}.")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ScoringError(f"Question {q.number} has an invalid answer.")
        if value not in allowed:
            raise ScoringError(f"Question {q.number} has an answer outside the allowed range.")
        clean[q.number] = value
    return clean


def find_band(tool, final_score):
    band = tool.bands.filter(min_score__lte=final_score, max_score__gte=final_score).select_related("guidance").first()
    if band is None:
        raise ScoringError(f"No score band covers {final_score} for {tool.short_name}.")
    return band


def score_answers(tool, answers):
    """
    Add up the answers, apply the tool's multiplier (x4 for WHO-5) BEFORE
    looking up the band, and check the safety item (PHQ-9 item 9).
    """
    clean = validate_answers(tool, answers)
    raw = sum(clean.values())
    final = raw * tool.score_multiplier
    band = find_band(tool, final)

    safety_numbers = set(tool.questions.filter(is_safety_item=True).values_list("number", flat=True))
    safety_flag = any(clean[n] > 0 for n in safety_numbers)

    return ScoreResult(tool=tool, raw_score=raw, final_score=final, band=band, safety_flag=safety_flag)
