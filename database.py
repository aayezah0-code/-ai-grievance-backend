import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DEFAULT_SUPABASE_URL = "postgresql://postgres.syxyymkbmhgbpoaefbtk:8oKlfNA6MirWjafC@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

raw_url = os.getenv("DATABASE_URL") or DEFAULT_SUPABASE_URL
SQLALCHEMY_DATABASE_URL = raw_url.strip().strip("'").strip('"')

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Normalize legacy postgres:// prefix
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = "postgresql://" + SQLALCHEMY_DATABASE_URL[len("postgres://"):]

    # Check for psycopg (v3) or psycopg2 driver availability
    if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
        try:
            import psycopg
            SQLALCHEMY_DATABASE_URL = "postgresql+psycopg://" + SQLALCHEMY_DATABASE_URL[len("postgresql://"):]
        except ImportError:
            try:
                import psycopg2
                SQLALCHEMY_DATABASE_URL = "postgresql+psycopg2://" + SQLALCHEMY_DATABASE_URL[len("postgresql://"):]
            except ImportError:
                pass

    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
