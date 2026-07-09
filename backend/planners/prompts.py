"""Prompt loading utilities for workflow planning."""

from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
WORKFLOW_PLANNER_SYSTEM_PROMPT = PROMPT_DIR / "workflow_planner_system_prompt.txt"


def load_workflow_planner_system_prompt() -> str:
    """Load the reusable workflow planner system prompt."""

    return WORKFLOW_PLANNER_SYSTEM_PROMPT.read_text(encoding="utf-8").strip()
