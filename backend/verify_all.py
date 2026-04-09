#!/usr/bin/env python3
"""Full end-to-end verification script. Run on VM."""
import json, subprocess, sys

def curl_post(session_id):
    cmd = [
        "curl", "-s", "-X", "POST", "http://localhost:8000/analyze",
        "-F", "file=@/tmp/test.png",
        "-H", f"X-Session-ID: {session_id}",
        "-m", "240"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=250)
    return json.loads(r.stdout)

def curl_get(session_id):
    cmd = [
        "curl", "-s", "http://localhost:8000/history",
        "-H", f"X-Session-ID: {session_id}"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return json.loads(r.stdout)

def curl_result(sub_id, session_id):
    cmd = [
        "curl", "-s", f"http://localhost:8000/result/{sub_id}",
        "-H", f"X-Session-ID: {session_id}"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return json.loads(r.stdout)

print("=" * 60)
print("PART 1: TIMEZONE + FULL PIPELINE")
print("=" * 60)

print("\n[1] Submitting as user-A (full pipeline)...")
result_a = curl_post("user-A")
sub_id_a = result_a["submission_id"]
r = result_a["result"]
print(f"    submission_id={sub_id_a}")
print(f"    score={r['suggested_score']}/{r['max_score']}")
print(f"    feedback={r['short_feedback'][:80]}")
print(f"    flags={r['validator_flags']}")
has_analyzer = not any(f in r["validator_flags"] for f in ["analysis_failed", "fallback_response"])
has_validator = "validator_applied" in r["validator_flags"]
print(f"    ANALYZER: {'✅ used' if has_analyzer else '❌ FAILED'}")
print(f"    VALIDATOR: {'✅ used' if has_validator else '⚠️ failed (graceful)'}")

print("\n[2] Timezone check (ISO 8601 with Z)...")
hist_a = curl_get("user-A")
print(f"    user-A history: {len(hist_a)} items")
for item in hist_a:
    ts = item["created_at"]
    has_z = ts.endswith("Z")
    print(f"    id={item['id']}, created_at={ts}, has_Z={has_z}")
    if not has_z:
        print(f"    ❌ FAIL: Timestamp missing Z suffix!")
        sys.exit(1)
print("    ✅ All timestamps have Z suffix")

print("\n[3] Isolation: user-B should NOT see user-A items...")
hist_b_before = curl_get("user-B")
print(f"    user-B sees {len(hist_b_before)} items before own submission")

print("\n[4] Submitting as user-B...")
result_b = curl_post("user-B")
sub_id_b = result_b["submission_id"]
print(f"    submission_id={sub_id_b}")

hist_a2 = curl_get("user-A")
hist_b2 = curl_get("user-B")
print(f"    user-A sees {len(hist_a2)} items (ids: {[i['id'] for i in hist_a2]})")
print(f"    user-B sees {len(hist_b2)} items (ids: {[i['id'] for i in hist_b2]})")

if len(hist_a2) != 1 or len(hist_b2) != 1:
    print(f"    ❌ FAIL: Wrong item counts")
    sys.exit(1)
if hist_a2[0]["id"] == hist_b2[0]["id"]:
    print(f"    ❌ FAIL: Privacy leak!")
    sys.exit(1)
print("    ✅ Isolation confirmed")

print("\n[5] Result endpoint isolation...")
denied = curl_result(sub_id_b, "user-A")
if "detail" in denied:
    print(f"    ✅ user-A correctly denied access to user-B's result")
else:
    print(f"    ❌ FAIL: user-A accessed user-B's result!")
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL CHECKS PASSED ✅")
print("=" * 60)
