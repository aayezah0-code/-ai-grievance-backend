from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from database import Base
import datetime

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    citizen_name = Column(String, default="Anonymous")
    user_id = Column(Integer, nullable=True, index=True)
    title = Column(String, nullable=True)
    original_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=True)
    department = Column(String, index=True)
    priority = Column(String, index=True)
    sentiment = Column(String)
    status = Column(String, default="Pending")
    estimated_resolution_time = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    address = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    ai_summary = Column(Text, nullable=True)
    detected_issue = Column(String, nullable=True)
    category = Column(String, nullable=True)
    visual_risk_level = Column(String, nullable=True)
    issue_tags = Column(String, nullable=True)
    confidence_score = Column(Integer, nullable=True) # 0-100
    image_observation = Column(Text, nullable=True)
    official_remarks = Column(Text, nullable=True)
    state = Column(String, nullable=True, index=True)
    caller_phone = Column(String, nullable=True)         # Phone number from voice call
    call_transcript = Column(Text, nullable=True)         # Full call transcript from Sarvam AI
    call_source = Column(String, nullable=True)           # e.g. 'sarvam_voice', 'web', 'app'
    recording_url = Column(String, nullable=True)         # Audio recording URL from Sarvam
    created_at = Column(DateTime, default=datetime.datetime.now)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    mobile_no = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    address = Column(String, nullable=False)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    pincode = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    profile_image_url = Column(String, nullable=True)
    role = Column(String, default="citizen", nullable=True)
    # Email verification fields (added for registration verification flow)
    is_verified = Column(Boolean, default=True, server_default='1', nullable=False)
    verification_code = Column(String, nullable=True)
    verification_code_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

class AnimalReport(Base):
    __tablename__ = "animal_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    media_url = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    
    # AI Assessment Fields
    detected_animal = Column(String, nullable=True)
    animal_condition = Column(String, nullable=True)
    possible_injury = Column(Text, nullable=True) # JSON string of injuries
    urgency_level = Column(String, nullable=True)
    rescue_priority = Column(String, nullable=True)
    health_risks = Column(Text, nullable=True) # JSON string of risks
    recommended_action = Column(Text, nullable=True)
    nearest_ngo = Column(String, nullable=True) # Maps to nearest_rescue_type
    eta = Column(String, nullable=True) # Maps to estimated_rescue_eta
    ai_summary = Column(Text, nullable=True)
    confidence_score = Column(String, nullable=True)

    status = Column(String, default="Report Submitted")
    created_at = Column(DateTime, default=datetime.datetime.now)

class Scheme(Base):
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, index=True)
    type = Column(String, index=True) # Central or State
    state = Column(String, index=True, nullable=True) # Specific state if type is State
    eligibility_summary = Column(Text, nullable=True)
    benefits = Column(Text, nullable=True)
    launch_year = Column(Integer, nullable=True)
    website_url = Column(String, nullable=True)
    application_steps = Column(Text, nullable=True) # Store as JSON string or markdown
    icon_type = Column(String, default="default")
    created_at = Column(DateTime, default=datetime.datetime.now)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String, nullable=True) # e.g. "Scheme", "Grievance"
    state = Column(String, nullable=True) # State specific notification
    priority = Column(String, default="Normal") # Normal, Urgent, High
    linked_scheme_id = Column(Integer, nullable=True) # ID of the related scheme
    link = Column(String, nullable=True)
    is_read = Column(Integer, default=0) # 0 for false, 1 for true
    created_at = Column(DateTime, default=datetime.datetime.now)

class DonationCampaign(Base):
    __tablename__ = "donation_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String, index=True)
    location = Column(String, index=True) # State or City
    ngo_name = Column(String, nullable=False)
    is_verified = Column(Integer, default=1) # 1 for True, 0 for False
    verification_type = Column(String, default="NGO Verified")
    urgency_level = Column(String, default="Community Support") # Critical, Urgent, Community Support
    amount_raised = Column(Integer, default=0)
    target_amount = Column(Integer, nullable=False)
    contributor_count = Column(Integer, default=0)
    impact_metrics = Column(String, nullable=True) # e.g. "500 Lives Saved"
    image_url = Column(String, nullable=True)
    expiry_date = Column(DateTime, nullable=True)
    related_complaint_category = Column(String, nullable=True) # e.g. "Sanitation", "Animal Welfare"
    moderation_status = Column(String, default="Approved") # Approved, Under Review, Rejected
    risk_score = Column(String, default="Low Risk") # Low Risk, Medium Risk, High Risk
    ai_fraud_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.now)

class SocialHelpCase(Base):
    __tablename__ = "social_help_cases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    media_url = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    detected_category = Column(String, nullable=True)
    priority_level = Column(String, nullable=True)
    behavior_analysis = Column(String, nullable=True)
    sentiment_score = Column(String, nullable=True)
    status = Column(String, default="Pending Assessment")
    created_at = Column(DateTime, default=datetime.datetime.now)

