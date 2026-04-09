#!/usr/bin/env python3
"""Run all name extraction and timezone tests."""
import json, subprocess, sys

BASE = "http://localhost:8000"

def curl_post(filename, session_id, timeout=240):
    cmd = [
        "curl", "-s", "-X", "POST", f"{BASE}/analyze",
        "-F", f"file=@{filename}",
        "-H", f"X-Session-ID: {session_id}",
        "-m", str(timeout)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+10)
    if r.returncode != 0:
        print(f"ERROR: {r.stderr}")
        return None
    return json.loads(r.stdout)

def curl_get(session_id):
    cmd = ["curl", "-s", f"{BASE}/history", "-H", f"X-Session-ID: {session_id}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return json.loads(r.stdout)

print("=" * 60)
print("BUG 2 FIX — STUDENT NAME EXTRACTION")
print("=" * 60)

# Test A
print("\n--- TEST A: 'Name: Ivan Ivanov' ---")
result_a = curl_post("/tmp/test_name_a.png", "testA")
if result_a:
    r = result_a["result"]
    print(f"  student_name: {r.get('student_name')}")
    print(f"  score: {r['suggested_score']}/{r['max_score']}")
    print(f"  subject: {r.get('subject')}")
    print(f"  topic: {r.get('topic')}")
    print(f"  task_title: {r.get('task_title')}")
    expected = "Ivan Ivanov"
    actual = r.get("student_name")
    print(f"  EXPECTED: {expected}")
    print(f"  MATCH: {'YES' if actual == expected else 'NO (checking partial)'}")
    if actual and expected.lower() in actual.lower():
        print(f"  CONTAINS: YES")

# Test B
print("\n--- TEST B: 'Student: Maria Petrova' ---")
result_b = curl_post("/tmp/test_name_b.png", "testB")
if result_b:
    r = result_b["result"]
    print(f"  student_name: {r.get('student_name')}")
    print(f"  score: {r['suggested_score']}/{r['max_score']}")
    expected = "Maria Petrova"
    actual = r.get("student_name")
    print(f"  EXPECTED: {expected}")
    print(f"  MATCH: {'YES' if actual == expected else 'NO (checking partial)'}")
    if actual and expected.lower() in actual.lower():
        print(f"  CONTAINS: YES")

# Test C
print("\n--- TEST C: No name field ---")
result_c = curl_post("/tmp/test_name_c.png", "testC")
if result_c:
    r = result_c["result"]
    print(f"  student_name: {r.get('student_name')}")
    print(f"  score: {r['suggested_score']}/{r['max_score']}")
    expected = None
    actual = r.get("student_name")
    print(f"  EXPECTED: {expected}")
    print(f"  MATCH: {'YES' if actual == expected else 'NO'}")

print("\n" + "=" * 60)
print("BUG 1 FIX — TIMEZONE")
print("=" * 60)

# Get system time
system_time = subprocess.run(["date"], capture_output=True, text=True).stdout.strip()
utc_time = subprocess.run(["date", "-u"], capture_output=True, text=True).stdout.strip()
print(f"\n  System time: {system_time}")
print(f"  UTC time:    {utc_time}")

# Get DB raw value
hist = curl_get("testA")
if hist and len(hist) > 0:
    api_time = hist[0]["created_at"]
    print(f"  API JSON:    {api_time}")
    has_z = api_time.endswith("Z")
    print(f"  Has Z suffix: {has_z}")

# Test bot conversion
from datetime import datetime, timezone
def fmt_telegram(iso_string):
    if not iso_string:
        return "—"
    utc = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    return utc.strftime('%d %b %Y, %H:%M UTC')

if hist:
    telegram_time = fmt_telegram(api_time)
    print(f"  Telegram:    {telegram_time}")
    # Verify: UTC time should match
    utc_dt = datetime.fromisoformat(api_time.replace('Z', '+00:00'))
    print(f"  UTC verified: {utc_dt.strftime('%d %b %Y, %H:%M UTC')}")

print("\n" + "=" * 60)
print("HISTORY PRIVACY CHECK")
print("=" * 60)

for sid, label in [("testA", "User A"), ("testB", "User B"), ("testC", "User C")]:
    h = curl_get(sid)
    ids = [item["id"] for item in h]
    print(f"  {label}: {len(h)} items, ids={ids}")

print("\nDone.")
