#!/usr/bin/env python3
import json

d = json.load(open("/tmp/pipeline_fix.json"))
r = d["result"]

print("=== VALIDATION PIPELINE CHECK ===")
print(f"is_valid: {r.get('is_valid', 'MISSING')}")
print(f"validator_override: {r.get('validator_override', 'MISSING')}")
print(f"validator_reason: {r.get('validator_reason', 'MISSING')}")
print(f"detailed_mistakes: {r.get('detailed_mistakes', 'MISSING')}")
print(f"detailed_mistakes count: {len(r.get('detailed_mistakes', []))}")
print(f"mistakes count: {len(r.get('mistakes', []))}")
print(f"validator_flags: {r.get('validator_flags', [])}")
print(f"validator_failed: {'validator_failed' in r.get('validator_flags', [])}")

# Check no empty detailed mistakes
for dm in r.get('detailed_mistakes', []):
    for f in ['type', 'location', 'what', 'why', 'how_to_fix']:
        if not dm.get(f, '').strip():
            print(f"WARNING: Empty field '{f}' in detailed_mistake!")

print("\n=== RESULT STRUCTURE ===")
for key in ['suggested_score', 'short_feedback', 'strengths', 'mistakes', 'detailed_mistakes', 'improvement_suggestion', 'next_steps', 'student_name', 'subject', 'topic', 'task_title', 'is_valid', 'validator_override', 'validator_reason', 'validator_flags']:
    val = r.get(key, 'MISSING')
    if isinstance(val, list):
        print(f"{key}: [{len(val)} items]")
    elif isinstance(val, str) and len(val) > 60:
        print(f"{key}: {val[:60]}...")
    else:
        print(f"{key}: {val}")
