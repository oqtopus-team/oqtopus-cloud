"""Baseline a database that predates Alembic, without running any DDL.

Databases created before Alembic was introduced (by the old
`operation/db/init.sql`) already carry the schema that the first revision would
have built, but they have no `alembic_version` row. They have to be told which
revision they correspond to before `alembic upgrade head` can apply the rest.

That revision is the **root of the revision chain**, not `head`. Stamping `head`
marks every revision after the baseline as applied while its DDL never runs, so
the schema silently lags behind what Alembic believes is deployed.

Run via `make migrate-stamp-baseline` (local) or `make migrate-stamp` in
`operation/<env>/` (remote, through a port-forward). Connection settings come
from `alembic/env.py`, so `ALEMBIC_DATABASE_URL` and TLS behave exactly as they
do for every other Alembic command.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import TextIO

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

# alembic.ini lives in the backend root, next to the alembic/ directory.
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _config(stdout: TextIO | None = None) -> Config:
    """Return an Alembic config, optionally capturing command output."""
    if stdout is None:
        return Config(str(ALEMBIC_INI))
    return Config(str(ALEMBIC_INI), stdout=stdout)


def baseline_revision(config: Config) -> str:
    """Return the root revision of the migration chain.

    Resolved from the chain rather than hardcoded so that it cannot go stale as
    revisions are added. Raises if the chain has no single root, which would
    mean the baseline is ambiguous and has to be chosen by hand.
    """
    # get_base() is typed Optional because a project may have no revisions at
    # all; here an empty chain means a broken checkout, so fail loudly.
    base = ScriptDirectory.from_config(config).get_base()
    if base is None:
        raise RuntimeError("the migration chain has no revisions")
    return base


def current_revision() -> str:
    """Return the revision the database is stamped at, or "" when untracked."""
    buffer = io.StringIO()
    command.current(_config(stdout=buffer))
    return buffer.getvalue().strip()


def main(argv: list[str] | None = None) -> int:
    config = _config()

    revision = baseline_revision(config)
    if not revision:
        print(
            "Could not resolve the baseline revision from the migration chain.",
            file=sys.stderr,
        )
        return 1

    current = current_revision()
    if current:
        print(
            f"Refusing to stamp: the database is already at revision {current!r}.\n"
            "This command is only for a database Alembic has never tracked.\n"
            "Re-stamping would rewind the recorded state and make the next\n"
            "`alembic upgrade head` re-run DDL that has already been applied.",
            file=sys.stderr,
        )
        return 1

    print(f"Baselining the database at {revision} (no DDL will run)")
    command.stamp(config, revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
