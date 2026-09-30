import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DEFAULT_SUPABASE_URL = "postgresql://postgres.syxyymkbmhgbpoaefbtk:8oKlfNA6MirWjafC@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_SUPABASE_URL)

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Normalize legacy postgres:// prefix
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # Check for psycopg (v3) or psycopg2 driver availability
    try:
        import psycopg
        if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
            SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    except ImportError:
        try:
            import psycopg2
            if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
                SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
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
