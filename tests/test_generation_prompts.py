from backend.generation.prompts import load_grounded_answer_system_prompt


def test_load_grounded_answer_system_prompt_contains_safeguards() -> None:
    prompt = load_grounded_answer_system_prompt()

    assert "ONLY using the supplied official context" in prompt
    assert "Never invent legal rules" in prompt
    assert "not legal advice" in prompt
