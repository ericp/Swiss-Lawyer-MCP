from backend.clarification.intent_classifier import IntentClassifier


def test_intent_classifier_detects_driving_licence_exchange() -> None:
    result = IntentClassifier().classify("I have an Italian driving licence.")

    assert result.intent == "driving_licence_exchange"
    assert "driving licence" in result.matched_keywords


def test_intent_classifier_defaults_to_immigration_when_no_keyword_matches() -> None:
    result = IntentClassifier().classify("Can I move there?")

    assert result.intent == "immigration"
    assert result.confidence == 0.25
