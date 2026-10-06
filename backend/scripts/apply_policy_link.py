"""Apply the additive policy link to an existing database without resetting data."""
import argparse
import importlib.util
import os
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    args = parser.parse_args()
    load_dotenv(args.env_file)
    url = make_url((os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or "").replace(
        "postgres://", "postgresql://", 1)).set(drivername="postgresql+psycopg")
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    migration_path = Path(__file__).resolve().parents[1] / "migrations/versions/0003_policy_application_link.py"
    spec = importlib.util.spec_from_file_location("policy_link_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    print("Applying the additive policy/application link migration.", flush=True)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
    engine.dispose()
    print("Policy/application column, foreign key and index are ready.", flush=True)
