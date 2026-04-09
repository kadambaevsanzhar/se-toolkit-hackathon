from ai.validator.openai_validator import ollama_validator


def test_openai_validator_defaults():
    assert ollama_validator.model
