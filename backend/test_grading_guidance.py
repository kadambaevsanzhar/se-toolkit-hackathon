from ai.grading_guidance import GENERAL_GRADING_GUIDANCE


def test_general_grading_guidance_covers_non_math_subjects():
    guidance = GENERAL_GRADING_GUIDANCE.lower()
    assert "history" in guidance
    assert "literature" in guidance
    assert "english" in guidance
    assert "biology" in guidance
    assert "geography" in guidance
    assert "economics" in guidance
    assert "computer science" in guidance
    assert "do not apply math-only logic to every subject" in guidance
