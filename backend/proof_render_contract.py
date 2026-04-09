#!/usr/bin/env python3
"""Check that Telegram formatting and web rendering use the same normalized truth."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bot"))
os.environ.setdefault("TELEGRAM_TOKEN", "proof-token")

from bot import HomeworkGraderBot  # noqa: E402


def main():
    bot = HomeworkGraderBot()
    normalized = {
        "analysis_status": "success",
        "validation_status": "validated",
        "is_preliminary": False,
        "is_academic_submission": True,
        "student_name": None,
        "subject": "Mathematics",
        "topic": "Algebra",
        "task_title": "Solve the equation",
        "suggested_score": 10,
        "max_score": 10,
        "short_feedback": "Validated summary",
        "strengths": ["Correct setup", "Correct final answer"],
        "mistakes": [],
        "detailed_mistakes": [],
        "improvement_suggestions": ["Show one more verification step."],
        "next_steps": ["Practice one harder equation.", "Check by substitution.", "Review linear equations."],
        "validator_reason": "Validated by secondary review.",
        "analyzer_reason": "Analyzer completed successfully.",
    }
    compact = bot.format_result({"submission_id": 1, "result": normalized})
    details = bot.format_details(normalized)
    print(json.dumps({
        "normalized": normalized,
        "telegram_compact": compact,
        "telegram_details": details,
        "compact_has_same_score": "10/10" in compact,
        "details_has_analysis_status": "analysis_status: success" in details,
        "details_has_validation_status": "validation_status: validated" in details,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
