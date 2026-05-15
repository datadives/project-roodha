import os
from pathlib import Path

import pytest
from sqlalchemy import text

from app.database import async_engine


def _load_dotenv_value(dotenv_path: Path, key: str) -> str | None:
    if not dotenv_path.exists():
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
      line = raw_line.strip()
      if not line or line.startswith("#") or "=" not in line:
          continue
      current_key, value = line.split("=", 1)
      if current_key.strip() == key:
          return value.strip().strip('"').strip("'")
    return None


@pytest.mark.asyncio
async def test_db_connection_select_1():
    dotenv_path = Path(__file__).resolve().parents[1] / ".env"
    database_url = os.getenv("DATABASE_URL") or _load_dotenv_value(dotenv_path, "DATABASE_URL")
    assert database_url, "DATABASE_URL must be set in the environment or .env file before running this test"

    try:
        async with async_engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
    except TimeoutError as exc:
        pytest.skip(f"Database host is not reachable from this local network: {database_url}: {exc}")
    except Exception as exc:
        if "password authentication failed" in str(exc).lower():
            pytest.fail(f"Database credentials were rejected for {database_url}: {exc}")
        pytest.fail(f"Database connectivity check failed for {database_url}: {exc}")
