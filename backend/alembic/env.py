from logging.config import fileConfig
from os import environ

import sqlalchemy as sa
from alembic import context
from alembic.autogenerate import renderers
from oqtopus_cloud.common.models import Base
from sqlalchemy import Enum, TypeDecorator, engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

enum_field_max_length = 64


def render_item(type_, obj, autogen_context):
    if type_ == "type":
        if isinstance(obj, sa.Enum):
            # Check for enum's members having name of acceptable length.
            # (...or, There might be more preferable ways than raising exception?)
            for member in obj.enums:
                if len(member) >= enum_field_max_length:
                    raise ValueError(f"Enum field `{member}` is too long.")
            return f"sa.String(length={enum_field_max_length})"

        if isinstance(obj, TypeDecorator):
            return f"sa.{obj.impl!r}"
    return False


def set_env_var(key: str):
    val = environ.get(key)
    if val is not None:
        config.set_section_option("alembic", key, val)
    else:
        raise KeyError(f'Environment variable "{key}" is not set')


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    set_env_var("DB_HOST")
    set_env_var("DB_USER")
    set_env_var("DB_PASS")
    set_env_var("DB_NAME")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
