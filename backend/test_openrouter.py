from ai.analyzer.openai_analyzer import analyzer_service


def test_openai_analyzer_defaults():
    assert analyzer_service.model
    assert analyzer_service.max_score == 10
