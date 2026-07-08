"""Prompt loading utilities for grounded generation."""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
GROUNDED_ANSWER_SYSTEM_PROMPT = PROMPT_DIR / "grounded_answer_system_prompt.txt"


def load_grounded_answer_system_prompt() -> str:
    """Load the reusable grounded-answer system prompt."""

    return GROUNDED_ANSWER_SYSTEM_PROMPT.read_text(encoding="utf-8").strip()
