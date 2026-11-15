"""Secret-file loading for the ops CLI.

The implementation lives in :mod:`oqtopus_cloud.common.secret_file` so the API
containers (DB credentials) and the ops CLI (LDAP / Keycloak credentials) share
exactly one file-secret contract. This module re-exports it for the ops package.
"""

from __future__ import annotations

from oqtopus_cloud.common.secret_file import (
    InsecureSecretFile,
    load_secret_file,
    load_secret_json,
)

__all__ = ["InsecureSecretFile", "load_secret_file", "load_secret_json"]
