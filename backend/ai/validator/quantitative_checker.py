"""Deterministic quantitative guardrails for simple linear-equation cases."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any


LINEAR_PATTERN = re.compile(
    r"^\s*([+-]?\d*)\s*([a-zA-Z])\s*([+-])\s*(\d+)\s*=\s*([+-]?\d+)\s*$"
)
VALUE_PATTERN = re.compile(r"^\s*([a-zA-Z])\s*=\s*([+-]?\d+(?:/\d+)?)\s*$")


@dataclass
class QuantitativeCheckResult:
    final_answer_correct: bool
    correct_answer: str
    first_wrong_step: str
    summary: str
    mistake: str
    detailed_mistake: dict[str, str]
    score: int
    reason: str


def run_quantitative_guardrails(
    raw_analyzer: dict[str, Any],
    final_result: dict[str, Any],
) -> QuantitativeCheckResult | None:
    """Return a deterministic override for simple visible linear equations."""
    subject = str(raw_analyzer.get("subject") or final_result.get("subject") or "").lower()
    if subject not in {"mathematics", "math", "algebra"}:
        return None

    task_text = str(raw_analyzer.get("reconstructed_task_text") or raw_analyzer.get("task_title") or "").strip()
    steps = _string_list(raw_analyzer.get("observed_steps"))
    answer_text = str(raw_analyzer.get("student_answer_text") or "").strip()
    equation_match = _find_linear_equation(task_text, steps)
    if not equation_match:
        return None

    coefficient, variable, constant_sign, constant_value, rhs_value = equation_match
    a = _parse_coefficient(coefficient)
    b = int(constant_value) * (1 if constant_sign == "+" else -1)
    c = int(rhs_value)
    if a == 0:
        return None

    correct_value = Fraction(c - b, a)
    final_line = _extract_final_assignment(steps, answer_text, variable)
    if final_line is None:
        return None

    student_value = final_line[1]
    correct_answer_text = _format_fraction(correct_value)
    if student_value == correct_value:
        return None

    first_wrong_step = _identify_first_wrong_step(steps, variable, correct_value)
    summary = (
        f"The student made a calculation error in the step that concludes {variable} = "
        f"{_format_fraction(student_value)}. The correct value is {variable} = {correct_answer_text}."
    )
    mistake = (
        f"The first real error is solving {first_wrong_step} as {variable} = {_format_fraction(student_value)} "
        f"instead of {variable} = {correct_answer_text}."
    )
    detail = {
        "type": "Calculation Error",
        "location": first_wrong_step,
        "what": (
            f"The student wrote {variable} = {_format_fraction(student_value)} instead of "
            f"{variable} = {correct_answer_text}."
        ),
        "why": (
            f"Solving the equation gives {variable} = {correct_answer_text}, so the visible final answer "
            f"{variable} = {_format_fraction(student_value)} is incorrect."
        ),
        "how_to_fix": (
            f"Re-solve the last step carefully, then verify by substitution that {variable} = "
            f"{correct_answer_text} satisfies the original equation."
        ),
    }
    reason = (
        f"Deterministic quantitative guardrail solved the visible linear equation independently and found "
        f"the correct answer {variable} = {correct_answer_text}. The student's final visible answer "
        f"{variable} = {_format_fraction(student_value)} is incorrect."
    )
    return QuantitativeCheckResult(
        final_answer_correct=False,
        correct_answer=correct_answer_text,
        first_wrong_step=first_wrong_step,
        summary=summary,
        mistake=mistake,
        detailed_mistake=detail,
        score=4,
        reason=reason,
    )


def apply_quantitative_guardrail(
    final_result: dict[str, Any],
    raw_analyzer: dict[str, Any],
) -> dict[str, Any]:
    """Override final result if deterministic quantitative checks find a decisive mismatch."""
    guardrail = run_quantitative_guardrails(raw_analyzer, final_result)
    if guardrail is None:
        return final_result

    result = dict(final_result)
    result["analysis_status"] = "success"
    result["validation_status"] = "validated"
    result["is_preliminary"] = False
    result["validator_override"] = True
    result["is_valid"] = True
    result["final_answer_correct"] = guardrail.final_answer_correct
    result["math_error_found"] = True
    result["contradiction_found"] = True
    result["suggested_score"] = guardrail.score
    result["short_feedback"] = guardrail.summary
    result["mistakes"] = [guardrail.mistake]
    result["detailed_mistakes"] = [guardrail.detailed_mistake]
    result["validator_reason"] = guardrail.reason
    return result


def _find_linear_equation(task_text: str, steps: list[str]) -> tuple[str, str, str, str, str] | None:
    candidates = [task_text] + steps
    for candidate in candidates:
        match = LINEAR_PATTERN.search(candidate.replace("Solve:", "").replace("Solve the equation", "").strip())
        if match:
            return match.groups()
    return None


def _extract_final_assignment(
    steps: list[str],
    answer_text: str,
    variable: str,
) -> tuple[str, Fraction] | None:
    candidates = list(reversed(steps))
    if answer_text:
        candidates.insert(0, answer_text)
    for line in candidates:
        match = VALUE_PATTERN.match(line)
        if match and match.group(1).lower() == variable.lower():
            return line.strip(), Fraction(match.group(2))
    return None


def _identify_first_wrong_step(steps: list[str], variable: str, correct_value: Fraction) -> str:
    for line in reversed(steps):
        match = VALUE_PATTERN.match(line)
        if match and match.group(1).lower() == variable.lower():
            return f"Step '{line.strip()}'"
    return f"Final step solving for {variable}; the correct value is {variable} = {_format_fraction(correct_value)}"


def _parse_coefficient(raw: str) -> int:
    if raw in {"", "+"}:
        return 1
    if raw == "-":
        return -1
    return int(raw)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
