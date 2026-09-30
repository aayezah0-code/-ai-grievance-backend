import urllib.request, json, sqlite3, random

BASE = "http://127.0.0.1:8000"

def post(url, data, hdrs=None):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    if hdrs:
        for k, v in hdrs.items(): req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as ex:
        return 0, {"error": str(ex)}

def get(url, hdrs=None):
    req = urllib.request.Request(url)
    if hdrs:
        for k, v in hdrs.items(): req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def patch(url, data, hdrs=None):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Content-Type", "application/json")
    if hdrs:
        for k, v in hdrs.items(): req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def db_row(uid):
    conn = sqlite3.connect("complaints.db")
    cur = conn.cursor()
    row = cur.execute("SELECT is_verified, verification_code FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row

new_email = "aayezahali111+v" + str(random.randint(10000,99999)) + "@gmail.com"
test_pass = "TestVerify@2026"
test_name = "Verify Test Citizen"

print("="*60)
print("TEST 1 - REGISTER (expect: 200, no JWT, email sent)")
s, d = post(BASE+"/api/auth/register", {
    "full_name": test_name, "email": new_email,
    "password": test_pass, "mobile_no": "9999999999",
    "address": "Test St", "city": "City", "state": "State", "pincode": "123456"
})
print("  HTTP:", s)
print("  requires_verification:", d.get("requires_verification"))
print("  email_sent:", d.get("email_sent"))
print("  NO access_token:", "access_token" not in d)
new_uid = d.get("user_id")
row = db_row(new_uid)
db_code = row[1]
print("  DB is_verified:", row[0], "(expected: 0)")
print("  DB code set:", bool(db_code))

print()
print("TEST 2 - LOGIN BEFORE VERIFY (expect: 403)")
s2, d2 = post(BASE+"/api/auth/login", {"email": new_email, "password": test_pass})
print("  HTTP:", s2, "(expected: 403)")
print("  detail:", d2.get("detail"))
print("  BLOCKED:", s2 == 403)

print()
print("TEST 3 - WRONG CODE (expect: 400)")
s3, d3 = post(BASE+"/api/auth/verify-email", {"email": new_email, "code": "000000"})
print("  HTTP:", s3, "(expected: 400)")
print("  detail:", d3.get("detail"))
print("  Still unverified:", db_row(new_uid)[0] == 0)

print()
print("TEST 4 - CORRECT CODE (expect: 200, is_verified=1, code cleared)")
s4, d4 = post(BASE+"/api/auth/verify-email", {"email": new_email, "code": db_code})
print("  HTTP:", s4)
print("  message:", d4.get("message"))
row4 = db_row(new_uid)
print("  DB is_verified:", row4[0], "(expected: 1)")
print("  code cleared:", row4[1] is None)

print()
print("TEST 5 - LOGIN AFTER VERIFY (expect: 200 + JWT)")
s5, d5 = post(BASE+"/api/auth/login", {"email": new_email, "password": test_pass})
print("  HTTP:", s5)
print("  access_token:", bool(d5.get("access_token")))
print("  starts eyJ:", str(d5.get("access_token",""))[:4])
print("  role:", d5.get("role"))
new_token = d5.get("access_token","")

print()
print("TEST 6 - COMPLAINT + MY-COMPLAINTS (regression)")
s6, d6 = post(BASE+"/api/complaints",
    {"citizen_name": test_name, "text": "Verify feature regression test", "image_url": None},
    {"Authorization": "Bearer " + new_token})
print("  Complaint HTTP:", s6)
print("  user_id:", d6.get("user_id"), "(expected:", new_uid,")")
print("  Match:", d6.get("user_id") == new_uid)
s7, d7 = get(BASE+"/api/my-complaints", {"Authorization": "Bearer " + new_token})
print("  My-complaints HTTP:", s7, "count:", len(d7) if isinstance(d7,list) else "ERR")

print()
print("TEST 7 - EXISTING USER REGRESSION (Aiza user 1)")
s8, d8 = post(BASE+"/api/auth/login", {"email": "aayezahali111@gmail.com", "password": "9827"})
print("  HTTP:", s8, "  JWT:", bool(d8.get("access_token")))
existing_token = d8.get("access_token","")

print()
print("TEST 8 - ADMIN REGRESSION")
s9, d9 = post(BASE+"/api/auth/login", {"email": "admin@grievance.gov", "password": "Admin@1234"})
print("  HTTP:", s9, "  role:", d9.get("role"), "  JWT:", bool(d9.get("access_token")))
admin_token = d9.get("access_token","")

print()
print("TEST 9 - RESEND VERIFICATION")
resend_email = "aayezahali111+rs" + str(random.randint(10000,99999)) + "@gmail.com"
sr1, dr1 = post(BASE+"/api/auth/register", {
    "full_name": "Resend User", "email": resend_email,
    "password": "Resend@123", "mobile_no": "8888888888",
    "address": "A", "city": "B", "state": "C", "pincode": "000000"
})
resend_uid = dr1.get("user_id")
conn = sqlite3.connect("complaints.db")
cur = conn.cursor()
orig_code = cur.execute("SELECT verification_code FROM users WHERE id=?", (resend_uid,)).fetchone()[0]
conn.close()
sr2, dr2 = post(BASE+"/api/auth/resend-verification", {"email": resend_email})
print("  Resend HTTP:", sr2)
conn = sqlite3.connect("complaints.db")
cur = conn.cursor()
new_code_row = cur.execute("SELECT verification_code FROM users WHERE id=?", (resend_uid,)).fetchone()
conn.close()
print("  Code refreshed:", orig_code != new_code_row[0])
print("  Message:", dr2.get("message"))

print()
print("TEST 10 - COMPLETION EMAIL REGRESSION")
sc, dc = post(BASE+"/api/complaints",
    {"citizen_name":"Aiza","text":"Completion email regression post-verify","image_url":None},
    {"Authorization":"Bearer "+existing_token})
cid = dc.get("id")
print("  New complaint ID:", cid)
p1 = patch(BASE+"/api/complaints/"+str(cid)+"/status",{"status":"Approved"},{"Authorization":"Bearer "+admin_token})
p2 = patch(BASE+"/api/complaints/"+str(cid)+"/status",{"status":"In Progress"},{"Authorization":"Bearer "+admin_token})
p3 = patch(BASE+"/api/complaints/"+str(cid)+"/status",{"status":"Completed","official_remarks":"Done"},{"Authorization":"Bearer "+admin_token})
print("  Approve:", p1[0], " InProgress:", p2[0], " Complete:", p3[0])
print("  Final status:", p3[1].get("status") if isinstance(p3[1],dict) else p3[1])

print()
print("ALL TESTS COMPLETE")
