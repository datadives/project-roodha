
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_db():
    conn = psycopg2.connect(dbname="postgres", user="postgres", host="127.0.0.1")
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'roodhamaster'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE roodhamaster")
    cur.close()
    conn.close()

if __name__ == "__main__":
    create_db()
