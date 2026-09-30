import os, sys, datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models

SQLITE_PATH = "sqlite:///./complaints.db"
SUPABASE_URL = "postgresql://postgres.syxyymkbmhgbpoaefbtk:8oKlfNA6MirWjafC@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

sqlite_engine = create_engine(SQLITE_PATH, connect_args={"check_same_thread": False})
supabase_engine = create_engine(SUPABASE_URL)

SqliteSession = sessionmaker(bind=sqlite_engine)
SupabaseSession = sessionmaker(bind=supabase_engine)

sqlite_db = SqliteSession()
supabase_db = SupabaseSession()

try:
    print("--- 1. Migrating Users ---")
    users = sqlite_db.query(models.User).order_by(models.User.id.asc()).all()
    print(f"Found {len(users)} users in SQLite.")
    for u in users:
        existing = supabase_db.query(models.User).filter(models.User.email == u.email).first()
        if not existing:
            new_u = models.User(
                id=u.id,
                full_name=u.full_name,
                mobile_no=u.mobile_no,
                email=u.email,
                address=u.address,
                city=u.city,
                state=u.state,
                pincode=u.pincode,
                hashed_password=u.hashed_password,
                role=u.role,
                is_verified=u.is_verified,
                verification_code=u.verification_code,
                verification_code_expires_at=u.verification_code_expires_at
            )
            supabase_db.add(new_u)
    supabase_db.commit()
    print("Users migrated!")

    # Fix users sequence in PostgreSQL
    with supabase_engine.connect() as conn:
        conn.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1) + 1, false) FROM users;"))
        conn.commit()

    print("\n--- 2. Migrating Schemes ---")
    schemes = sqlite_db.query(models.Scheme).order_by(models.Scheme.id.asc()).all()
    print(f"Found {len(schemes)} schemes in SQLite.")
    for s in schemes:
        existing = supabase_db.query(models.Scheme).filter(models.Scheme.name == s.name).first()
        if not existing:
            new_s = models.Scheme(
                id=s.id,
                name=s.name,
                description=s.description,
                category=s.category,
                type=s.type,
                state=s.state,
                benefits=s.benefits,
                eligibility_summary=s.eligibility_summary,
                launch_year=s.launch_year,
                website_url=s.website_url,
                application_steps=s.application_steps
            )
            supabase_db.add(new_s)
    supabase_db.commit()
    print("Schemes migrated!")

    with supabase_engine.connect() as conn:
        conn.execute(text("SELECT setval(pg_get_serial_sequence('schemes', 'id'), COALESCE(MAX(id), 1) + 1, false) FROM schemes;"))
        conn.commit()

    print("\n--- 3. Migrating Complaints ---")
    complaints = sqlite_db.query(models.Complaint).order_by(models.Complaint.id.asc()).all()
    print(f"Found {len(complaints)} complaints in SQLite.")
    for c in complaints:
        existing = supabase_db.query(models.Complaint).filter(models.Complaint.id == c.id).first()
        if not existing:
            new_c = models.Complaint(
                id=c.id,
                user_id=c.user_id,
                citizen_name=c.citizen_name,
                title=c.title,
                original_text=c.original_text,
                translated_text=c.translated_text,
                department=c.department,
                priority=c.priority,
                sentiment=c.sentiment,
                status=c.status,
                latitude=c.latitude,
                longitude=c.longitude,
                address=c.address,
                pincode=c.pincode,
                image_url=c.image_url,
                estimated_resolution_time=c.estimated_resolution_time,
                ai_summary=c.ai_summary,
                detected_issue=c.detected_issue,
                category=c.category,
                visual_risk_level=c.visual_risk_level,
                issue_tags=c.issue_tags,
                confidence_score=c.confidence_score,
                image_observation=c.image_observation,
                official_remarks=c.official_remarks,
                state=c.state,
                caller_phone=c.caller_phone,
                call_transcript=c.call_transcript,
                call_source=c.call_source,
                recording_url=c.recording_url,
                interaction_id=c.interaction_id,
                created_at=c.created_at
            )
            supabase_db.add(new_c)
    supabase_db.commit()
    print("Complaints migrated!")

    with supabase_engine.connect() as conn:
        conn.execute(text("SELECT setval(pg_get_serial_sequence('complaints', 'id'), COALESCE(MAX(id), 1) + 1, false) FROM complaints;"))
        conn.commit()

    print("\n--- 4. Migrating Donation Campaigns ---")
    campaigns = sqlite_db.query(models.DonationCampaign).order_by(models.DonationCampaign.id.asc()).all()
    print(f"Found {len(campaigns)} campaigns in SQLite.")
    for d in campaigns:
        existing = supabase_db.query(models.DonationCampaign).filter(models.DonationCampaign.title == d.title).first()
        if not existing:
            new_d = models.DonationCampaign(
                id=d.id,
                title=d.title,
                description=d.description,
                category=d.category,
                location=d.location,
                ngo_name=d.ngo_name,
                urgency_level=d.urgency_level,
                amount_raised=d.amount_raised,
                target_amount=d.target_amount,
                contributor_count=d.contributor_count,
                impact_metrics=d.impact_metrics,
                verification_type=d.verification_type,
                related_complaint_category=d.related_complaint_category,
                expiry_date=d.expiry_date,
                moderation_status=d.moderation_status,
                risk_score=d.risk_score,
                ai_fraud_reason=d.ai_fraud_reason
            )
            supabase_db.add(new_d)
    supabase_db.commit()
    print("Donation campaigns migrated!")

    print("\n--- 5. Migrating Notifications ---")
    notifs = sqlite_db.query(models.Notification).order_by(models.Notification.id.asc()).all()
    print(f"Found {len(notifs)} notifications in SQLite.")
    for n in notifs:
        existing = supabase_db.query(models.Notification).filter(models.Notification.title == n.title).first()
        if not existing:
            new_n = models.Notification(
                id=n.id,
                title=n.title,
                content=n.content,
                category=n.category,
                priority=n.priority,
                state=n.state,
                linked_scheme_id=n.linked_scheme_id
            )
            supabase_db.add(new_n)
    supabase_db.commit()
    print("Notifications migrated!")

    print("\n==========================================")
    print("ALL DATA MIGRATION TO SUPABASE COMPLETED!")
    print(f"Users in Supabase: {supabase_db.query(models.User).count()}")
    print(f"Complaints in Supabase: {supabase_db.query(models.Complaint).count()}")
    print(f"Schemes in Supabase: {supabase_db.query(models.Scheme).count()}")
    print("==========================================")

except Exception as e:
    print(f"Migration error: {e}")
    supabase_db.rollback()
finally:
    sqlite_db.close()
    supabase_db.close()
