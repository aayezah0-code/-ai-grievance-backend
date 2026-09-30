import os
import re
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DEFAULT_SUPABASE_URL = "postgresql://postgres.syxyymkbmhgbpoaefbtk:8oKlfNA6MirWjafC@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

def sanitize_url(raw: str) -> str:
    if not raw:
        return DEFAULT_SUPABASE_URL
    u = raw.strip().strip("'\"`")
    # In case user pasted 'DATABASE_URL=postgresql://...' in the value box
    if "=" in u and ("postgres" in u or "sqlite" in u):
        u = u.split("=", 1)[1].strip().strip("'\"`")
    # Extract clean postgres URL via regex
    m = re.search(r'(postgres(?:ql)?://[^\s\'"`]+)', u)
    if m:
        u = m.group(1)
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    return u or DEFAULT_SUPABASE_URL

env_url = os.getenv("DATABASE_URL")
SQLALCHEMY_DATABASE_URL = sanitize_url(env_url)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Select available driver (psycopg v3 or psycopg2)
    try:
        import psycopg
        if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
            SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://" + SQLALCHEMY_DATABASE_URL[len("postgresql://"):]
    except ImportError:
        try:
            import psycopg2
            if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
                SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://" + SQLALCHEMY_DATABASE_URL[len("postgresql://"):]
        except ImportError:
            pass

    try:
        engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
    except Exception as e:
        print(f"[Database Error]: Failed with URL {SQLALCHEMY_DATABASE_URL}: {e}. Falling back to default Supabase URL.")
        fallback_url = "postgresql+psycopg://" + DEFAULT_SUPABASE_URL[len("postgresql://"):]
        engine = create_engine(
            fallback_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
