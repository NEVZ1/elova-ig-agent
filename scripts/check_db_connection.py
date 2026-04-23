from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.session import async_engine


def describe_url(name: str, url: str | None) -> None:
    if not url:
        print(f"{name}: <missing>")
        return
    parsed = urlparse(url)
    print(f"{name}:")
    print(f"  scheme={parsed.scheme}")
    print(f"  host={parsed.hostname}")
    print(f"  port={parsed.port}")
    print(f"  database={(parsed.path or '').lstrip('/')}")
    print(f"  user_present={bool(parsed.username)}")
    print(f"  password_present={bool(parsed.password)}")
    print(f"  query_keys={sorted(parse_qs(parsed.query).keys())}")
    print(f"  direct_supabase_host={bool(parsed.hostname and parsed.hostname.startswith('db.') and parsed.hostname.endswith('.supabase.co'))}")
    print(f"  pooler_supabase_host={bool(parsed.hostname and '.pooler.supabase.com' in parsed.hostname)}")


async def main() -> None:
    describe_url("database_url", settings.database_url)
    describe_url("database_url_sync", settings.database_url_sync)
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            print(f"DB_OK={result.scalar()}")
    except Exception as exc:  # noqa: BLE001
        print(f"DB_ERROR_TYPE={type(exc).__name__}")
        print(f"DB_ERROR={str(exc)[:1000]}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    asyncio.run(main())
