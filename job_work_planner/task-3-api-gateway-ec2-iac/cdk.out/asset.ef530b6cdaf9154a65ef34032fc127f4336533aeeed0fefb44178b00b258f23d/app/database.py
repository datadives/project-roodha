import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")

LOCAL_DEVELOPMENT_DATABASE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/roodhamaster"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL and os.getenv("ENV", "").lower() == "development":
    SQLALCHEMY_DATABASE_URL = LOCAL_DEVELOPMENT_DATABASE_URL

if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Configure it in task-4-backend-skeleton/.env or your environment before starting the backend."
    )

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
