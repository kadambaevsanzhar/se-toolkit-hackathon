#!/usr/bin/env python3
import json

d = json.load(open("/tmp/det_result.json"))
r = d["result"]

checks = {
    "score 9-10 for correct math": r["suggested_score"] >= 9,
    "strengths 2-3 items": 2 <= len(r["strengths"]) <= 3,
    "mistakes 0-2 items": 0 <= len(r["mistakes"]) <= 2,
    "detailed_mistakes matches mistakes": len(r["detailed_mistakes"]) == len(r["mistakes"]),
    "next_steps exactly 3": len(r["next_steps"]) == 3,
    "student_name extracted": r["student_name"] == "Ivan Ivanov",
    "no fabricated mistakes": len(r["mistakes"]) == 0,
}

print("=== CONTRACT CHECKS ===")
for k, v in checks.items():
    print(f"  {'PASS' if v else 'FAIL'}: {k}")
print(f"\nAll checks: {all(checks.values())}")
