from ai.validator.normalizer import ResponseNormalizer
from ai.validator.quantitative_checker import apply_quantitative_guardrail, run_quantitative_guardrails
from main import _should_continue_after_rejection


def test_rejected_image_has_no_score():
    result = ResponseNormalizer.normalize_rejection(
        {
            "is_academic_submission": False,
            "subject": None,
            "reason": "Unreadable image",
            "supported_action": "Please upload a clear photo of homework or a written academic answer.",
        }
    )
    assert result["suggested_score"] is None
    assert result["analysis_status"] == "rejected"
    assert result["validation_status"] == "not_applicable"


def test_validator_failure_stays_preliminary():
    analyzer = ResponseNormalizer.normalize_analyzer_success(
        {
            "is_academic_submission": True,
            "student_name": None,
            "subject": "Mathematics",
            "topic": "Algebra",
            "task_title": "Solve for x",
            "suggested_score": 10,
            "max_score": 10,
            "short_feedback": "Correct solution.",
            "strengths": ["Correct answer"],
            "mistakes": [],
            "detailed_mistakes": [],
            "improvement_suggestions": [],
            "next_steps": [],
        }
    )
    merged = ResponseNormalizer.merge_validator_result(
        analyzer,
        {"validator_failed": True, "reason": "Bad validator JSON"},
    )
    assert merged["analysis_status"] == "validator_failed"
    assert merged["is_preliminary"] is True
    assert merged["validation_status"] == "failed"


def test_validator_override_caps_wrong_quantitative_answer():
    analyzer = ResponseNormalizer.normalize_analyzer_success(
        {
            "is_academic_submission": True,
            "student_name": None,
            "subject": "Mathematics",
            "topic": "Algebra",
            "task_title": "Solve for x",
            "suggested_score": 9,
            "max_score": 10,
            "short_feedback": "Looks correct.",
            "strengths": ["Confident work", "Readable steps"],
            "mistakes": [],
            "detailed_mistakes": [],
            "improvement_suggestions": ["Check the final division carefully."],
            "next_steps": ["Practice a similar equation.", "Verify by substitution.", "Review dividing both sides."],
        }
    )
    merged = ResponseNormalizer.merge_validator_result(
        analyzer,
        {
            "is_valid": True,
            "override": True,
            "final_score": 4,
            "reason": "Final answer is wrong.",
            "validated_summary": "The final answer is incorrect.",
            "validated_mistakes": ["The last equation solves to x = 5, not x = 4."],
            "validated_detailed_mistakes": [
                {
                    "type": "Calculation error",
                    "location": "Step from 3x = 15 to x = 4",
                    "what": "15 divided by 3 was computed as 4.",
                    "why": "15 / 3 = 5, so the final answer is incorrect.",
                    "how_to_fix": "Divide 15 by 3 correctly and verify by substitution.",
                }
            ],
            "subject_confirmed": "Mathematics",
            "analysis_consistent": False,
            "final_answer_correct": False,
            "math_error_found": True,
            "error_location_correct": False,
            "error_type_correct": False,
            "explanation_specific_enough": False,
            "first_wrong_step": "Step from 3x = 15 to x = 4",
            "contradiction_found": True,
        },
    )
    assert merged["analysis_status"] == "success"
    assert merged["suggested_score"] == 4
    assert merged["short_feedback"] == "The final answer is incorrect."
    assert merged["mistakes"] == ["The last equation solves to x = 5, not x = 4."]
    assert merged["detailed_mistakes"][0]["location"] == "Step from 3x = 15 to x = 4"


def test_validator_override_replaces_bad_analyzer_detailed_mistakes():
    analyzer = ResponseNormalizer.normalize_analyzer_success(
        {
            "is_academic_submission": True,
            "student_name": None,
            "subject": "Mathematics",
            "topic": "Algebra",
            "task_title": "Solve: 3x - 4 = 11",
            "suggested_score": 6,
            "max_score": 10,
            "short_feedback": "There is an error in the transformation step.",
            "strengths": ["The goal is identified.", "The work is readable."],
            "mistakes": ["The step to 3x = 15 is wrong."],
            "detailed_mistakes": [
                {
                    "type": "Calculation error",
                    "location": "Step where 3x - 4 = 11 becomes 3x = 15",
                    "what": "The student moved the constant incorrectly.",
                    "why": "The addition was handled incorrectly.",
                    "how_to_fix": "Add 4 to both sides.",
                }
            ],
            "improvement_suggestions": ["Review the first real error before finishing the problem."],
            "next_steps": ["Practice one more equation.", "Check each step.", "Verify the final answer."],
        }
    )
    merged = ResponseNormalizer.merge_validator_result(
        analyzer,
        {
            "is_valid": True,
            "override": True,
            "final_score": 4,
            "reason": "The analyzer blamed a correct earlier step. The real error is the final division from 3x = 15 to x = 4.",
            "validated_summary": "The transformation to 3x = 15 is correct. The error occurs in the next step: 15 divided by 3 equals 5, not 4.",
            "validated_mistakes": ["The first real error is the final division from 3x = 15 to x = 4."],
            "validated_detailed_mistakes": [
                {
                    "type": "Calculation error",
                    "location": "Step from 3x = 15 to x = 4",
                    "what": "15 divided by 3 was computed incorrectly as 4.",
                    "why": "15 / 3 = 5, so x should be 5.",
                    "how_to_fix": "Divide 15 by 3 correctly and confirm by substitution.",
                }
            ],
            "subject_confirmed": "Mathematics",
            "analysis_consistent": True,
            "final_answer_correct": False,
            "math_error_found": True,
            "error_location_correct": False,
            "error_type_correct": False,
            "explanation_specific_enough": False,
            "first_wrong_step": "Step from 3x = 15 to x = 4",
            "contradiction_found": False,
        },
    )
    assert merged["mistakes"] == ["The first real error is the final division from 3x = 15 to x = 4."]
    assert merged["detailed_mistakes"][0]["location"] == "Step from 3x = 15 to x = 4"
    assert "3x = 15 is correct" in merged["short_feedback"]


def test_contradictory_strengths_are_removed_on_wrong_final_answer():
    final = ResponseNormalizer._enforce_contract(
        {
            "analysis_status": "success",
            "validation_status": "validated",
            "is_preliminary": False,
            "strengths": [
                "Correctly divided both sides by 3 to solve for x.",
                "The setup of the equation is readable.",
            ],
            "mistakes": ["Arithmetic error in dividing 15 by 3 to find x."],
            "detailed_mistakes": [
                {
                    "type": "Arithmetic Error",
                    "location": "Step from 3x = 15 to x = 4",
                    "what": "15 divided by 3 was computed incorrectly.",
                    "why": "15 / 3 = 5, not 4.",
                    "how_to_fix": "Divide 15 by 3 correctly and verify by substitution.",
                }
            ],
            "improvement_suggestions": ["Check the final division carefully."],
            "next_steps": ["Practice one more equation.", "Check by substitution.", "Review dividing both sides."],
            "final_answer_correct": False,
        }
    )
    assert all("correctly divided" not in item.lower() for item in final["strengths"])


def test_quantitative_guardrail_overrides_wrong_linear_equation_answer():
    raw_analyzer = {
        "subject": "Mathematics",
        "task_title": "Solve: 3x - 4 = 11",
        "reconstructed_task_text": "Solve: 3x - 4 = 11",
        "student_answer_text": "x = 4",
        "observed_steps": ["3x - 4 = 11", "3x = 15", "x = 4"],
    }
    final = {
        "analysis_status": "success",
        "validation_status": "validated",
        "is_preliminary": False,
        "suggested_score": 8,
        "max_score": 10,
        "short_feedback": "Looks mostly correct.",
        "strengths": ["Readable work", "Confident answer"],
        "mistakes": [],
        "detailed_mistakes": [],
        "validator_reason": "Validator missed the wrong final answer.",
        "final_answer_correct": True,
        "math_error_found": False,
        "validator_override": False,
        "is_valid": True,
    }
    guarded = apply_quantitative_guardrail(final, raw_analyzer)
    assert guarded["suggested_score"] == 4
    assert guarded["final_answer_correct"] is False
    assert guarded["math_error_found"] is True
    assert "x = 5" in guarded["short_feedback"]
    assert guarded["detailed_mistakes"][0]["location"] == "Step 'x = 4'"


def test_quantitative_guardrail_skips_correct_linear_equation_answer():
    raw_analyzer = {
        "subject": "Mathematics",
        "task_title": "Solve: 3x - 4 = 11",
        "reconstructed_task_text": "Solve: 3x - 4 = 11",
        "student_answer_text": "x = 5",
        "observed_steps": ["3x - 4 = 11", "3x = 15", "x = 5"],
    }
    final = {
        "analysis_status": "success",
        "validation_status": "validated",
        "is_preliminary": False,
        "suggested_score": 10,
        "max_score": 10,
        "short_feedback": "Correct solution.",
        "strengths": ["Correct work", "Clear steps"],
        "mistakes": [],
        "detailed_mistakes": [],
        "validator_reason": "Validator confirmed the answer.",
        "final_answer_correct": True,
        "math_error_found": False,
        "validator_override": False,
        "is_valid": True,
    }
    guarded = apply_quantitative_guardrail(final, raw_analyzer)
    assert guarded == final


def test_quantitative_guardrail_ignores_non_quantitative_case():
    raw_analyzer = {
        "subject": "History",
        "task_title": "When did the Berlin Wall fall?",
        "reconstructed_task_text": "When did the Berlin Wall fall?",
        "student_answer_text": "1987",
        "observed_steps": ["The Berlin Wall fell in 1987."],
    }
    assert run_quantitative_guardrails(raw_analyzer, {"subject": "History"}) is None


def test_short_history_answer_false_rejection_is_overridden():
    classification = {
        "is_academic_submission": False,
        "subject": "History",
        "reason": "The statement is factually incorrect as World War II started in 1939, not 1945.",
        "supported_action": "Please upload a clear photo of homework or a written academic answer.",
    }
    assert _should_continue_after_rejection(classification) is True


def test_true_non_academic_rejection_stays_rejected():
    classification = {
        "is_academic_submission": False,
        "subject": None,
        "reason": "The image does not appear to contain enough readable academic content for reliable grading.",
        "supported_action": "Please upload a clear photo of homework or a written academic answer.",
    }
    assert _should_continue_after_rejection(classification) is False
