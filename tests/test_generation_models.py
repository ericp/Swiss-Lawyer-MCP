from backend.models.generation import CitedSource, GeneratedAnswer


def test_generated_answer_model_preserves_structured_fields() -> None:
    answer = GeneratedAnswer(
        answer="Short answer.",
        explanation="Explanation based on retrieved context.",
        procedure_steps=["Step one", "Step two"],
        important_notes=["Not legal advice."],
        cited_sources=[CitedSource(source="work.pdf", page=2, region="federal")],
        confidence="Medium",
        insufficient_context=False,
    )

    assert answer.answer == "Short answer."
    assert answer.procedure_steps == ["Step one", "Step two"]
    assert answer.cited_sources[0].source == "work.pdf"
    assert answer.confidence == "Medium"
    assert answer.insufficient_context is False
