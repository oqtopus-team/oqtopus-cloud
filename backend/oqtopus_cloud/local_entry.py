"""Entry points for running the APIs locally.

uvicorn options are supplied through environment variables. uvicorn's click CLI
is declared with ``auto_envvar_prefix="UVICORN"``, so every option it accepts
can be set as ``UVICORN_<OPTION>`` (shared by all APIs). To set an option for a
single API, use ``<SCOPE>_<OPTION>`` (e.g. ``USER_API_LOG_LEVEL``), which takes
precedence over ``UVICORN_<OPTION>``.

``POWERTOOLS_SERVICE_NAME`` and ``POWERTOOLS_METRICS_NAMESPACE`` can likewise be
set per API as ``<SCOPE>_POWERTOOLS_SERVICE_NAME`` etc.; they default to the
service name (e.g. ``user-api``).

Only names that are real uvicorn options are mapped, so unrelated variables
sharing the prefix (e.g. ``USER_API_URL``) are left alone.

The ``oqtopus-cloud-*`` command names defined in ``pyproject.toml`` are depended
on by oqtopus-cli. Renaming them is a breaking change.
"""

import os
import sys
from dataclasses import dataclass

from uvicorn.main import main as uvicorn_cli


@dataclass(frozen=True)
class ApiSpec:
    name: str  # service name (as in the Makefile), e.g. "user-api"
    app: str  # uvicorn import string

    @property
    def scope(self) -> str:
        """Environment variable prefix, e.g. "USER_API" (without trailing "_")."""
        return self.name.upper().replace("-", "_")


USER = ApiSpec("user-api", "oqtopus_cloud.user.lambda_function:app")
PROVIDER = ApiSpec("provider-api", "oqtopus_cloud.provider.lambda_function:app")
ADMIN = ApiSpec("admin-api", "oqtopus_cloud.admin.lambda_function:app")
USER_SIGNUP = ApiSpec(
    "user_signup-api", "oqtopus_cloud.user_signup.lambda_function:app"
)


# Names that can be set per API as ``<SCOPE>_<NAME>``.
_POWERTOOLS_VARS = ("POWERTOOLS_SERVICE_NAME", "POWERTOOLS_METRICS_NAMESPACE")


def _uvicorn_option_names() -> frozenset[str]:
    """Return the upper-cased names of the options the uvicorn CLI accepts."""
    names = frozenset(
        p.name.upper() for p in uvicorn_cli.params if p.name and p.name != "app"
    )
    if not names:
        raise RuntimeError("could not read uvicorn options from its click command")
    return names


def _drop_empty(key: str) -> None:
    """Treat an empty value as unset, since click cannot convert ''."""
    if os.environ.get(key) == "":
        del os.environ[key]


def apply_scoped_uvicorn_env(scope: str) -> None:
    """Promote ``<SCOPE>_FOO`` to ``UVICORN_FOO`` for real uvicorn options FOO."""
    options = _uvicorn_option_names()
    prefix = f"{scope}_"
    for key, value in list(os.environ.items()):
        if not key.startswith(prefix) or value == "":
            continue
        name = key[len(prefix) :]
        if name in options:
            os.environ[f"UVICORN_{name}"] = value


def _start_uvicorn(app: str) -> None:
    uvicorn_cli(args=[app])


def apply_scoped_powertools_env(scope: str) -> None:
    """Promote ``<SCOPE>_POWERTOOLS_*`` to ``POWERTOOLS_*`` (see ``_POWERTOOLS_VARS``)."""
    for name in _POWERTOOLS_VARS:
        value = os.environ.get(f"{scope}_{name}", "")
        if value != "":
            os.environ[name] = value


def _run(spec: ApiSpec) -> None:
    # Must be set before the application is imported (uvicorn imports it below).
    for key in _POWERTOOLS_VARS:
        _drop_empty(key)
    apply_scoped_powertools_env(spec.scope)
    for key in _POWERTOOLS_VARS:
        os.environ.setdefault(key, spec.name)

    for key in ("UVICORN_HOST", "UVICORN_PORT"):
        _drop_empty(key)
    apply_scoped_uvicorn_env(spec.scope)
    os.environ.setdefault("UVICORN_HOST", "127.0.0.1")
    if "UVICORN_PORT" not in os.environ:
        # No default here: ports are defined in backend/Makefile (and by the
        # caller, e.g. oqtopus-cli). uvicorn's own default would collide.
        sys.exit(f"{spec.scope}_PORT (or UVICORN_PORT) must be set")

    _start_uvicorn(spec.app)


def run_user() -> None:
    _run(USER)


def run_provider() -> None:
    _run(PROVIDER)


def run_admin() -> None:
    _run(ADMIN)


def run_user_signup() -> None:
    _run(USER_SIGNUP)
