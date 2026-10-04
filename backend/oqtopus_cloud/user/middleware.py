import asyncio
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from oqtopus_cloud.common.auth import AuthError, AuthorizationError, resolve_identity
from oqtopus_cloud.user.conf import logger

# resolve_identity is synchronous and, on the Q-API-Token path, does a blocking
# DB read plus a deliberately expensive Argon2 verify. Running it inline on the
# event loop would serialize *all* requests (incl. OIDC) behind one token check
# -- a trivial DoS with a single valid token_id. Offload it to a worker thread,
# and cap concurrency so a flood of token checks cannot exhaust CPU/memory
# (Argon2 is memory-hard). Tune with AUTH_MAX_CONCURRENCY (default 8).
_AUTH_MAX_CONCURRENCY = max(1, int(os.getenv("AUTH_MAX_CONCURRENCY", "8")))


class CustomMiddleware(BaseHTTPMiddleware):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auth_sem = asyncio.Semaphore(_AUTH_MAX_CONCURRENCY)

    async def dispatch(self, request: Request, call_next):
        corr_id = request.headers.get("x-correlation-id")
        if os.getenv("ENV") == "local":
            logger.info("Running in local environment")
            corr_id = "local-correlation-id"
        if not corr_id:
            corr_id = request.scope["aws.context"].aws_request_id
        corr_id = str(corr_id)

        logger.set_correlation_id(corr_id)

        # NB: this runs OUTSIDE FastAPI's ExceptionMiddleware, so raising
        # HTTPException here would surface as a 500 (only ServerErrorMiddleware
        # is further out). Return an explicit Response for auth failures instead.
        try:
            async with self._auth_sem:
                identity = await asyncio.to_thread(resolve_identity, request)
            request.state.user_id = identity.user_id
            request.state.user_pool_id = identity.user_pool_id
            request.state.region = identity.region
            request.state.auth_method = identity.auth_method
        except AuthorizationError as e:
            # Authenticated but not permitted (e.g. unapproved user) -> 403.
            # Re-authenticating would not help, so the SPA must NOT bounce to
            # login; it shows an access-denied state instead.
            logger.warning(f"Authorization failed: {e}")
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden"},
                headers={"X-Correlation-Id": corr_id},
            )
        except AuthError as e:
            # Authentication failed (missing/invalid token) -> 401. The SPA
            # treats this as a session-expiry and sends the browser to login.
            # Only advertise a challenge when the failed scheme defines one:
            # OIDC -> "Bearer"; the Q-API-Token path sets challenge=None so the
            # CLI is not misdirected to a Bearer flow.
            logger.warning(f"Authentication failed: {e}")
            headers = {"X-Correlation-Id": corr_id}
            if e.challenge:
                headers["WWW-Authenticate"] = e.challenge
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized"},
                headers=headers,
            )
        except KeyError:
            # AWS path: the API Gateway authorizer context is missing.
            logger.error("No AWS event found in request scope")
            return JSONResponse(
                status_code=500,
                content={"detail": "No AWS event found in request scope"},
                headers={"X-Correlation-Id": corr_id},
            )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = corr_id
        return response
