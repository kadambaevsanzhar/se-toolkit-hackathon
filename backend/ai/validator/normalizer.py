"""Normalization helpers for analyzer + validator pipeline."""

from __future__ import annotations

import os
from typing import Any

DEFAULT_MAX_SCORE = int(os.getenv("AI_MAX_SCORE", "10"))
SUPPORTED_ACTION = "Please upload a clear photo of homework or a written academic answer."


class ResponseNormalizer:
    """Unifies analyzer, validator, and failure responses for web and Telegram."""

    @staticmethod
    def normalize_rejection(classification: dict[str, Any]) -> dict[str, Any]:
        reason = classification.get(
            "reason",
            "The image does not appear to contain enough readable academic content for reliable grading.",
        )
        return {
            "analysis_status": "rejected",
            "validation_status": "not_applicable",
            "is_preliminary": False,
            "student_name": None,
            "subject": classification.get("subject"),
            "topic": None,
            "task_title": None,
            "suggested_score": None,
            "max_score": None,
            "short_feedback": reason,
            "strengths": [],
            "mistakes": [],
            "detailed_mistakes": [],
            "improvement_suggestions": [],
            "improvement_suggestion": "",
            "next_steps": [],
            "validation_status_detail": None,
            "validator_reason": "Not applicable for rejected images.",
            "analyzer_reason": reason,
            "validator_flags": ["rejected_non_academic"],
            "is_academic_submission": False,
            "academic_rejection_reason": reason,
            "supported_action": classification.get("supported_action", SUPPORTED_ACTION),
            "is_valid": False,
            "validator_override": False,
            "final_answer_correct": None,
            "math_error_found": None,
            "contradiction_found": False,
        }

    @staticmethod
    def normalize_analyzer_success(analyzer_result: dict[str, Any]) -> dict[str, Any]:
        strengths = ResponseNormalizer._fit_strengths(analyzer_result.get("strengths"))
        mistakes = ResponseNormalizer._fit_mistakes(analyzer_result.get("mistakes"))
        detailed_mistakes = ResponseNormalizer._fit_detailed_mistakes(
            analyzer_result.get("detailed_mistakes", []),
            len(mistakes),
        )
        mistakes = mistakes[: len(detailed_mistakes)] if detailed_mistakes else mistakes[:0]
        suggestions = ResponseNormalizer._fit_improvement_suggestions(
            analyzer_result.get("improvement_suggestions")
        )
        next_steps = ResponseNormalizer._fit_next_steps(analyzer_result.get("next_steps"))
        return {
            "analysis_status": "analyzed",
            "validation_status": "pending",
            "is_preliminary": True,
            "student_name": analyzer_result.get("student_name"),
            "subject": analyzer_result.get("subject"),
            "topic": analyzer_result.get("topic"),
            "task_title": analyzer_result.get("task_title"),
            "suggested_score": analyzer_result.get("suggested_score"),
            "max_score": analyzer_result.get("max_score", DEFAULT_MAX_SCORE),
            "short_feedback": analyzer_result.get("short_feedback", ""),
            "strengths": strengths,
            "mistakes": mistakes,
            "detailed_mistakes": detailed_mistakes,
            "improvement_suggestions": suggestions,
            "improvement_suggestion": suggestions[0] if suggestions else "",
            "next_steps": next_steps,
            "validator_reason": "Validation pending.",
            "analyzer_reason": "Analyzer completed successfully.",
            "validator_flags": [],
            "is_academic_submission": True,
            "academic_rejection_reason": None,
            "supported_action": None,
            "is_valid": False,
            "validator_override": False,
            "final_answer_correct": None,
            "math_error_found": None,
            "contradiction_found": False,
        }

    @staticmethod
    def normalize_analyzer_failure(reason: str) -> dict[str, Any]:
        return {
            "analysis_status": "analyzer_failed",
            "validation_status": "failed",
            "is_preliminary": False,
            "student_name": None,
            "subject": None,
            "topic": None,
            "task_title": None,
            "suggested_score": None,
            "max_score": None,
            "short_feedback": "Technical analysis failure. Please try again later.",
            "strengths": [],
            "mistakes": [],
            "detailed_mistakes": [],
            "improvement_suggestions": [],
            "improvement_suggestion": "",
            "next_steps": [],
            "validator_reason": "Validation did not run.",
            "analyzer_reason": reason,
            "validator_flags": ["analyzer_failed"],
            "is_academic_submission": True,
            "academic_rejection_reason": None,
            "supported_action": None,
            "is_valid": False,
            "validator_override": False,
            "final_answer_correct": None,
            "math_error_found": None,
            "contradiction_found": False,
        }

    @staticmethod
    def merge_validator_result(base: dict[str, Any], validator_result: dict[str, Any]) -> dict[str, Any]:
        if validator_result.get("validator_failed"):
            final = dict(base)
            final["analysis_status"] = "validator_failed"
            final["validation_status"] = "failed"
            final["is_preliminary"] = True
            final["validator_reason"] = validator_result.get("reason", "Final validation was unavailable.")
            final["validator_flags"] = ["validator_failed"]
            return ResponseNormalizer._enforce_contract(final)

        final = dict(base)
        final["analysis_status"] = "success"
        final["validation_status"] = "validated"
        final["is_preliminary"] = False
        final["is_valid"] = bool(validator_result.get("is_valid", False))
        final["validator_override"] = bool(validator_result.get("override", False))
        final["validator_reason"] = validator_result.get("reason", "")
        final["final_answer_correct"] = validator_result.get("final_answer_correct")
        final["math_error_found"] = validator_result.get("math_error_found")
        final["contradiction_found"] = bool(validator_result.get("contradiction_found", False))
        final["subject"] = validator_result.get("subject_confirmed") or final.get("subject")

        if final["validator_override"]:
            final["suggested_score"] = validator_result.get("final_score", final.get("suggested_score"))
            final["short_feedback"] = validator_result.get("validated_summary", final.get("short_feedback"))
            final["mistakes"] = ResponseNormalizer._string_list(
                validator_result.get("validated_mistakes", final.get("mistakes", []))
            )
            final["detailed_mistakes"] = ResponseNormalizer._validator_detailed_mistakes(
                validator_result,
                final["mistakes"],
                final.get("detailed_mistakes", []),
            )

        final = ResponseNormalizer._apply_consistency_gate(final, validator_result)
        return ResponseNormalizer._enforce_contract(final)

    @staticmethod
    def should_regenerate_from_validator(base: dict[str, Any], validator_result: dict[str, Any]) -> bool:
        if validator_result.get("validator_failed"):
            return False
        if validator_result.get("contradiction_found"):
            return True
        if validator_result.get("analysis_consistent") is False:
            return True
        confirmed = validator_result.get("subject_confirmed")
        subject = base.get("subject")
        return bool(confirmed and subject and confirmed.strip().lower() != subject.strip().lower())

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        item = str(value).strip()
        return [item] if item else []

    @staticmethod
    def _fit_strengths(value: Any) -> list[str]:
        items = ResponseNormalizer._string_list(value)
        if len(items) >= 3:
            return items[:3]
        if len(items) == 2:
            return items
        if len(items) == 1:
            return items + ["Work is presented in a readable structure."]
        return ["Work addresses the visible task.", "Submission contains a visible student attempt."]

    @staticmethod
    def _fit_mistakes(value: Any) -> list[str]:
        return ResponseNormalizer._string_list(value)[:2]

    @staticmethod
    def _fit_detailed_mistakes(value: Any, expected_count: int) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            value = []
        normalized = []
        for item in value[:expected_count]:
            if not isinstance(item, dict):
                continue
            fields = {
                "type": str(item.get("type", "")).strip(),
                "location": str(item.get("location", "")).strip(),
                "what": str(item.get("what", "")).strip(),
                "why": str(item.get("why", "")).strip(),
                "how_to_fix": str(item.get("how_to_fix", "")).strip(),
            }
            if all(fields.values()):
                normalized.append(fields)
        return normalized[:expected_count]

    @staticmethod
    def _fit_improvement_suggestions(value: Any) -> list[str]:
        items = ResponseNormalizer._string_list(value)
        if items:
            return items[:1]
        return ["Review the task carefully and focus on the main correction needed."]

    @staticmethod
    def _fit_next_steps(value: Any) -> list[str]:
        items = ResponseNormalizer._string_list(value)
        if len(items) >= 3:
            return items[:3]
        defaults = [
            "Review the key concept used in this task.",
            "Practice one similar problem with full steps.",
            "Check the final answer against the original task.",
        ]
        return (items + defaults)[:3]

    @staticmethod
    def _remove_contradictory_strengths(final: dict[str, Any]) -> dict[str, Any]:
        result = dict(final)
        strengths = ResponseNormalizer._string_list(result.get("strengths"))
        if not strengths:
            return result

        final_answer_correct = result.get("final_answer_correct")
        mistakes_text = " ".join(ResponseNormalizer._string_list(result.get("mistakes"))).lower()
        bad_tokens = (
            "correct final answer",
            "correct solution",
            "correctly solved",
            "no mistakes",
            "perfect",
        )
        quantitative_mismatch_tokens = (
            "correctly divided",
            "correctly solved for x",
            "correctly solved for y",
            "accurate final answer",
        )

        filtered = []
        for strength in strengths:
            lower = strength.lower()
            if final_answer_correct is False and any(token in lower for token in bad_tokens + quantitative_mismatch_tokens):
                continue
            if mistakes_text and any(token in lower for token in bad_tokens):
                continue
            filtered.append(strength)

        result["strengths"] = filtered
        return result

    @staticmethod
    def _validator_detailed_mistakes(
        validator_result: dict[str, Any],
        mistakes: list[str],
        fallback: Any,
    ) -> list[dict[str, Any]]:
        first_wrong_step = str(validator_result.get("first_wrong_step") or "").strip()
        detailed = ResponseNormalizer._fit_detailed_mistakes(
            validator_result.get("validated_detailed_mistakes", []),
            len(mistakes),
        )
        if detailed:
            if first_wrong_step:
                detailed[0] = dict(detailed[0])
                detailed[0]["location"] = first_wrong_step
            return detailed
        if not mistakes:
            return []
        reason = str(validator_result.get("reason") or "").strip()
        summary = str(validator_result.get("validated_summary") or "").strip()
        synthesized = [
            {
                "type": "Decisive error",
                "location": first_wrong_step or "First real error in the student response",
                "what": mistakes[0],
                "why": reason or summary or "The validator found that this explanation was the first real error.",
                "how_to_fix": "Correct this specific step or claim, then re-check the final answer against the task.",
            }
        ]
        return ResponseNormalizer._fit_detailed_mistakes(synthesized, len(mistakes)) or ResponseNormalizer._fit_detailed_mistakes(
            fallback,
            len(mistakes),
        )

    @staticmethod
    def _enforce_contract(final: dict[str, Any]) -> dict[str, Any]:
        final = dict(final)
        if final.get("analysis_status") in {"analyzer_failed", "rejected"}:
            final["strengths"] = []
            final["mistakes"] = []
            final["detailed_mistakes"] = []
            final["improvement_suggestions"] = []
            final["improvement_suggestion"] = ""
            final["next_steps"] = []
            return final
        final = ResponseNormalizer._remove_contradictory_strengths(final)
        final["strengths"] = ResponseNormalizer._fit_strengths(final.get("strengths"))
        final["mistakes"] = ResponseNormalizer._fit_mistakes(final.get("mistakes"))
        final["detailed_mistakes"] = ResponseNormalizer._fit_detailed_mistakes(
            final.get("detailed_mistakes", []),
            len(final["mistakes"]),
        )
        if final["detailed_mistakes"]:
            final["mistakes"] = final["mistakes"][: len(final["detailed_mistakes"])]
        final["improvement_suggestions"] = ResponseNormalizer._fit_improvement_suggestions(
            final.get("improvement_suggestions")
        )
        final["improvement_suggestion"] = final["improvement_suggestions"][0]
        final["next_steps"] = ResponseNormalizer._fit_next_steps(final.get("next_steps"))
        return final

    @staticmethod
    def _apply_consistency_gate(final: dict[str, Any], validator_result: dict[str, Any]) -> dict[str, Any]:
        result = dict(final)
        summary = str(result.get("short_feedback", "")).lower()
        strengths = " ".join(result.get("strengths", [])).lower()
        mistakes = " ".join(result.get("mistakes", [])).lower()
        next_steps = " ".join(result.get("next_steps", [])).lower()
        reason = str(result.get("validator_reason", "")).lower()
        final_answer_correct = result.get("final_answer_correct")
        math_error_found = result.get("math_error_found")
        score = result.get("suggested_score")
        confirmed = validator_result.get("subject_confirmed")
        first_wrong_step = str(validator_result.get("first_wrong_step") or "").strip().lower()
        detailed_mistakes = result.get("detailed_mistakes", [])

        contradiction = False
        if final_answer_correct is False and any(token in summary for token in ("correct", "no mistakes", "perfect")):
            contradiction = True
        if mistakes and any(token in strengths for token in ("correct final answer", "correct solution", "perfect")):
            contradiction = True
        if final_answer_correct is False and isinstance(score, int) and score > 4:
            result["suggested_score"] = 4
            contradiction = True
        if math_error_found is True and isinstance(score, int) and score > 6:
            result["suggested_score"] = 6
            contradiction = True
        if any(token in next_steps for token in ("fix", "check the final answer", "correct the answer")) and any(
            token in summary for token in ("fully correct", "perfect", "no mistakes")
        ):
            contradiction = True
        if isinstance(score, int) and "too low" in reason and "full marks" in reason and score < result.get("max_score", 10):
            contradiction = True
        if confirmed and result.get("subject") and confirmed.strip().lower() != str(result["subject"]).strip().lower():
            contradiction = True
        if validator_result.get("error_location_correct") is False:
            contradiction = True
        if validator_result.get("error_type_correct") is False:
            contradiction = True
        if validator_result.get("explanation_specific_enough") is False:
            contradiction = True
        if final_answer_correct is False and first_wrong_step and detailed_mistakes:
            locations = " ".join(str(item.get("location", "")).lower() for item in detailed_mistakes if isinstance(item, dict))
            if first_wrong_step not in locations:
                contradiction = True

        if contradiction:
            result["validator_override"] = True
            result["contradiction_found"] = True
            if validator_result.get("validated_summary"):
                result["short_feedback"] = validator_result["validated_summary"]
            if validator_result.get("validated_mistakes") is not None:
                result["mistakes"] = ResponseNormalizer._string_list(validator_result.get("validated_mistakes"))
            if isinstance(validator_result.get("final_score"), int):
                result["suggested_score"] = validator_result["final_score"]
            result["detailed_mistakes"] = ResponseNormalizer._validator_detailed_mistakes(
                validator_result,
                result.get("mistakes", []),
                result.get("detailed_mistakes", []),
            )
        return result
