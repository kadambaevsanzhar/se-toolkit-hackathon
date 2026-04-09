#!/usr/bin/env python3
"""Final validation pipeline verification."""
import json, sys

files = ["/tmp/pipeline_v2.json", "/tmp/pipeline_final.json", "/tmp/pipeline_fix.json"]

for f in files:
    try:
        d = json.load(open(f))
        r = d["result"]
        print(f"\n=== {f} ===")
        print(f"  is_valid: {r.get('is_valid', 'MISSING')}")
        print(f"  validator_override: {r.get('validator_override', 'MISSING')}")
        print(f"  validator_reason: {r.get('validator_reason', 'MISSING')[:60]}")
        print(f"  score: {r['suggested_score']}/{r['max_score']}")
        print(f"  mistakes: {r['mistakes']}")
        print(f"  detailed_mistakes: [{len(r['detailed_mistakes'])} items]")
        print(f"  flags: {r['validator_flags']}")
        print(f"  student_name: {r.get('student_name')}")
        break
    except Exception as e:
        print(f"  {f}: {e}")
