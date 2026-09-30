"""
Quick test: submit complaints in Hinglish and Tamil via the live API.
Run from the backend folder with venv activated.
"""
import sys
import json
import urllib.request

BASE = "http://localhost:8000"

def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, body
    except Exception as ex:
        return 0, str(ex)

def get(path):
    req = urllib.request.Request(BASE + path)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as ex:
        return 0, str(ex)

def run():
    # Health check
    status, data = get("/api/notifications")
    print(f"[Health] /api/notifications => {status}")
    assert status == 200, "Backend not reachable!"

    tests = [
        {
            "lang": "Hinglish",
            "text": "Meri gali mein bahut bada pothole hai. Bahut accident ho rahe hain. Koi action nahi le raha. Jaldi theek karo.",
            "user_id": 1,
        },
        {
            "lang": "Tamil",
            "text": "என் தெருவில் பெரிய குழி இருக்கிறது. தினமும் விபத்துக்கள் நடக்கின்றன. உடனடியாக சரிசெய்யுங்கள்.",
            "user_id": 1,
        },
        {
            "lang": "English",
            "text": "There is a large pothole on Main Street causing accidents. Please fix it immediately.",
            "user_id": 1,
        },
    ]

    for t in tests:
        print(f"\n{'='*60}")
        print(f"[TEST] Language: {t['lang']}")
        print(f"[TEST] Text: {t['text'][:80]}...")
        status, resp = post("/api/complaints/submit", {"text": t["text"], "user_id": t["user_id"]})
        print(f"[TEST] HTTP Status: {status}")
        if isinstance(resp, dict):
            print(f"[TEST] Title    : {resp.get('title', 'N/A')}")
            print(f"[TEST] Dept     : {resp.get('department', 'N/A')}")
            print(f"[TEST] Severity : {resp.get('severity', 'N/A')}")
            summary = resp.get('ai_summary') or resp.get('summary', 'N/A')
            if summary and summary != 'N/A':
                print(f"[TEST] Summary  : {summary[:120]}...")
            print(f"[TEST] PASS ✓" if status in (200, 201) else f"[TEST] FAIL ✗")
        else:
            print(f"[TEST] Response : {str(resp)[:300]}")

    print(f"\n{'='*60}")
    print("[DONE] All tests completed.")

if __name__ == "__main__":
    # Force UTF-8 output so Tamil/Hindi prints correctly
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run()
