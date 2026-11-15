"""Load a secret from a file, refusing unsafe files (TOCTOU-safe).

This is the single file-secret contract shared by the API containers
(``session.py`` -> DB credentials) and the on-prem ops CLI (LDAP bind password,
Keycloak service-account credential). Keeping one loader is deliberate: the
production DB credentials and the ops credentials must be injected the *same*
way, so a file that is safe for one is safe for the other.

Secrets are read from files, never from CLI arguments, environment variables, or
logs. The file is opened with ``O_NOFOLLOW`` (so a symlink is refused at open
time) and then the *open descriptor* is ``fstat``-ed -- checking the path and
then opening it would be a TOCTOU race. A file is accepted only if it is a
regular file, owned by the current user (or root), and not readable by group or
others (``mode & 0o077 == 0``; ``0600`` or ``0400``).
"""

from __future__ import annotations

import errno
import json
import os
import stat
from typing import Any


class InsecureSecretFile(Exception):
    """The secret file fails a safety check (symlink / perms / owner / type)."""


def load_secret_file(path: str) -> str:
    """Return the stripped contents of ``path`` after TOCTOU-safe safety checks.

    Raises :class:`InsecureSecretFile` for a symlink, group/other-accessible
    permissions, an unexpected owner, or a non-regular file;
    :class:`FileNotFoundError` if missing. The value is never logged here.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        # ELOOP: the final path component is a symlink (refused by O_NOFOLLOW).
        if e.errno == errno.ELOOP:
            raise InsecureSecretFile(f"secret file is a symlink: {path}") from e
        raise
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise InsecureSecretFile(f"secret file is not a regular file: {path}")
        mode = stat.S_IMODE(st.st_mode)
        if mode & 0o077:
            raise InsecureSecretFile(
                f"secret file {path} is group/other-accessible (mode {oct(mode)}); "
                "require 0600 or 0400"
            )
        if st.st_uid not in (os.getuid(), 0):
            raise InsecureSecretFile(
                f"secret file {path} is owned by uid {st.st_uid}, not the current user"
            )
        with os.fdopen(fd, encoding="utf-8") as f:
            fd = -1  # fdopen takes ownership; don't double-close
            return f.read().strip()
    finally:
        if fd >= 0:
            os.close(fd)


def load_secret_json(path: str) -> Any:
    """Load and parse a JSON secret file through :func:`load_secret_file`.

    The same safety checks apply (symlink / perms / owner / type). The parsed
    value is returned as-is; the caller validates its shape. On malformed JSON a
    :class:`InsecureSecretFile` is raised with the path but **not** the contents,
    so the secret value can never leak into a traceback.
    """
    raw = load_secret_file(path)
    try:
        return json.loads(raw)
    except ValueError as e:
        raise InsecureSecretFile(f"secret file {path} is not valid JSON") from e
