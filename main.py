from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import os, shutil, uuid, datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
load_dotenv()
import jwt
import database, models, ai_engine

database.Base.metadata.create_all(bind=database.engine)

def seed_default_accounts():
    db = database.SessionLocal()
    try:
        admins = [
            ("Aliya Admin", "aliya123@gmail.com", "aliya123", "9999999999"),
            ("System Admin", "admin@grievance.gov", "Admin@1234", "9876543210"),
            ("Aliya", "aliya@gmail.com", "123456", "9876543211"),
            ("Aayezah Ali", "aayezahali@gmail.com", "1234567", "9876543212"),
        ]
        for name, email, password, phone in admins:
            existing = db.query(models.User).filter(models.User.email == email).first()
            if not existing:
                u = models.User(
                    full_name=name,
                    mobile_no=phone,
                    email=email,
                    address="Municipal Administrative HQ",
                    city="Bhopal",
                    state="Madhya Pradesh",
                    pincode="462001",
                    hashed_password=password,
                    role="admin",
                    is_verified=True
                )
                db.add(u)

        citizens = [
            ("Aayezah Ali", "aayezahali111@gmail.com", "12345678", "9123456789"),
            ("Aayezah", "aayezah0@gmail.com", "12345678", "9123456788")
        ]
        for name, email, password, phone in citizens:
            existing = db.query(models.User).filter(models.User.email == email).first()
            if not existing:
                c = models.User(
                    full_name=name,
                    mobile_no=phone,
                    email=email,
                    address="Citizen Colony",
                    city="Bhopal",
                    state="Madhya Pradesh",
                    pincode="462001",
                    hashed_password=password,
                    role="citizen",
                    is_verified=True
                )
                db.add(c)
        db.commit()
    except Exception as e:
        print(f"[Seed] Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()

seed_default_accounts()

# --- JWT CONFIGURATION ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "19bb6444f3aaf9fab6fbc69b3417e7ed12d2929d52276fd9e486b297f4d6c4d7")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

def create_access_token(user_id: int, role: str) -> str:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    expire = now_utc + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": expire,
        "iat": now_utc
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

# --- EMAIL CONFIGURATION (Phase 8) ---
MAIL_HOST = os.getenv("MAIL_HOST", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
MAIL_FROM = os.getenv("MAIL_FROM", "") or MAIL_USERNAME

def send_completion_email(
    to_email: str, 
    citizen_name: str, 
    complaint_id: int, 
    complaint_title: str,
    description: str = "",
    category: str = "",
    department: str = "",
    priority: str = "",
    official_remarks: Optional[str] = None,
    created_at = None
):
    """Send a resolution notification email to the complaint owner upon completion."""
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print(f"[Email] EMAIL FAILED: SMTP credentials not configured in environment — skipping email for complaint #{complaint_id}")
        return

    try:
        subject = f"Your Complaint Has Been Completed - Complaint #{complaint_id}"
        formatted_date = created_at.strftime("%d %b %Y, %I:%M %p") if isinstance(created_at, datetime.datetime) else (str(created_at) if created_at else "N/A")
        remarks_text = official_remarks if (official_remarks and official_remarks.strip()) else "No additional remarks."

        body = f"""Dear {citizen_name},

We are pleased to inform you that your grievance has been marked as Completed.

--------------------------------------------------
COMPLAINT DETAILS
--------------------------------------------------
Complaint ID     : #{complaint_id}
Title            : {complaint_title or 'Civic Grievance'}
Category         : {category or 'General Infrastructure'}
Department       : {department or 'Public Works'}
Priority         : {priority or 'Medium'}
Status           : Completed
Date Filed       : {formatted_date}

Description:
{description or 'No description provided.'}

Official Remarks:
{remarks_text}
--------------------------------------------------

Thank you for bringing this matter to our attention. Your active participation helps improve our civic infrastructure.

Regards,
Municipal Grievance Redressal Team
CitizenConnect"""

        msg = MIMEMultipart()
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, [to_email], msg.as_string())

        print(f"[Email] EMAIL SUCCESS: Resolution email delivered to {to_email} for complaint #{complaint_id}")
    except Exception as e:
        safe_msg = str(e)
        if MAIL_PASSWORD and MAIL_PASSWORD in safe_msg:
            safe_msg = safe_msg.replace(MAIL_PASSWORD, "******")
        print(f"[Email] EMAIL FAILED: Could not deliver completion email to {to_email} for complaint #{complaint_id}: {safe_msg}")

def send_verification_email(to_email: str, full_name: str, code: str):
    """Send a 6-digit email verification code to a newly registered citizen."""
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print(f"[Email] VERIFICATION EMAIL FAILED: SMTP not configured — skipping for {to_email}")
        return False
    try:
        subject = "Verify Your CitizenConnect Account"
        body = f"""Dear {full_name},

Thank you for registering with CitizenConnect.

Your email verification code is:

    {code}

This code will expire in 10 minutes.

If you did not create this account, please ignore this email.

Regards,
CitizenConnect"""
        msg = MIMEMultipart()
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_FROM, [to_email], msg.as_string())
        print(f"[Email] VERIFICATION EMAIL SENT to {to_email}")
        return True
    except Exception as e:
        safe_msg = str(e)
        if MAIL_PASSWORD and MAIL_PASSWORD in safe_msg:
            safe_msg = safe_msg.replace(MAIL_PASSWORD, "******")
        print(f"[Email] VERIFICATION EMAIL FAILED for {to_email}: {safe_msg}")
        return False

app = FastAPI(title="Grievance Processing AI")

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "CitizenConnect Grievance AI Backend",
        "docs_url": "/docs"
    }


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> models.User:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    auth_str = authorization.strip()
    if not auth_str.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Expected 'Bearer <token>'")

    token = auth_str[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload: missing user_id")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

class ComplaintCreate(BaseModel):
    citizen_name: Optional[str] = "Anonymous"
    user_id: Optional[int] = None
    text: Optional[str] = ""
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    image_url: Optional[str] = None

class ComplaintResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    citizen_name: str
    title: Optional[str]
    original_text: str
    translated_text: Optional[str]
    department: str
    priority: str
    sentiment: str
    status: str
    latitude: Optional[str]
    longitude: Optional[str]
    address: Optional[str]
    pincode: Optional[str]
    image_url: Optional[str]
    estimated_resolution_time: Optional[str]
    ai_summary: Optional[str] = None
    detected_issue: Optional[str] = None
    category: Optional[str] = None
    visual_risk_level: Optional[str] = None
    issue_tags: Optional[str] = None
    confidence_score: Optional[int] = None
    image_observation: Optional[str] = None
    official_remarks: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class ComplaintStatusUpdate(BaseModel):
    status: str
    official_remarks: Optional[str] = None

class UserCreate(BaseModel):
    full_name: str
    mobile_no: str
    email: str
    address: str
    city: str
    state: str
    pincode: str
    password: str

class AdminCreate(BaseModel):
    full_name: str
    email: str
    password: str
    admin_code: Optional[str] = None
    mobile_no: Optional[str] = ""
    address: Optional[str] = ""
    city: Optional[str] = ""
    state: Optional[str] = ""
    pincode: Optional[str] = ""

class UserLogin(BaseModel):
    email: str
    password: str

import secrets

@app.post("/api/auth/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Generate secure 6-digit verification code
    code = str(secrets.randbelow(1000000)).zfill(6)
    expires_at = datetime.datetime.now() + datetime.timedelta(minutes=10)

    new_user = models.User(
        full_name=user.full_name,
        mobile_no=user.mobile_no,
        email=user.email,
        address=user.address,
        city=user.city,
        state=user.state,
        pincode=user.pincode,
        hashed_password=user.password,
        role="citizen",
        is_verified=False,
        verification_code=code,
        verification_code_expires_at=expires_at
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email (do NOT issue JWT yet)
    email_sent = send_verification_email(new_user.email, new_user.full_name, code)

    return {
        "message": "Registration successful. Please check your email for the verification code.",
        "user_id": new_user.id,
        "email": new_user.email,
        "email_sent": email_sent,
        "requires_verification": True
    }

@app.post("/api/auth/admin/register")
def register_admin(admin: AdminCreate, db: Session = Depends(get_db)):
    # Validate admin invite/secret code if ADMIN_INVITE_CODE is configured
    expected_code = os.getenv("ADMIN_INVITE_CODE", "ADMIN2026")
    if admin.admin_code and admin.admin_code.strip() != expected_code.strip():
        raise HTTPException(status_code=403, detail="Invalid admin authorization code")

    db_user = db.query(models.User).filter(models.User.email == admin.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_admin = models.User(
        full_name=admin.full_name,
        mobile_no=admin.mobile_no or "N/A",
        email=admin.email,
        address=admin.address or "Administrative HQ",
        city=admin.city or "City Center",
        state=admin.state or "State",
        pincode=admin.pincode or "000000",
        hashed_password=admin.password,
        role="admin"
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    token = create_access_token(user_id=new_admin.id, role="admin")
    return {
        "message": "Admin registered successfully",
        "user_id": new_admin.id,
        "role": "admin",
        "access_token": token,
        "token_type": "bearer"
    }

@app.post("/api/auth/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or db_user.hashed_password != user.password:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # Block login for unverified citizen accounts
    if not db_user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in."
        )

    role = db_user.role or "citizen"
    token = create_access_token(user_id=db_user.id, role=role)
    return {
        "message": "Login successful",
        "user_id": db_user.id,
        "full_name": db_user.full_name,
        "role": role,
        "access_token": token,
        "token_type": "bearer"
    }

class VerifyEmailRequest(BaseModel):
    email: str
    code: str

class ResendVerificationRequest(BaseModel):
    email: str

@app.post("/api/auth/verify-email")
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == req.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="No account found with this email.")
    if db_user.is_verified:
        return {"message": "Email is already verified. Please log in."}
    if not db_user.verification_code or db_user.verification_code != req.code:
        raise HTTPException(status_code=400, detail="Invalid verification code.")
    if not db_user.verification_code_expires_at or \
       datetime.datetime.now() > db_user.verification_code_expires_at:
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired. Please request a new code."
        )
    # Mark as verified and clear the code
    db_user.is_verified = True
    db_user.verification_code = None
    db_user.verification_code_expires_at = None
    db.commit()
    return {"message": "Email verified successfully. You can now log in."}

@app.post("/api/auth/resend-verification")
def resend_verification(req: ResendVerificationRequest, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == req.email).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="No account found with this email.")
    if db_user.is_verified:
        return {"message": "Email is already verified. Please log in."}
    # Generate fresh code and reset expiry
    new_code = str(secrets.randbelow(1000000)).zfill(6)
    db_user.verification_code = new_code
    db_user.verification_code_expires_at = datetime.datetime.now() + datetime.timedelta(minutes=10)
    db.commit()
    send_verification_email(db_user.email, db_user.full_name, new_code)
    return {"message": "A new verification code has been sent to your email."}

# --- USER PROFILE ENDPOINTS ---

@app.get("/api/users/me/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "full_name": user.full_name,
        "mobile_no": user.mobile_no,
        "email": user.email,
        "address": user.address,
        "city": user.city,
        "state": user.state,
        "pincode": user.pincode,
        "role": user.role or "citizen",
        "profile_image_url": user.profile_image_url
    }

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    mobile_no: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

@app.put("/api/users/update/{user_id}")
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return {"message": "User updated successfully", "user": {
        "id": db_user.id,
        "full_name": db_user.full_name,
        "mobile_no": db_user.mobile_no,
        "email": db_user.email,
        "address": db_user.address,
        "city": db_user.city,
        "state": db_user.state,
        "pincode": db_user.pincode,
        "profile_image_url": db_user.profile_image_url
    }}

@app.post("/api/users/profile-image/{user_id}")
async def upload_profile_image(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"profile_{user_id}_{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("uploads", unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        image_url = f"/uploads/{unique_filename}"
        db_user.profile_image_url = image_url
        db.commit()
        
        return {"profile_image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/stats/{user_id}")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # In a real app, these would be calculated from actual data.
    # For demonstration, we'll return some dynamic-ish stats based on the user's complaints.
    
    complaints = db.query(models.Complaint).filter(models.Complaint.citizen_name == db_user.full_name).all()
    total_complaints = len(complaints)
    resolved_complaints = sum(1 for c in complaints if c.status == "Resolved")
    
    # Contribution score: 10 points per complaint, 50 points per resolved complaint
    contribution_score = (total_complaints * 10) + (resolved_complaints * 50)
    
    # Community level based on score
    level = "Novice Citizen"
    if contribution_score > 500: level = "Elite Guardian"
    elif contribution_score > 200: level = "Active Reformer"
    elif contribution_score > 50: level = "Responsible Citizen"
    
    return {
        "complaints_submitted": total_complaints,
        "resolved_complaints": resolved_complaints,
        "contribution_score": contribution_score,
        "community_level": level,
        "participation_percent": min(100, 20 + (total_complaints * 5)),
        "badges": [
            {"id": 1, "name": "First Reporter", "icon": "🏅", "earned": total_complaints > 0},
            {"id": 2, "name": "Problem Solver", "icon": "🛠️", "earned": resolved_complaints > 0},
            {"id": 3, "name": "Top Contributor", "icon": "⭐", "earned": contribution_score > 300},
            {"id": 4, "name": "Verification Pro", "icon": "✅", "earned": True}
        ]
    }

class ChatMessage(BaseModel):
    message: str

@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    try:
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join("uploads", unique_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"image_url": f"/uploads/{unique_filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/complaints", response_model=ComplaintResponse)
def submit_complaint(
    complaint: ComplaintCreate, 
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    # Derive user_id from JWT if present and valid
    user_id = complaint.user_id
    if authorization and authorization.strip().lower().startswith("bearer "):
        token = authorization.strip()[7:].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            jwt_user_id = payload.get("user_id")
            if jwt_user_id is not None:
                user_id = jwt_user_id
        except Exception as e:
            print(f"[Backend] JWT decode in complaint submission failed or expired: {e}")

    local_image_path = None
    if complaint.image_url and "uploads/" in complaint.image_url:
        filename = complaint.image_url.split("uploads/")[-1]
        local_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", filename)

    text_val = complaint.text or ""
    print(f"\n[AI Workflow] Fresh submission detected. Triggering ONE-TIME Gemini analysis...")
    
    try:
        ai_result = ai_engine.validate_and_summarize_grievance(text_val, local_image_path)
    except Exception as ai_err:
        print(f"[Backend] AI Analysis CRASHED. Using emergency fallback: {ai_err}")
        from ai_engine import get_fallback_analysis
        ai_result = get_fallback_analysis(text_val, str(ai_err))

    print(f"[Backend] AI Analysis Result keys: {list(ai_result.keys())}")
    print(f"[Backend] AI Title: {ai_result.get('title')} | Dept: {ai_result.get('department')} | Severity: {ai_result.get('severity')}")

    # Map AI engine output (new schema) to DB fields
    title         = ai_result.get("title") or "Grievance Report"
    department    = ai_result.get("department") or "Public Works Department"
    summary       = ai_result.get("summary") or ""
    category      = ai_result.get("category") or "General Issue"
    severity      = ai_result.get("severity") or "Medium"
    sentiment     = ai_result.get("sentiment") or "Concerned"
    risks         = ai_result.get("risks") or ""
    confidence    = ai_result.get("confidence_score") or 0  # already 0-100 int
    image_obs     = ai_result.get("image_observation") or ""
    detected_iss  = ai_result.get("detected_issue") or title

    db_complaint = models.Complaint(
        citizen_name=complaint.citizen_name,
        user_id=user_id,
        title=title,
        original_text=text_val,
        translated_text=text_val,
        department=department,
        priority=severity,
        sentiment=sentiment,
        estimated_resolution_time="2-4 Days",
        ai_summary=summary,
        detected_issue=detected_iss,
        category=category,
        visual_risk_level=severity,
        issue_tags=risks if isinstance(risks, str) else ", ".join(risks),
        confidence_score=confidence,
        image_observation=image_obs,
        official_remarks=None,
        latitude=complaint.latitude,
        longitude=complaint.longitude,
        address=complaint.address,
        pincode=complaint.pincode,
        image_url=complaint.image_url,
        created_at=datetime.datetime.now()
    )
    db.add(db_complaint)
    db.commit()
    db.refresh(db_complaint)
    print(f"[Backend] Saved complaint ID={db_complaint.id} | Title={db_complaint.title} | Dept={db_complaint.department}")
    return db_complaint

@app.get("/api/complaints", response_model=List[ComplaintResponse])
def get_complaints(db: Session = Depends(get_db)):
    print(f"[AI Workflow] Fetching complaint list. REUSING stored AI analysis from database. No Gemini calls triggered.")
    complaints = db.query(models.Complaint).order_by(models.Complaint.id.desc()).all()
    return complaints

@app.get("/api/my-complaints", response_model=List[ComplaintResponse])
def get_my_complaints(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    complaints = db.query(models.Complaint)\
        .filter(models.Complaint.user_id == current_user.id)\
        .order_by(models.Complaint.id.desc())\
        .all()
    return complaints

ALLOWED_COMPLAINT_STATUSES = {"Pending", "Approved", "Rejected", "In Progress", "Completed"}

ALLOWED_STATUS_TRANSITIONS = {
    "Pending": {"Approved", "Rejected"},
    "Approved": {"In Progress", "Completed"},
    "In Progress": {"Completed"},
}

@app.patch("/api/complaints/{complaint_id}/status", response_model=ComplaintResponse)
def update_complaint_status(
    complaint_id: int, 
    update: ComplaintStatusUpdate, 
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(require_admin)
):
    complaint = db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    new_status = update.status.strip() if update.status else ""
    if new_status not in ALLOWED_COMPLAINT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Allowed statuses: {', '.join(sorted(ALLOWED_COMPLAINT_STATUSES))}"
        )

    current_status = complaint.status
    allowed_next = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from '{current_status}' to '{new_status}'"
        )

    try:
        complaint.status = new_status
        if update.official_remarks is not None:
            complaint.official_remarks = update.official_remarks
        db.commit()
        db.refresh(complaint)
        print(f"[Backend] Updated Complaint ID={complaint.id} status from '{current_status}' to '{new_status}' by Admin {admin_user.full_name} (ID: {admin_user.id})")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update complaint status")

    # Send resolution email ONLY when transitioning to "Completed" and was not previously "Completed"
    if current_status != "Completed" and new_status == "Completed":
        if complaint.user_id:
            try:
                owner = db.query(models.User).filter(models.User.id == complaint.user_id).first()
                if owner and owner.email:
                    send_completion_email(
                        to_email=owner.email,
                        citizen_name=owner.full_name or complaint.citizen_name or "Citizen",
                        complaint_id=complaint.id,
                        complaint_title=complaint.title or complaint.original_text[:80] or "Civic Grievance",
                        description=complaint.original_text or "",
                        category=complaint.category or "General Infrastructure",
                        department=complaint.department or "Public Works",
                        priority=complaint.priority or "Medium",
                        official_remarks=complaint.official_remarks,
                        created_at=complaint.created_at
                    )
                else:
                    print(f"[Email] EMAIL FAILED: Owner User ID {complaint.user_id} not found or missing email address.")
            except Exception as email_err:
                safe_err = str(email_err)
                if MAIL_PASSWORD and MAIL_PASSWORD in safe_err:
                    safe_err = safe_err.replace(MAIL_PASSWORD, "******")
                print(f"[Email] EMAIL FAILED: {safe_err}")
        else:
            print(f"[Email] EMAIL FAILED: Complaint #{complaint.id} has no registered user_id (submitted anonymously).")

    return complaint

@app.get("/api/analytics")
def get_analytics(db: Session = Depends(get_db)):
    print(f"[AI Workflow] Loading analytics. Reading historical AI metrics from database. No Gemini calls triggered.")
    complaints = db.query(models.Complaint).all()
    
    departments = {}
    priorities = {}
    total = len(complaints)
    resolved = 0
    
    for c in complaints:
        departments[c.department] = departments.get(c.department, 0) + 1
        priorities[c.priority] = priorities.get(c.priority, 0) + 1
        if c.status == "Resolved":
            resolved += 1
            
    return {
        "total": total,
        "resolved": resolved,
        "departments": departments,
        "priorities": priorities
    }

@app.post("/api/chat")
def chat_with_bot(chat: ChatMessage):
    reply = ai_engine.chatbot_reply([], chat.message)
    return {"reply": reply}


# ─── Animal Welfare Endpoints ───────────────────────────────────────────

class AnimalReportCreate(BaseModel):
    description: str
    address: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    media_url: Optional[str] = None
    user_id: Optional[int] = 1

class AnimalReportResponse(BaseModel):
    id: int
    description: str
    address: Optional[str]
    latitude: Optional[str]
    longitude: Optional[str]
    media_url: Optional[str]
    
    # New AI Fields
    detected_animal: Optional[str]
    animal_condition: Optional[str]
    possible_injury: Optional[str]
    urgency_level: Optional[str]
    rescue_priority: Optional[str]
    health_risks: Optional[str]
    recommended_action: Optional[str]
    nearest_ngo: Optional[str]
    eta: Optional[str]
    ai_summary: Optional[str]
    confidence_score: Optional[str]

    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

@app.post("/api/animal-reports", response_model=AnimalReportResponse)
def submit_animal_report(report: AnimalReportCreate, db: Session = Depends(get_db)):
    local_image_path = None
    if report.media_url and "uploads/" in report.media_url:
        filename = report.media_url.split("uploads/")[-1]
        local_image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", filename)

    print(f"\n[Animal Welfare] Processing new report. Image: {local_image_path or 'No'}")
    try:
        ai_result = ai_engine.analyze_animal_welfare(report.description, local_image_path)
    except Exception as ai_err:
        print(f"[Backend] Animal Welfare AI CRASHED. Using fallback: {ai_err}")
        from ai_engine import get_animal_fallback
        ai_result = get_animal_fallback(report.description, str(ai_err))
    
    # Map AI results to DB model
    # Convert lists to strings for storage
    injuries = ai_result.get("possible_injuries", [])
    risks = ai_result.get("health_risks", [])
    
    db_report = models.AnimalReport(
        user_id=report.user_id,
        description=report.description,
        address=report.address,
        latitude=report.latitude,
        longitude=report.longitude,
        media_url=report.media_url,
        detected_animal=ai_result.get("detected_animal"),
        animal_condition=ai_result.get("animal_condition"),
        possible_injury=", ".join(injuries) if isinstance(injuries, list) else str(injuries),
        urgency_level=ai_result.get("urgency_level"),
        rescue_priority=ai_result.get("rescue_priority"),
        health_risks=", ".join(risks) if isinstance(risks, list) else str(risks),
        recommended_action=ai_result.get("recommended_action"),
        nearest_ngo=ai_result.get("nearest_rescue_type"),
        eta=ai_result.get("estimated_rescue_eta"),
        ai_summary=ai_result.get("summary"),
        confidence_score=str(ai_result.get("confidence_score", "0.90")),
        status="Report Submitted",
        created_at=datetime.datetime.now()
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    print(f"[Animal Welfare] Report ID {db_report.id} saved with AI analysis.")
    return db_report

@app.get("/api/animal-reports", response_model=List[AnimalReportResponse])
def get_animal_reports(db: Session = Depends(get_db)):
    reports = db.query(models.AnimalReport).order_by(models.AnimalReport.id.desc()).all()
    return reports

@app.get("/api/animal-reports/{report_id}", response_model=AnimalReportResponse)
def get_animal_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(models.AnimalReport).filter(models.AnimalReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

@app.get("/api/animal-analytics")
def get_animal_analytics(db: Session = Depends(get_db)):
    reports = db.query(models.AnimalReport).all()
    return {
        "total": len(reports),
        "animals_saved": max(0, len(reports) - 2),
        "active_reports": sum(1 for r in reports if r.status == "Report Submitted"),
    }

# ─── Government Schemes Endpoints ──────────────────────────────────────────

class SchemeCreate(BaseModel):
    name: str
    description: str
    category: str
    type: str # Central or State
    state: Optional[str] = None
    eligibility_summary: Optional[str] = None
    benefits: Optional[str] = None
    launch_year: Optional[int] = None
    website_url: Optional[str] = None
    application_steps: Optional[str] = None
    icon_type: Optional[str] = "default"

class SchemeResponse(BaseModel):
    id: int
    name: str
    description: str
    category: str
    type: str
    state: Optional[str]
    eligibility_summary: Optional[str]
    benefits: Optional[str]
    launch_year: Optional[int]
    website_url: Optional[str]
    application_steps: Optional[str]
    icon_type: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

@app.post("/api/schemes", response_model=SchemeResponse)
def create_scheme(scheme: SchemeCreate, db: Session = Depends(get_db)):
    new_scheme = models.Scheme(**scheme.dict())
    db.add(new_scheme)
    
    # Create notification for new scheme
    notification_title = f"New {scheme.type} Scheme: {scheme.name}"
    notification_content = f"A new government scheme '{scheme.name}' has been added in the {scheme.category} category."
    if scheme.state:
        notification_title = f"New State Scheme: {scheme.name} ({scheme.state})"
        
    new_notif = models.Notification(
        title=notification_title,
        content=notification_content,
        category="Scheme",
        link="/gov-schemes"
    )
    db.add(new_notif)
    
    db.commit()
    db.refresh(new_scheme)
    return new_scheme

@app.get("/api/schemes", response_model=List[SchemeResponse])
def get_schemes(type: Optional[str] = None, state: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Scheme)
    if type:
        query = query.filter(models.Scheme.type == type)
    if state:
        query = query.filter(models.Scheme.state == state)
    return query.order_by(models.Scheme.id.desc()).all()

@app.delete("/api/schemes/{scheme_id}")
def delete_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = db.query(models.Scheme).filter(models.Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    db.delete(scheme)
    db.commit()
    return {"message": "Scheme deleted"}

# ─── Notifications Endpoints ──────────────────────────────────────────────

class NotificationResponse(BaseModel):
    id: int
    title: str
    content: str
    category: Optional[str]
    state: Optional[str]
    priority: str
    linked_scheme_id: Optional[int]
    link: Optional[str]
    is_read: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class DonationCampaignResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    location: str
    ngo_name: str
    is_verified: int
    verification_type: str
    urgency_level: str
    amount_raised: int
    target_amount: int
    contributor_count: int
    impact_metrics: Optional[str]
    image_url: Optional[str]
    expiry_date: Optional[datetime.datetime]
    related_complaint_category: Optional[str]
    moderation_status: str
    risk_score: str
    ai_fraud_reason: Optional[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class SmartDonationResponse(DonationCampaignResponse):
    smart_label: Optional[str] = None
    ai_reason: Optional[str] = None
    match_score: Optional[int] = 0

@app.get("/api/notifications", response_model=List[NotificationResponse])
def get_notifications(state: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.Notification)
    if state:
        # Show specific state notifications + Central/System notifications (where state is None)
        query = query.filter((models.Notification.state == state) | (models.Notification.state == None))
    return query.order_by(models.Notification.id.desc()).limit(20).all()

@app.get("/api/donations", response_model=List[DonationCampaignResponse])
def get_donations(state: Optional[str] = None, category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.DonationCampaign)
    if state:
        query = query.filter(models.DonationCampaign.location == state)
    if category:
        query = query.filter(models.DonationCampaign.related_complaint_category == category)
    return query.order_by(models.DonationCampaign.id.desc()).all()

@app.get("/api/donations/smart-match", response_model=List[SmartDonationResponse])
def get_smart_donations(state: Optional[str] = None, interests: Optional[str] = None, db: Session = Depends(get_db)):
    import json
    from sqlalchemy import func
    
    # Parse user interests
    user_interests = {}
    if interests:
        try:
            user_interests = json.loads(interests)
        except:
            pass

    # Identify top trending civic issue
    trending = db.query(models.Complaint.department, func.count(models.Complaint.id).label('cnt'))\
                 .group_by(models.Complaint.department)\
                 .order_by(func.count(models.Complaint.id).desc()).first()
    trending_category = trending.department if trending else None

    # Fetch all campaigns
    campaigns = db.query(models.DonationCampaign).all()
    ranked_campaigns = []

    for camp in campaigns:
        score = 0
        ai_reason = ""
        smart_label = ""
        
        # 1. Location Relevance
        if state and camp.location == state:
            score += 15
            ai_reason = f"Prioritized due to urgent needs in your selected region ({state})."
            smart_label = "Trending Near You"

        # 2. User Interest Mapping
        matched_interest_score = 0
        if camp.related_complaint_category in user_interests:
            matched_interest_score = user_interests[camp.related_complaint_category]
        elif camp.category in user_interests:
            matched_interest_score = user_interests[camp.category]
            
        if matched_interest_score > 0:
            score += matched_interest_score * 2 # Weighting interest
            if score >= 15 and not smart_label:
                smart_label = "Recommended For You"
                ai_reason = f"Matches your active civic interest in {camp.category or camp.related_complaint_category}."
            elif not smart_label:
                smart_label = "Based On Your Activity"
                ai_reason = "Recommended based on your recent engagement patterns."

        # 3. Civic Trend
        if trending_category and camp.related_complaint_category == trending_category:
            score += 10
            if not smart_label:
                smart_label = "High Civic Impact"
                ai_reason = f"High priority: Addresses the current surge in {trending_category} reports."

        # 4. Urgency
        if camp.urgency_level == "Critical":
            score += 10
            if not smart_label:
                smart_label = "Emergency Priority"
                ai_reason = "Critical emergency requiring immediate community intervention."
        elif camp.urgency_level == "Urgent":
            score += 5
            
        # Fallback
        if not smart_label:
            smart_label = "Community Support"
            ai_reason = "Support a verified local initiative."

        # Add to ranked list
        camp_dict = camp.__dict__.copy()
        camp_dict['match_score'] = score
        camp_dict['smart_label'] = smart_label
        camp_dict['ai_reason'] = ai_reason
        ranked_campaigns.append(camp_dict)

    # Sort by score descending
    ranked_campaigns.sort(key=lambda x: x['match_score'], reverse=True)
    return ranked_campaigns

# --- SOCIAL HELP & COMMUNITY SUPPORT ---

@app.post("/api/social-help/report")
async def report_social_help(
    description: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    media_url = None
    if file:
        file_ext = os.path.splitext(file.filename)[1]
        file_id = str(uuid.uuid4())
        file_path = f"uploads/{file_id}{file_ext}"
        os.makedirs("uploads", exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        media_url = f"http://localhost:8000/{file_path}"
    else:
        file_path = None

    from ai_engine import assess_social_help_case, get_social_fallback
    try:
        ai_result = assess_social_help_case(description, file_path)
    except Exception as ai_err:
        print(f"[Backend] Social Help AI CRASHED. Using fallback: {ai_err}")
        ai_result = get_social_fallback(description, str(ai_err))

    new_case = models.SocialHelpCase(
        description=description,
        media_url=media_url,
        detected_category=ai_result.get("detected_category"),
        priority_level=ai_result.get("priority_level"),
        behavior_analysis=ai_result.get("behavior_analysis"),
        sentiment_score=ai_result.get("sentiment_score"),
        status="Pending Assessment"
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    return {
        "success": True,
        "case_id": new_case.id,
        "assessment": ai_result
    }

@app.get("/api/social-help/stats")
def get_social_help_stats(db: Session = Depends(get_db)):
    # Simulating aggregated impact metrics
    return {
        "people_helped": { "value": 1240, "change": "+28%" },
        "ngos_active": { "value": 45, "change": "Active in your area" },
        "reports_received": { "value": 312, "change": "+10%" },
        "reunited": { "value": 85, "change": "+40%" }
    }

# --- SEED DATA (For Demonstration) ---

@app.post("/api/donations/validate")
def validate_donation(campaign: dict, db: Session = Depends(get_db)):
    """Simulates receiving a new campaign submission and running AI fraud detection."""
    title = campaign.get("title", "")
    desc = campaign.get("description", "")
    target = campaign.get("target_amount", 0)
    cat = campaign.get("category", "")
    
    from ai_engine import validate_donation_campaign
    ai_result = validate_donation_campaign(title, desc, target, cat)
    return ai_result

@app.get("/api/donations/recommendations")
def get_donation_recommendations(db: Session = Depends(get_db)):
    # Simple AI Logic: Identify trending complaint categories and recommend matching campaigns
    from sqlalchemy import func
    trending = db.query(models.Complaint.department, func.count(models.Complaint.id).label('cnt'))\
                 .group_by(models.Complaint.department)\
                 .order_by(func.count(models.Complaint.id).desc()).first()
    
    if not trending:
        return {"trending_category": "General", "recommendation": "Community Welfare", "campaign_count": 0}
    
    count = db.query(models.DonationCampaign).filter(models.DonationCampaign.related_complaint_category == trending.department).count()
    
    return {
        "trending_category": trending.department,
        "recommendation": f"Most Needed Support: {trending.department} Drive",
        "reason": f"Based on recent increase in {trending.department} reports.",
        "campaign_count": count
    }

@app.get("/api/donations/hotspots")
def get_donations_hotspots(db: Session = Depends(get_db)):
    # Group complaints by state to find hotspots
    from sqlalchemy import func
    hotspots_data = db.query(
        models.Complaint.state,
        func.count(models.Complaint.id).label('count'),
        models.Complaint.department,
        func.max(models.Complaint.priority).label('max_priority')
    ).group_by(models.Complaint.state, models.Complaint.department).all()

    # Process into hotspots
    hotspots = []
    processed_states = {}

    # Coordinate mapping for Indian states (Approx centers for heatmap)
    coords = {
        "Madhya Pradesh": [23.2599, 77.4126],
        "Maharashtra": [19.7507, 75.7139],
        "Delhi": [28.6139, 77.2090],
        "Uttar Pradesh": [26.8467, 80.9462],
        "Rajasthan": [27.0238, 74.2179],
        "Gujarat": [22.2587, 71.1924],
        "Karnataka": [15.3173, 75.7139],
        "Tamil Nadu": [11.1271, 78.6569],
        "West Bengal": [22.9868, 87.8550],
        "Bihar": [25.0961, 85.3131]
    }

    for state, count, dept, priority in hotspots_data:
        if state not in coords: continue
        
        if state not in processed_states:
            # Determine risk level
            risk_level = "Low Risk"
            intensity = count * 10
            if count > 5: risk_level = "Critical Zone"
            elif count > 3: risk_level = "High Risk"
            elif count > 1: risk_level = "Moderate Risk"

            # Find related campaign
            campaign = db.query(models.DonationCampaign).filter(
                (models.DonationCampaign.location == state) | 
                (models.DonationCampaign.related_complaint_category == dept)
            ).first()

            processed_states[state] = {
                "id": state,
                "location": state,
                "coords": coords[state],
                "complaint_count": count,
                "main_issue": dept,
                "risk_level": risk_level,
                "intensity": min(100, intensity),
                "ai_summary": f"{dept} reports are significantly high in {state} currently. Immediate community awareness is recommended.",
                "related_campaign": {
                    "id": campaign.id,
                    "title": campaign.title
                } if campaign else None
            }
        else:
            processed_states[state]["complaint_count"] += count
    
    return list(processed_states.values())

@app.post("/api/notifications/{notif_id}/read")
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(models.Notification).filter(models.Notification.id == notif_id).first()
    if notif:
        notif.is_read = 1
        db.commit()
    return {"message": "Marked as read"}

# Seed initial schemes if none exist
@app.on_event("startup")
def seed_data():
    db = database.SessionLocal()
    if db.query(models.Scheme).count() == 0:
        schemes_data = [
            # CENTRAL SCHEMES
            {
                "name": "PM Kisan Samman Nidhi",
                "description": "Income support to all landholding farmers' families in the country.",
                "category": "Agriculture",
                "type": "Central",
                "eligibility_summary": "All small and marginal farmers' families.",
                "benefits": "Rs. 6000 per year in three equal installments.",
                "launch_year": 2019,
                "website_url": "https://pmkisan.gov.in/",
                "application_steps": "1. Visit PM-Kisan Portal\n2. New Farmer Registration\n3. Fill Aadhaar details\n4. Submit land records."
            },
            {
                "name": "Ayushman Bharat PM-JAY",
                "description": "Health insurance cover for secondary and tertiary care hospitalization.",
                "category": "Health",
                "type": "Central",
                "benefits": "Health cover of Rs. 5 lakh per family per year.",
                "eligibility_summary": "Low-income families identified by SECC.",
                "launch_year": 2018,
                "website_url": "https://nha.gov.in/",
                "application_steps": "1. Check eligibility on portal\n2. Visit Empaneled Hospital\n3. Show Ayushman Card\n4. Get cashless treatment."
            },
            {
                "name": "PM Awas Yojana (Urban)",
                "description": "Housing for all in urban areas with credit linked interest subsidy.",
                "category": "Housing",
                "type": "Central",
                "benefits": "Interest subsidy on home loans.",
                "eligibility_summary": "EWS, LIG, and MIG families without a pucca house.",
                "launch_year": 2015,
                "website_url": "https://pmay-urban.gov.in/",
                "application_steps": "1. Register on PMAY portal\n2. Fill Citizen Assessment\n3. Apply for home loan\n4. Submit required docs."
            },
            {
                "name": "PM Internship Scheme",
                "description": "Internship opportunities in top companies for skill development.",
                "category": "Education & Employment",
                "type": "Central",
                "benefits": "Rs. 5000 monthly stipend + one-time assistance.",
                "eligibility_summary": "Youth aged 21-24 not in full-time jobs.",
                "launch_year": 2024,
                "website_url": "https://pminternship.mca.gov.in/",
                "application_steps": "1. Register on portal\n2. Fill profile\n3. Apply to companies\n4. Join after selection."
            },
            # MAHARASHTRA
            {
                "name": "Majhi Ladki Bahin Yojana",
                "description": "Monthly financial aid to women for empowerment.",
                "category": "Social Welfare",
                "type": "State",
                "state": "Maharashtra",
                "benefits": "Rs. 1500 per month directly to bank account.",
                "eligibility_summary": "Women aged 21-65, annual family income < 2.5 Lakh.",
                "launch_year": 2024,
                "website_url": "https://ladakibahin.maharashtra.gov.in/",
                "application_steps": "1. Apply via Nari Shakti Dhoot App\n2. Fill personal info\n3. Upload income certificate\n4. Verification."
            },
            # UTTAR PRADESH
            {
                "name": "Kanya Sumangala Yojana",
                "description": "Cash incentive for the birth and education of girl children.",
                "category": "Education",
                "type": "State",
                "state": "Uttar Pradesh",
                "benefits": "Rs. 15,000 in six stages from birth to graduation.",
                "eligibility_summary": "Residents of UP with annual income < 3 Lakh.",
                "launch_year": 2019,
                "website_url": "https://mksy.up.gov.in/",
                "application_steps": "1. Register on portal\n2. Apply for relevant stage\n3. Upload birth/edu docs\n4. DBT transfer."
            },
            # RAJASTHAN
            {
                "name": "Chiranjeevi Health Insurance",
                "description": "Cashless medical insurance for all families in Rajasthan.",
                "category": "Health",
                "type": "State",
                "state": "Rajasthan",
                "benefits": "Up to Rs. 25 lakh cashless treatment.",
                "eligibility_summary": "All permanent residents of Rajasthan.",
                "launch_year": 2021,
                "website_url": "https://chiranjeevi.rajasthan.gov.in/",
                "application_steps": "1. Register on SSO portal\n2. Link Jan Aadhaar\n3. Select health insurance\n4. Print policy card."
            },
            # DELHI
            {
                "name": "Delhi Ladli Scheme",
                "description": "Financial security for girl children from birth to education.",
                "category": "Social Welfare",
                "type": "State",
                "state": "Delhi",
                "benefits": "Financial maturity amount on reaching age 18.",
                "eligibility_summary": "Girl child born in Delhi, family income < 1 Lakh.",
                "launch_year": 2008,
                "website_url": "https://wcd.delhi.gov.in/",
                "application_steps": "1. Apply through hospital/school\n2. Submit income proof\n3. Get registration number\n4. Renew at each stage."
            },
            # GUJARAT
            {
                "name": "Shravan Tirthdarshan Yojana",
                "description": "Subsidized pilgrimage for senior citizens of Gujarat.",
                "category": "Social Welfare",
                "type": "State",
                "state": "Gujarat",
                "benefits": "75% subsidy on travel cost by bus.",
                "eligibility_summary": "Citizens aged 60+, permanent residents of Gujarat.",
                "launch_year": 2017,
                "website_url": "https://gujaratindia.gov.in/",
                "application_steps": "1. Fill application form\n2. Submit age/resident proof\n3. Travel in groups\n4. Claim reimbursement."
            },
            # KARNATAKA
            {
                "name": "Gruha Lakshmi Yojana",
                "description": "Direct benefit transfer to women heads of families.",
                "category": "Social Welfare",
                "type": "State",
                "state": "Karnataka",
                "benefits": "Rs. 2000 per month for household expenses.",
                "eligibility_summary": "Woman head of family with BPL/APL/Antyodaya card.",
                "launch_year": 2023,
                "website_url": "https://sevasindhu.karnataka.gov.in/",
                "application_steps": "1. Visit Seva Sindhu portal\n2. Register mobile number\n3. Link Ration card & Bank A/C\n4. Track status."
            },
            # MADHYA PRADESH
            {
                "name": "Ladli Behna Yojana",
                "description": "Financial aid for women's health and empowerment in MP.",
                "category": "Social Welfare",
                "type": "State",
                "state": "Madhya Pradesh",
                "benefits": "Rs. 1250 per month directly to account.",
                "eligibility_summary": "Married women residents, age 21-60.",
                "launch_year": 2023,
                "website_url": "https://cmladlibehna.mp.gov.in/",
                "application_steps": "1. Visit nearest Anganwadi\n2. Submit e-KYC\n3. Fill form\n4. Approval."
            }
        ]

        # Add generic schemes for other states to ensure coverage
        other_states = [
            "Tamil Nadu", "Bihar", "Punjab", "Haryana", "West Bengal", "Kerala", "Assam", 
            "Odisha", "Telangana", "Andhra Pradesh", "Chhattisgarh", "Uttarakhand", 
            "Himachal Pradesh", "Jammu & Kashmir", "Jharkhand", "Goa", "Sikkim", 
            "Nagaland", "Manipur", "Mizoram", "Tripura", "Meghalaya", "Arunachal Pradesh"
        ]
        
        for state in other_states:
            schemes_data.append({
                "name": f"Mukhyamantri Jan Kalyan Yojana - {state}",
                "description": f"A comprehensive welfare scheme for the citizens of {state} to ensure social security.",
                "category": "Social Welfare",
                "type": "State",
                "state": state,
                "benefits": "Various subsidies on education, health, and basic amenities.",
                "eligibility_summary": f"Permanent residents of {state}.",
                "launch_year": 2022,
                "website_url": f"https://{state.lower().replace(' ', '')}.gov.in/",
                "application_steps": "1. Visit State Portal\n2. Login with Jan Aadhaar/Ration Card\n3. Select scheme\n4. Apply."
            })

        for s in schemes_data:
            db_scheme = models.Scheme(**s)
            db.add(db_scheme)
        
        # Add initial notifications
        # Fetch some schemes to link them
        pm_kisan = db.query(models.Scheme).filter(models.Scheme.name == "PM Kisan Samman Nidhi").first()
        ladli_behna = db.query(models.Scheme).filter(models.Scheme.name == "Ladli Behna Yojana").first()
        kanya_sumangala = db.query(models.Scheme).filter(models.Scheme.name == "Kanya Sumangala Yojana").first()

        notifs = [
            models.Notification(
                title="Welcome to CitizenConnect",
                content="Explore government schemes and report civic issues easily. Your AI assistant is here to help.",
                category="System",
                priority="Normal"
            ),
            models.Notification(
                title="PM Kisan Installment Update",
                content="The next installment of PM Kisan Samman Nidhi is being processed. Check your status.",
                category="Scheme",
                priority="High",
                linked_scheme_id=pm_kisan.id if pm_kisan else None
            ),
            models.Notification(
                title="Ladli Behna Deadline Alert",
                content="MP Ladli Behna Yojana Phase 3 registration is closing soon. Apply now to avoid missing out.",
                category="Urgent",
                state="Madhya Pradesh",
                priority="Urgent",
                linked_scheme_id=ladli_behna.id if ladli_behna else None
            ),
            models.Notification(
                title="Kanya Sumangala New Stage Open",
                content="Applications for Stage 4 of Kanya Sumangala Yojana are now being accepted in UP.",
                category="Scheme",
                state="Uttar Pradesh",
                priority="Normal",
                linked_scheme_id=kanya_sumangala.id if kanya_sumangala else None
            ),
            models.Notification(
                title="Emergency Relief Fund - Monsoon",
                content="Central government has announced emergency relief funds for flood-affected areas.",
                category="Emergency",
                priority="Urgent"
            )
        ]
        db.add_all(notifs)
        db.commit()

        # Add donation campaigns
        campaigns = [
            models.DonationCampaign(
                title="Bhopal Flood Relief 2026",
                description="Emergency support for families affected by heavy monsoon floods in Bhopal region.",
                category="Disaster Relief",
                location="Madhya Pradesh",
                ngo_name="MP Seva Sansthan",
                urgency_level="Critical",
                amount_raised=125000,
                target_amount=500000,
                contributor_count=142,
                impact_metrics="400 Families Fed",
                verification_type="Government Verified",
                related_complaint_category="Roads & Infrastructure", # Flood related to drainage/roads
                expiry_date=datetime.datetime.now() + datetime.timedelta(days=15)
            ),
            models.DonationCampaign(
                title="Mumbai Stray Animal Rescue",
                description="Medical aid and shelter support for injured stray animals in South Mumbai.",
                category="Animal Welfare",
                location="Maharashtra",
                ngo_name="PawFriends NGO",
                urgency_level="Urgent",
                amount_raised=45000,
                target_amount=100000,
                contributor_count=89,
                impact_metrics="12 Animals Treated",
                verification_type="NGO Verified",
                related_complaint_category="Animal Welfare",
                expiry_date=datetime.datetime.now() + datetime.timedelta(days=7)
            ),
            models.DonationCampaign(
                title="Delhi Smart School Kit Drive",
                description="Providing digital learning kits to underprivileged students in East Delhi.",
                category="Education",
                location="Delhi",
                ngo_name="Shiksha Foundation",
                urgency_level="Community Support",
                amount_raised=210000,
                target_amount=300000,
                contributor_count=256,
                impact_metrics="150 Kits Distributed",
                verification_type="Transparency Verified",
                related_complaint_category="Education",
                expiry_date=datetime.datetime.now() + datetime.timedelta(days=30)
            ),
            models.DonationCampaign(
                title="Bangalore Green Cleanup Drive",
                description="Restoring local parks and lakes in Bangalore through community participation.",
                category="Sanitation",
                location="Karnataka",
                ngo_name="GreenCity Warriors",
                urgency_level="Community Support",
                amount_raised=15000,
                target_amount=50000,
                contributor_count=45,
                impact_metrics="2 Lakes Restored",
                verification_type="NGO Verified",
                related_complaint_category="Sanitation",
                expiry_date=datetime.datetime.now() + datetime.timedelta(days=10),
                moderation_status="Approved",
                risk_score="Low Risk"
            ),
            models.DonationCampaign(
                title="Global Mega Tech Initiative",
                description="Please donate 50 crores for me to buy computers and clean a local street.",
                category="Technology",
                location="Delhi",
                ngo_name="Unknown Entity",
                urgency_level="Critical",
                amount_raised=5000,
                target_amount=500000000,
                contributor_count=2,
                impact_metrics=None,
                verification_type="Unverified",
                related_complaint_category="Sanitation",
                expiry_date=datetime.datetime.now() + datetime.timedelta(days=3),
                moderation_status="Under Review",
                risk_score="High Risk",
                ai_fraud_reason="Highly unrealistic funding goal (50 Crore) for the described scope. Urgent admin review needed."
            )
        ]
        db.add_all(campaigns)
        db.commit()

        # Add initial complaints for Heatmap
        complaints = [
            models.Complaint(
                citizen_name="Rahul Sharma",
                original_text="Heavy waterlogging on main road after rain. Potholes are very deep and dangerous.",
                department="Roads & Infrastructure",
                priority="High",
                sentiment="Negative",
                status="Pending",
                state="Madhya Pradesh",
                detected_issue="Potholes & Waterlogging"
            ),
            models.Complaint(
                citizen_name="Anita Desai",
                original_text="Stray dog injured in car accident, needs urgent medical attention near Bandra.",
                department="Animal Welfare",
                priority="Critical",
                sentiment="Negative",
                status="Pending",
                state="Maharashtra",
                detected_issue="Injured Animal"
            ),
            models.Complaint(
                citizen_name="Vikas Gupta",
                original_text="Garbage not collected for 10 days, bad smell and health risk in the colony.",
                department="Sanitation",
                priority="High",
                sentiment="Negative",
                status="In Progress",
                state="Delhi",
                detected_issue="Garbage Dumping"
            ),
            models.Complaint(
                citizen_name="Priya Singh",
                original_text="Street lights not working for a week, very unsafe for women walking at night.",
                department="Public Safety",
                priority="Urgent",
                sentiment="Negative",
                status="Pending",
                state="Uttar Pradesh",
                detected_issue="Broken Street Lights"
            ),
            models.Complaint(
                citizen_name="Amit Patel",
                original_text="Sewage line leakage, dirty water flooding the basement area.",
                department="Sanitation",
                priority="High",
                sentiment="Negative",
                status="Pending",
                state="Madhya Pradesh",
                detected_issue="Sewage Leakage"
            ),
            models.Complaint(
                citizen_name="Sanjay Rao",
                original_text="Fallen tree blocking the road and damaged power lines.",
                department="Roads & Infrastructure",
                priority="Critical",
                sentiment="Negative",
                status="Pending",
                state="Maharashtra",
                detected_issue="Road Blockage"
            )
        ]
        db.add_all(complaints)
        db.commit()

    db.close()


# ─── Sarvam AI Voice Helpline Webhook ───────────────────────────────────

@app.post("/api/voice-webhook")
async def handle_voice_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Sarvam AI calls this after every inbound call ends.
    Actual Sarvam webhook payload fields:
      - interaction_id  : unique call ID
      - transcript      : full conversation text (list of {role, content} or plain string)
      - duration        : call duration in seconds
      - caller_phone / from_number : caller's number
      - agent_variables : dict of variables collected during call
      - recording_url   : (if enabled)
    """
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        pass
    if not payload:
        payload = dict(request.query_params)

    print(f"[Voice Webhook] Raw payload from Sarvam AI: {payload}")

    # ── Extract caller phone ────────────────────────────────────────────
    caller_phone = (
        payload.get("caller_phone") or
        payload.get("from_number") or
        payload.get("from") or
        payload.get("phone") or
        payload.get("phone_number") or
        None
    )

    # ── Extract transcript (Sarvam sends list of {role,content} dicts) ──
    raw_transcript = payload.get("transcript") or payload.get("call_transcript") or payload.get("conversation")
    if isinstance(raw_transcript, list):
        # Convert list of {role, content} to readable string
        call_transcript = "\n".join(
            f"{turn.get('role','?').upper()}: {turn.get('content','')}"
            for turn in raw_transcript
        )
    else:
        call_transcript = raw_transcript or ""

    # ── Extract agent_variables (citizen may have spoken name/address) ──
    agent_vars = payload.get("agent_variables") or {}
    citizen_name = (
        agent_vars.get("citizen_name") or
        agent_vars.get("name") or
        payload.get("citizen_name") or
        f"Caller {caller_phone or 'Unknown'}"
    )
    address = (
        agent_vars.get("address") or
        agent_vars.get("location") or
        payload.get("address") or
        "Voice Helpline - Location not provided"
    )

    # ── Use transcript as the complaint text for AI analysis ─────────────
    original_text = call_transcript or payload.get("description") or "Voice Grievance Reported via Helpline"

    call_source = "sarvam_voice"
    dept = "Public Works Department"
    prio = "High"
    sentiment = "Negative"
    summary = original_text[:500] if original_text else "Voice complaint"
    detected_issue = "Voice Grievance"
    category = "General Civic Issue"

    # ── Run AI analysis on the transcript ──────────────────────────────
    try:
        analysis = ai_engine.analyze_complaint(original_text)
        if isinstance(analysis, dict):
            dept = analysis.get("department") or dept
            prio = analysis.get("priority") or prio
            sentiment = analysis.get("sentiment") or sentiment
            summary = analysis.get("summary") or summary
            detected_issue = analysis.get("detected_issue") or detected_issue
            category = analysis.get("category") or category
    except Exception as e:
        print(f"[Voice Webhook] AI fallback note: {e}")

    complaint = models.Complaint(
        citizen_name=f"{citizen_name} (📞 Voice Helpline)",
        original_text=original_text,
        translated_text=summary,
        department=dept,
        priority=prio,
        sentiment=sentiment,
        status="Pending",
        address=address,
        ai_summary=summary,
        detected_issue=detected_issue,
        category=category,
        visual_risk_level="Medium",
        confidence_score=95,
        caller_phone=caller_phone,
        call_transcript=call_transcript,
        call_source=call_source,
        created_at=datetime.datetime.now()
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    print(f"[Voice Webhook] ✅ Complaint ID={complaint.id} created | caller={caller_phone} | dept={dept} | prio={prio}")

    return {
        "success": True,
        "complaint_id": complaint.id,
        "message": f"Complaint #{complaint.id} registered for {citizen_name}",
        "department": dept,
        "priority": prio
    }


@app.post("/api/request-callback")
async def request_callback(data: dict = Body(...)):
    """
    Triggers an outbound call from the Sarvam AI Voice Agent to the user's phone.
    Requires SARVAM_ORG_ID, SARVAM_WORKSPACE_ID, SARVAM_APP_ID, SARVAM_API_KEY in .env.
    """
    phone = str(data.get("phone_number", "")).strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")

    # Format to international format (+91...) if user enters 10 digits
    clean_digits = "".join(ch for ch in phone if ch.isdigit())
    if len(clean_digits) == 10:
        formatted_phone = f"+91{clean_digits}"
    elif phone.startswith("+"):
        formatted_phone = phone
    else:
        formatted_phone = f"+{clean_digits}"

    org_id = os.getenv("SARVAM_ORG_ID", "").strip()
    workspace_id = os.getenv("SARVAM_WORKSPACE_ID", "").strip()
    app_id = os.getenv("SARVAM_APP_ID", "").strip()
    api_key = os.getenv("SARVAM_API_KEY", "").strip()

    if not (org_id and workspace_id and app_id and api_key):
        return {
            "success": False,
            "error": "SARVAM_CONFIG_MISSING",
            "message": "Sarvam configuration (Org ID, Workspace ID, or App ID) is missing in backend .env."
        }

    url = f"https://apps.sarvam.ai/api/outbounds/v1/orgs/{org_id}/workspaces/{workspace_id}/outbounds"
    payload = {
        "app_config": {"app_id": app_id},
        "user_config": {"phone_number": formatted_phone},
        "webhook_config": {
            "url": "https://ai-grievance-backend-fro0.onrender.com/api/voice-webhook"
        }
    }
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json"
    }

    print(f"[Request Callback] Triggering outbound call to {formatted_phone} via Sarvam...")
    try:
        import requests
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        print(f"[Request Callback] Sarvam response status={resp.status_code}, body={resp.text}")
        if resp.status_code in [200, 201]:
            return {
                "success": True,
                "message": f"AI voice agent is calling {formatted_phone}! Please answer to report your grievance.",
                "sarvam_data": resp.json() if resp.text else {}
            }
        else:
            return {
                "success": False,
                "status_code": resp.status_code,
                "error": resp.text,
                "message": f"Sarvam API error: {resp.text}"
            }
    except Exception as e:
        print(f"[Request Callback] Connection error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to connect to Sarvam outbound service."
        }


@app.post("/api/admin/sync-complaints")
def sync_complaints(complaints: List[dict] = Body(...), db: Session = Depends(get_db)):
    """Bulk-sync complaints from local database to cloud database."""
    added = 0
    for c_data in complaints:
        orig = c_data.get("original_text")
        exists = db.query(models.Complaint).filter(models.Complaint.original_text == orig).first() if orig else None
        if not exists:
            created_str = c_data.get("created_at")
            try:
                created_dt = datetime.datetime.fromisoformat(created_str) if created_str else datetime.datetime.now()
            except Exception:
                created_dt = datetime.datetime.now()

            comp = models.Complaint(
                citizen_name=c_data.get("citizen_name"),
                title=c_data.get("title"),
                original_text=c_data.get("original_text") or "",
                translated_text=c_data.get("translated_text"),
                department=c_data.get("department") or "Other",
                priority=c_data.get("priority") or "Medium",
                sentiment=c_data.get("sentiment") or "Neutral",
                status=c_data.get("status") or "Pending",
                latitude=c_data.get("latitude"),
                longitude=c_data.get("longitude"),
                address=c_data.get("address"),
                pincode=c_data.get("pincode"),
                image_url=c_data.get("image_url"),
                ai_summary=c_data.get("ai_summary"),
                detected_issue=c_data.get("detected_issue"),
                category=c_data.get("category"),
                visual_risk_level=c_data.get("visual_risk_level") or "Medium",
                confidence_score=c_data.get("confidence_score") or 95,
                caller_phone=c_data.get("caller_phone"),
                call_transcript=c_data.get("call_transcript"),
                call_source=c_data.get("call_source"),
                created_at=created_dt
            )
            db.add(comp)
            added += 1
    db.commit()
    return {"success": True, "added": added}

