import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


def test_policy_link_migration_preserves_existing_rows_and_is_repeatable():
    spec = importlib.util.spec_from_file_location("policy_link_migration",
        Path(__file__).resolve().parents[1] / "migrations/versions/0003_policy_application_link.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE applications (id INTEGER PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE policies (id INTEGER PRIMARY KEY, policy_number VARCHAR(80))"))
        connection.execute(sa.text("INSERT INTO policies VALUES (1, 'Existing policy')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        row = connection.execute(sa.text("SELECT policy_number, application_id FROM policies WHERE id=1")).one()
        assert row == ("Existing policy", None)
        inspector = sa.inspect(connection)
        assert any(fk["constrained_columns"] == ["application_id"] for fk in inspector.get_foreign_keys("policies"))
        assert any(index["name"] == "ix_policies_application_id" for index in inspector.get_indexes("policies"))
