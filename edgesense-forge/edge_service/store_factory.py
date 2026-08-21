from pathlib import Path

from .storage import EventStore


def create_store(database_url: str | None, database_path: Path):
    if database_url and database_url.startswith(("postgresql://", "postgres://")):
        from .storage_postgres import PostgresEventStore
        return PostgresEventStore(database_url)
    return EventStore(database_path)
