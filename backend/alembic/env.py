"""Alembic environment configuration.

The database URL is built from DB_HOST / DB_NAME / DB_CONNECTOR plus credentials
resolved by oqtopus_cloud.common.session.get_secret() -- the SAME resolver the
application uses, honouring DB_CREDENTIAL_SOURCE (file | local | aws). On-prem
migrations therefore run with DB_SECRET_FILE only (no DB_USERNAME/DB_PASSWORD in
the environment), exactly like the API containers. A manual migration can still
opt into env credentials with DB_CREDENTIAL_SOURCE=local, or bypass resolution
entirely with ALEMBIC_DATABASE_URL (used for the SQLite initial-revision case).

target_metadata aggregates every model class imported via
oqtopus_cloud.common.models, so the package's __init__.py must import all
models that should participate in autogenerate.

Empty autogenerate revisions are suppressed via process_revision_directives;
running `alembic revision --autogenerate` when there are no model changes
prints "No changes detected" and creates no file.

TLS comes from oqtopus_cloud.common.db_tls, the same helper session.py uses, so
migrations reach the RDS Proxy exactly like the application does.
"""

import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import URL, make_url

# Importing the package registers every model class with Base.metadata.
import oqtopus_cloud.common.models  # noqa: F401
from oqtopus_cloud.common.db_tls import ssl_connect_args
from oqtopus_cloud.common.model_util import DateTimeTz
from oqtopus_cloud.common.models import Base
from oqtopus_cloud.common.session import build_db_url, validate_db_runtime_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# alembic.ini configures the "alembic" logger at INFO, so this is shown by default.
logger = logging.getLogger("alembic.env")


def _build_url() -> URL:
    # Allow callers to override the URL directly (useful for generating the
    # initial revision against an empty SQLite database, etc.). This explicit
    # path is the only one exempt from the DB-contract validation below.
    override = os.environ.get("ALEMBIC_DATABASE_URL")
    if override:
        return make_url(override)
    # Normal path: enforce the SAME DB contract the application does at startup
    # (DB_HOST/DB_NAME/DB_CONNECTOR present + allowed connector + the configured
    # credential source), and build the URL with the SAME shared helper -- so
    # migrations and the app resolve credentials and escape them identically.
    validate_db_runtime_config()
    return build_db_url()


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
    url = _build_url()
    parsed = make_url(url)
    # `ssl` is a PyMySQL connect argument, so it is only applied to MySQL URLs.
    # ALEMBIC_DATABASE_URL is also used to point at a throwaway SQLite database
    # (see _build_url), whose driver would reject it.
    #
    # Passed as connect_args rather than URL query parameters so that these win
    # over any ssl_* already present in an ALEMBIC_DATABASE_URL override.
    connect_args = (
        ssl_connect_args(parsed.host) if parsed.get_backend_name() == "mysql" else {}
    )
    # Logged because a migration is often the only thing an operator runs
    # against a production database: "which database, over TLS or not" should
    # never have to be inferred from a stack trace.
    logger.info(
        "connecting to %s (TLS: %s)",
        parsed.render_as_string(hide_password=True),
        "on" if "ssl" in connect_args else "off",
    )
    engine = create_engine(url, poolclass=pool.NullPool, connect_args=connect_args)
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
