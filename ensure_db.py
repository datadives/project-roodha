import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_NAME = "roodha_local"
DEFAULT_DB = "postgres"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_HOST = "127.0.0.1"

def ensure_db():
    try:
        # 1. Connect to default db to check/create the target db
        print(f"Connecting to default database '{DEFAULT_DB}' at {DB_HOST}...")
        conn = psycopg2.connect(dbname=DEFAULT_DB, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
        exists = cur.fetchone()

        if not exists:
            print(f"Database '{DB_NAME}' does not exist. Creating...")
            cur.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"Database '{DB_NAME}' created.")
        else:
            print(f"Database '{DB_NAME}' already exists.")

        cur.close()
        conn.close()

        # 2. Connect to the new database to provision tables and seed data
        print(f"Connecting to '{DB_NAME}' to provision schema...")
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS machines (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT 'Active'
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                machine_id INTEGER REFERENCES machines(id),
                status VARCHAR(50) DEFAULT 'Pending'
            );
        """)
        print("Tables validated/created.")

        # 3. Seed "Safety Orange" test data
        cur.execute("SELECT COUNT(*) FROM machines WHERE name = 'Safety Orange Machine'")
        if cur.fetchone()[0] == 0:
            print("Seeding 'Safety Orange' test data...")
            cur.execute("INSERT INTO machines (name, status) VALUES (%s, %s) RETURNING id", 
                        ("Safety Orange Machine", "Active"))
            machine_id = cur.fetchone()[0]
            
            cur.execute("INSERT INTO jobs (title, machine_id, status) VALUES (%s, %s, %s)",
                        ("Safety Orange Priority Job", machine_id, "Pending"))
            
            conn.commit()
            print("Test data seeded successfully.")
        else:
            print("Test data already exists. Skipping seed.")

        cur.close()
        conn.close()
        print("Database provisioning complete.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    ensure_db()
