"""Flexible authentication/authorization for the OQTOPUS backend.

Historically the User API trusted a single identity contract: the API Gateway
Lambda authorizer verified the caller's Cognito ID token (or ``q-api-token``)
and injected ``requestContext.authorizer["user_id"]``, which the FastAPI
middleware read into ``request.state.user_id``.

To let the whole stack run outside AWS (e.g. on an internal network fronted by
oauth2-proxy + Keycloak + LDAP), identity resolution is now pluggable via the
``AUTH_MODE`` environment variable:

- ``aws``   : read the identity from the API Gateway authorizer context
              (Mangum ``request.scope["aws.event"]``). Unchanged prod behavior.
- ``oidc``  : verify a Bearer JWT against any OIDC issuer (JWKS) and derive the
              identity from a configurable claim. Authorization (account-status
              check) is enforced in-app, replacing what the Lambda authorizer
              did upstream.
- ``local`` : hardcoded developer identity (the existing ``ENV=local`` bypass).

When ``AUTH_MODE`` is unset the mode defaults to ``local`` if ``ENV=local`` else
``aws`` -- so existing deployments and tests behave exactly as before.
"""

from oqtopus_cloud.common.auth.identity import (
    AuthError,
    Identity,
    auth_mode,
    resolve_identity,
)

__all__ = ["AuthError", "Identity", "auth_mode", "resolve_identity"]
