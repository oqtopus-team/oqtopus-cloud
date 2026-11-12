"""Command step sequences (ordered, idempotent, fail-closed).

Each function returns an ordered ``{step_name: callable}`` mapping. The order is
the contract:

- ``user-disable`` / ``user-delete`` (Phase 1 = logical delete, no physical
    removal) suspend the DB **first** so API access stops immediately, then revoke
    the API token and Keycloak sessions, remove the admin group, and lock the LDAP
    account. A partial failure stays fail-closed (only disable steps remain).
- ``admin-revoke`` removes the LDAP group **before** revoking sessions.
- ``admin-grant`` adds the group then revokes sessions so a re-login/refresh
    picks up the new role.

Callables depend only on the adapter protocols, so these are unit-testable with
fakes. The temp password passed to ``user-add`` is used by a step and never
logged by the orchestrator (only step names are audited).
"""

from __future__ import annotations

from collections.abc import Callable

from oqtopus_cloud.ops.adapters import DbOps, KeycloakOps, LdapOps

Steps = dict[str, Callable[[], None]]


def user_add_steps(
    ldap: LdapOps,
    *,
    uid: str,
    email: str,
    cn: str,
    sn: str,
    given_name: str,
    temp_password: str,
) -> Steps:
    def validate() -> None:
        # A fresh add must not reset an existing user's password: reject any
        # existing uid, and reject the email if it already belongs to another
        # entry. (Re-running a failed add uses --operation-id, where this step is
        # already `done` and skipped.)
        if ldap.find_user(uid) is not None:
            raise ValueError(
                f"LDAP already has uid={uid!r}; refusing to re-add (use a dedicated reset flow)"
            )
        if ldap.find_by_mail(email) is not None:
            raise ValueError(f"email {email!r} already belongs to another LDAP entry")

    return {
        "validate_ldap_entry": validate,
        "create_ldap_entry": lambda: ldap.create_user(uid, email, cn, sn, given_name),
        "set_temp_password": lambda: ldap.set_temp_password(uid, temp_password),
    }


def user_disable_steps(
    ldap: LdapOps, keycloak: KeycloakOps, db: DbOps, *, uid: str, email: str
) -> Steps:
    def preflight() -> None:
        # Read-only identity check BEFORE the first mutation: the uid (LDAP /
        # Keycloak) and the email (DB) must be the same person, or we could
        # suspend one user and disable another on a typo.
        entry = ldap.find_user(uid)
        if entry is None:
            raise ValueError(f"no LDAP user with uid={uid!r}")
        if entry.get("mail") != email:
            raise ValueError(
                f"uid/email mismatch: uid={uid!r} has mail={entry.get('mail')!r}, not {email!r}"
            )
        # A DB row may not exist yet (user added but never logged in, so not
        # auto-provisioned). That is "already inaccessible in the DB", not an
        # error: db_suspend below is a no-op in that case and the session/group/
        # LDAP deactivation still runs.

    return {
        "preflight_identity": preflight,
        # DB first: stops API access immediately (approved gate -> suspended).
        "db_suspend": lambda: db.suspend(email),
        "revoke_api_token": lambda: db.revoke_api_token(email),
        "revoke_keycloak_sessions": lambda: keycloak.revoke_sessions(uid),
        "remove_admin_group": lambda: ldap.remove_from_admin_group(uid),
        "disable_ldap_account": lambda: ldap.disable_account(uid),
    }


# Phase 1: a user "delete" is a logical delete (same steps as disable, tombstone
# retained). Physical removal is Phase 2.
user_delete_steps = user_disable_steps


def admin_grant_steps(
    ldap: LdapOps, keycloak: KeycloakOps, *, uid: str
) -> Steps:
    def preflight() -> None:
        # Don't add a non-existent uid to the group (dangling member).
        if ldap.find_user(uid) is None:
            raise ValueError(f"no LDAP user with uid={uid!r}")

    return {
        "preflight_identity": preflight,
        "add_admin_group": lambda: ldap.add_to_admin_group(uid),
        # Revoke sessions so a re-login / refresh issues a token with the role.
        "revoke_keycloak_sessions": lambda: keycloak.revoke_sessions(uid),
    }


def admin_revoke_steps(
    ldap: LdapOps, keycloak: KeycloakOps, *, uid: str
) -> Steps:
    return {
        # Remove the group first, then revoke sessions. NOTE: already-issued
        # self-contained access tokens keep the admin role until they expire; the
        # effective revocation SLA is the access-token max lifetime (immediate
        # revocation would require per-request DB/LDAP checks or a denylist).
        "remove_admin_group": lambda: ldap.remove_from_admin_group(uid),
        "revoke_keycloak_sessions": lambda: keycloak.revoke_sessions(uid),
    }
