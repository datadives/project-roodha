import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# 1. Load and format the URL
load_dotenv()
db_url = os.getenv('DATABASE_URL')
if '+asyncpg' in db_url:
    db_url = db_url.replace('+asyncpg', '')

print("Connecting to AWS RDS...")
engine = create_engine(db_url)

# 2. Import your single models file
import app.models

# 3. Find the database metadata inside your models file
db_metadata = None
for name, obj in vars(app.models).items():
    if hasattr(obj, 'metadata') and hasattr(obj.metadata, 'create_all'):
        db_metadata = obj.metadata
        break

# 4. Build the tables
if db_metadata:
    db_metadata.create_all(bind=engine)
    print('✅ All Tables Created Successfully in AWS!')
else:
    print('❌ Could not find database structure in models.')