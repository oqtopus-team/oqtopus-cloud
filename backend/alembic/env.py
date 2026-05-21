"""Alembic environment configuration.

The database URL is built from environment variables (DB_HOST, DB_NAME,
DB_CONNECTOR, DB_USERNAME, DB_PASSWORD). When ENV=local, the username/password
default to admin/password to match the local MySQL Docker setup in
backend/oqtopus_cloud/common/session.py.

target_metadata aggregates every model class imported via
oqtopus_cloud.common.models, so the package's __init__.py must import all
models that should participate in autogenerate.

Empty autogenerate revisions are suppressed via process_revision_directives;
running `alembic revision --autogenerate` when there are no model changes
prints "No changes detected" and creates no file.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Importing the package registers every model class with Base.metadata.
import oqtopus_cloud.common.models  # noqa: F401
from oqtopus_cloud.common.model_util import DateTimeTz
from oqtopus_cloud.common.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _build_url() -> str:
    # Allow callers to override the URL directly (useful for generating the
    # initial revision against an empty SQLite database, etc.).
    override = os.environ.get("ALEMBIC_DATABASE_URL")
    if override:
        return override
    connector = os.environ.get("DB_CONNECTOR", "mysql+pymysql")
    host = os.environ["DB_HOST"]
    db_name = os.environ["DB_NAME"]
    if os.environ.get("ENV") == "local":
        user = os.environ.get("DB_USERNAME", "admin")
        password = os.environ.get("DB_PASSWORD", "password")
    else:
        user = os.environ["DB_USERNAME"]
        password = os.environ["DB_PASSWORD"]
    return f"{connector}://{user}:{password}@{host}/{db_name}"


def process_revision_directives(context, revision, directives):
    """Skip generating a revision file when models match the database."""
    if getattr(config.cmd_opts, "autogenerate", False):
        script = directives[0]
        if script.upgrade_ops.is_empty():
            directives[:] = []
            print("No changes detected — skipping revision file")


def render_item(type_, obj, autogen_context):
    """Render the custom DateTimeTz column type with a clean import."""
    if type_ == "type" and isinstance(obj, DateTimeTz):
        autogen_context.imports.add(
            "from oqtopus_cloud.common.model_util import DateTimeTz"
        )
        return "DateTimeTz()"
    return False  # fall back to default rendering


def run_migrations_offline() -> None:
    context.configure(
        url=_build_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # NOTE: compare_type is False because some model columns use String
        # without an explicit length, which crashes MySQL's VARCHAR compiler
        # during type comparison. Adds/drops are still detected.
        compare_type=False,
        render_item=render_item,
        process_revision_directives=process_revision_directives,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_build_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
            render_item=render_item,
            process_revision_directives=process_revision_directives,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
