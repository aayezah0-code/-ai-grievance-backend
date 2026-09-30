import os
import re
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# STRICT PROJECT RULE: Supabase Cloud PostgreSQL is the exclusive database
DEFAULT_SUPABASE_URL = "postgresql://postgres.syxyymkbmhgbpoaefbtk:8oKlfNA6MirWjafC@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

def sanitize_url(raw: str) -> str:
    if not raw:
        return DEFAULT_SUPABASE_URL
    u = raw.strip().strip("'\"`")
    if "=" in u and "postgres" in u:
        u = u.split("=", 1)[1].strip().strip("'\"`")
    m = re.search(r'(postgres(?:ql)?://[^\s\'"`]+)', u)
    if m:
        u = m.group(1)
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://"):]
    return u or DEFAULT_SUPABASE_URL

env_url = os.getenv("DATABASE_URL")
SQLALCHEMY_DATABASE_URL = sanitize_url(env_url)

# Select available PostgreSQL driver (psycopg v3 or psycopg2)
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
    print(f"[Database Error]: Connection issue with {SQLALCHEMY_DATABASE_URL}: {e}. Connecting to Supabase pooler default.")
    fallback_url = "postgresql+psycopg://" + DEFAULT_SUPABASE_URL[len("postgresql://"):]
    engine = create_engine(
        fallback_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
