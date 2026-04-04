from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- YOUR ACTUAL AWS RDS CREDENTIALS ---
DB_PASSWORD = "Jk48iW^G3qNFsrEi.0NzfNC1_c3=k."
DB_ENDPOINT = "rdsmasterstack-masterdbinstancefa9667f0-zgqvy2ytchrm.cjas4ee48mso.ap-south-1.rds.amazonaws.com"

# These stay the same:
DB_USERNAME = "postgres"
DB_PORT = "5432"
DB_NAME = "roodhamaster"

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_ENDPOINT}:{DB_PORT}/{DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()