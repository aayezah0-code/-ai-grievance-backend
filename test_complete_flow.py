import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

print("="*60)
print("RUNNING COMPREHENSIVE SUITE OF CITIZEN / ADMIN & JWT TESTS")
print("="*60)

# TEST 1: Citizen Registration & Login
citizen_email = f"test_citizen_{requests.get(f'{BASE_URL}/api/analytics').json().get('total', 0) + 100}@test.com"
print(f"\n[1] Registering citizen: {citizen_email}")
reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
    "full_name": "Test Citizen Flow",
    "mobile_no": "9998887776",
    "email": citizen_email,
    "address": "123 Citizen Lane",
    "city": "Mumbai",
    "state": "Maharashtra",
    "pincode": "400001",
    "password": "CitizenPassword123"
})
assert reg_res.status_code == 200, f"Citizen reg failed: {reg_res.text}"
citizen_data = reg_res.json()
citizen_token = citizen_data["access_token"]
citizen_id = citizen_data["user_id"]
assert citizen_data["role"] == "citizen"
print(f" -> Citizen registered with ID={citizen_id}, role={citizen_data['role']}, token received.")

# TEST 2: Citizen Complaint Submission (JWT derived ownership)
print("\n[2] Submitting complaint with Citizen JWT")
comp_res = requests.post(
    f"{BASE_URL}/api/complaints",
    headers={"Authorization": f"Bearer {citizen_token}"},
    json={
        "citizen_name": "Test Citizen Flow",
        "user_id": 99999, # Deliberately send mismatched user_id to test JWT override
        "text": "Dangerous open pothole on Main Street causing traffic disruption."
    }
)
assert comp_res.status_code == 200, f"Complaint submission failed: {comp_res.text}"
complaint = comp_res.json()
complaint_id = complaint["id"]
assert complaint["user_id"] == citizen_id, f"Security issue: expected user_id={citizen_id}, got {complaint['user_id']}"
assert complaint["status"] == "Pending"
print(f" -> Complaint #{complaint_id} created with verified user_id={complaint['user_id']} (overrode spoofed client user_id). AI Dept: {complaint['department']}, Priority: {complaint['priority']}")

# TEST 3: Citizen My-Complaints
print("\n[3] Fetching My Complaints for citizen")
my_comp_res = requests.get(
    f"{BASE_URL}/api/my-complaints",
    headers={"Authorization": f"Bearer {citizen_token}"}
)
assert my_comp_res.status_code == 200, f"My complaints failed: {my_comp_res.text}"
my_complaints = my_comp_res.json()
found = any(c["id"] == complaint_id for c in my_complaints)
assert found, "Submitted complaint not found in citizen's My Complaints list!"
print(f" -> Successfully fetched {len(my_complaints)} complaints for citizen. Complaint #{complaint_id} verified.")

# TEST 4: Another Citizen Isolation
print("\n[4] Testing data isolation between citizens")
other_email = f"other_citizen_{citizen_id}@test.com"
other_reg = requests.post(f"{BASE_URL}/api/auth/register", json={
    "full_name": "Other Citizen",
    "mobile_no": "1112223334",
    "email": other_email,
    "address": "456 Other St",
    "city": "Delhi",
    "state": "Delhi",
    "pincode": "110001",
    "password": "OtherPassword123"
})
other_token = other_reg.json()["access_token"]
other_my_res = requests.get(
    f"{BASE_URL}/api/my-complaints",
    headers={"Authorization": f"Bearer {other_token}"}
)
other_complaints = other_my_res.json()
assert not any(c["id"] == complaint_id for c in other_complaints), "Isolation breach: other citizen saw first citizen's complaint!"
print(f" -> Isolation verified: Other citizen has {len(other_complaints)} complaints and cannot see complaint #{complaint_id}.")

# TEST 5: Admin Registration
print("\n[5] Testing Admin Registration at /api/auth/admin/register")
admin_test_email = f"admin_test_{citizen_id}@grievance.gov"
admin_reg_res = requests.post(f"{BASE_URL}/api/auth/admin/register", json={
    "full_name": "Official Admin Officer",
    "email": admin_test_email,
    "password": "AdminSecretPass@123",
    "admin_code": "ADMIN2026"
})
assert admin_reg_res.status_code == 200, f"Admin reg failed: {admin_reg_res.text}"
admin_reg_data = admin_reg_res.json()
assert admin_reg_data["role"] == "admin"
admin_token = admin_reg_data["access_token"]
print(f" -> Admin registered with role={admin_reg_data['role']}, ID={admin_reg_data['user_id']}")

# TEST 6: Security - Citizen cannot perform admin status update
print("\n[6] Testing Security: Citizen calling admin PATCH /api/complaints/{id}/status")
citizen_status_res = requests.patch(
    f"{BASE_URL}/api/complaints/{complaint_id}/status",
    headers={"Authorization": f"Bearer {citizen_token}"},
    json={"status": "Approved"}
)
assert citizen_status_res.status_code == 403, f"Expected 403 Forbidden, got {citizen_status_res.status_code}"
print(" -> Correctly received 403 Forbidden when citizen tried to update complaint status.")

# TEST 7: Admin Status Transitions
print("\n[7] Testing Admin Status Transitions (Pending -> Approved -> In Progress -> Completed)")

# Step A: Approved
appr_res = requests.patch(
    f"{BASE_URL}/api/complaints/{complaint_id}/status",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"status": "Approved"}
)
assert appr_res.status_code == 200, f"Approved transition failed: {appr_res.text}"
assert appr_res.json()["status"] == "Approved"
print(" -> Transition 1: Status updated to Approved")

# Step B: In Progress
prog_res = requests.patch(
    f"{BASE_URL}/api/complaints/{complaint_id}/status",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"status": "In Progress"}
)
assert prog_res.status_code == 200, f"In Progress transition failed: {prog_res.text}"
assert prog_res.json()["status"] == "In Progress"
print(" -> Transition 2: Status updated to In Progress")

# Step C: Completed
comp_status_res = requests.patch(
    f"{BASE_URL}/api/complaints/{complaint_id}/status",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"status": "Completed"}
)
assert comp_status_res.status_code == 200, f"Completed transition failed: {comp_status_res.text}"
assert comp_status_res.json()["status"] == "Completed"
print(" -> Transition 3: Status updated to Completed (resolution email trigger invoked)")

# TEST 8: Verify Citizen sees Completed status
print("\n[8] Verifying updated Completed status in citizen's My Complaints")
final_my_res = requests.get(
    f"{BASE_URL}/api/my-complaints",
    headers={"Authorization": f"Bearer {citizen_token}"}
)
final_complaints = final_my_res.json()
matching = next((c for c in final_complaints if c["id"] == complaint_id), None)
assert matching is not None
assert matching["status"] == "Completed", f"Expected Completed, got {matching['status']}"
print(f" -> Confirmed: Citizen sees updated status '{matching['status']}' in My Complaints.")

print("\n" + "="*60)
print("ALL 8 VERIFICATION TESTS PASSED PERFECTLY!")
print("="*60)
