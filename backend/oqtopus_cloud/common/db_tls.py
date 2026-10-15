"""TLS settings for database connections.

The RDS Proxy rejects non-TLS connections, so every client that talks to the
database -- the Lambdas via `session.py` and Alembic via `alembic/env.py` --
has to present the CA bundle shipped in `oqtopus_cloud/common/certs`. Keeping
that in one place is deliberate: when the Alembic environment built its engine
without these arguments, every migration against a real environment failed with
`(3159) This RDS Proxy requires TLS connections`, while the application itself
connected fine.
"""

import os
from typing import Any

# Amazon RDS CA bundle shipped inside this package (see certs/README.md for why
# it is a combined RDS + Amazon Trust Services bundle). Overridable via the
# DB_SSL_CA env var (wired through Terraform), with this bundled copy as a safe
# fallback so a missing env var cannot silently drop TLS or cause an outage.
DEFAULT_DB_SSL_CA = os.path.join(
    os.path.dirname(__file__), "certs", "global-bundle.pem"
)

# Hosts that can only be reached through an `ec2-instance-connect` port-forward
# (see operation/Makefile.common). The RDS Proxy certificate is issued for
# `*.proxy-*.rds.amazonaws.com`, so verifying it against the local end of the
# tunnel can never succeed.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def ssl_ca_path() -> str:
    """Return the CA bundle used to verify the database server certificate."""
    return os.environ.get("DB_SSL_CA", DEFAULT_DB_SSL_CA)


def ssl_connect_args(host: str | None = None) -> dict[str, Any]:
    """Return the PyMySQL `connect_args` entries that enable TLS.

    Empty when ENV=local, where the dev MySQL container is reached over a
    trusted network and serves no CA-signed certificate.

    `host` is the host the client actually dials. For a loopback host the
    connection is going through a port-forward to the RDS Proxy, so hostname
    verification is disabled -- the certificate names the proxy, never
    `localhost`. The certificate chain itself is still verified against
    `ssl_ca_path()`, so this does not accept an arbitrary server.
    """
    if os.environ.get("ENV") == "local":
        return {}
    ssl: dict[str, Any] = {"ca": ssl_ca_path()}
    if host in _LOOPBACK_HOSTS:
        ssl["check_hostname"] = False
    return {"ssl": ssl}
