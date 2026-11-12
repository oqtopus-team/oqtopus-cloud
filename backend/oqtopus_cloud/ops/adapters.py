"""Side-effecting adapters for the ops orchestrator.

The command step sequences depend only on the :class:`LdapOps` /
:class:`KeycloakOps` / :class:`DbOps` protocols (so they can be unit-tested with
fakes). The concrete implementations below perform the real I/O.

Safety:
- LDAP connections use ``raise_exceptions=True``; only explicitly idempotent
    result codes (entry/attr already exists, no-such-attr on delete) are
    swallowed. Every other failure propagates, so a step is never journaled
    ``done`` on an ACL/schema/ppolicy/connectivity error.
- LDAP TLS requires the internal CA and ``CERT_REQUIRED`` (verified cert +
    hostname). Plaintext is only reachable via an explicit demo-only flag.
- Keycloak HTTP uses a timeout and expects an ``https`` base URL.
All methods are idempotent.
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Optional, Protocol

from ldap3 import MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, Connection, Server, Tls
from ldap3.core.exceptions import (
    LDAPAttributeOrValueExistsResult,
    LDAPNoSuchAttributeResult,
)

from oqtopus_cloud.common.models.user import User, UserStatus
from oqtopus_cloud.common.session import _create_session
from oqtopus_cloud.ops import ldaputil


class LdapOps(Protocol):
    def find_user(self, uid: str) -> Optional[dict]: ...
    def find_by_mail(self, mail: str) -> Optional[dict]: ...
    def create_user(self, uid: str, mail: str, cn: str, sn: str, given_name: str) -> None: ...
    def set_temp_password(self, uid: str, temp_password: str) -> None: ...
    def add_to_admin_group(self, uid: str) -> None: ...
    def remove_from_admin_group(self, uid: str) -> None: ...
    def disable_account(self, uid: str) -> None: ...


class KeycloakOps(Protocol):
    def revoke_sessions(self, username: str) -> None: ...


class DbOps(Protocol):
    def user_exists(self, user_email: str) -> bool: ...
    def suspend(self, user_email: str) -> None: ...
    def revoke_api_token(self, user_email: str) -> None: ...


# --- concrete implementations ------------------------------------------------


class LdapClient:
    def __init__(
        self,
        *,
        server_uri: str,
        bind_dn: str,
        bind_password: str,
        users_base: str,
        admin_group_dn: str,
        use_tls: bool = True,
        ca_certs_file: str | None = None,
        allow_insecure: bool = False,
        conn_factory: Callable[[], Connection] | None = None,
    ):
        if use_tls:
            if not ca_certs_file:
                raise ValueError("ca_certs_file is required for LDAP TLS (internal CA)")
            tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ca_certs_file)
            self._server = Server(server_uri, use_ssl=True, tls=tls)
        else:
            if not allow_insecure:
                raise ValueError("plaintext LDAP requires allow_insecure=True (demo only)")
            self._server = Server(server_uri, use_ssl=False)
        self._bind_dn = bind_dn
        self._bind_password = bind_password
        self._users_base = users_base
        self._admin_group_dn = admin_group_dn
        self._conn_factory = conn_factory

    def _conn(self) -> Connection:
        if self._conn_factory is not None:
            return self._conn_factory()
        # raise_exceptions: a rejected add/modify raises instead of returning False.
        return Connection(
            self._server,
            user=self._bind_dn,
            password=self._bind_password,
            auto_bind=True,
            raise_exceptions=True,
        )

    def _search_one(self, ldap_filter: str) -> Optional[dict]:
        with self._conn() as c:
            c.search(self._users_base, ldap_filter, attributes=["uid", "mail"])
            if not c.entries:
                return None
            if len(c.entries) > 1:
                raise RuntimeError(f"LDAP returned multiple entries for {ldap_filter}")
            e = c.entries[0]
            return {
                "dn": e.entry_dn,
                "uid": str(e.uid.value) if "uid" in e else None,
                "mail": str(e.mail.value) if "mail" in e else None,
            }

    def find_user(self, uid: str) -> Optional[dict]:
        return self._search_one(ldaputil.uid_filter(uid))

    def find_by_mail(self, mail: str) -> Optional[dict]:
        return self._search_one(ldaputil.mail_filter(mail))

    def create_user(self, uid: str, mail: str, cn: str, sn: str, given_name: str) -> None:
        dn = ldaputil.user_dn(uid, self._users_base)
        with self._conn() as c:
            # entryAlreadyExists is NOT swallowed. A fresh add runs only after
            # preflight found the DN absent (and is skipped on resume once done),
            # so hitting "already exists" means a concurrent create won the race.
            # Fail closed for manual reconciliation -- never fall through to
            # set_temp_password and reset another operation's account.
            c.add(
                dn,
                object_class=["inetOrgPerson"],
                attributes={"uid": uid, "cn": cn, "sn": sn, "givenName": given_name, "mail": mail},
            )

    def set_temp_password(self, uid: str, temp_password: str) -> None:
        dn = ldaputil.user_dn(uid, self._users_base)
        with self._conn() as c:
            # RFC 3062 Password Modify Extended Operation: the server hashes it.
            if not c.extend.standard.modify_password(user=dn, new_password=temp_password):
                raise RuntimeError(f"LDAP password modify failed: {c.result}")
            # Force a change at next login (ppolicy pwdReset).
            c.modify(dn, {"pwdReset": [(MODIFY_REPLACE, ["TRUE"])]})

    def add_to_admin_group(self, uid: str) -> None:
        member = ldaputil.member_value(uid, self._users_base)
        with self._conn() as c:
            try:
                c.modify(self._admin_group_dn, {"member": [(MODIFY_ADD, [member])]})
            except LDAPAttributeOrValueExistsResult:
                return  # already a member -> idempotent

    def remove_from_admin_group(self, uid: str) -> None:
        member = ldaputil.member_value(uid, self._users_base)
        with self._conn() as c:
            try:
                c.modify(self._admin_group_dn, {"member": [(MODIFY_DELETE, [member])]})
            except LDAPNoSuchAttributeResult:
                return  # not a member -> idempotent

    def disable_account(self, uid: str) -> None:
        dn = ldaputil.user_dn(uid, self._users_base)
        with self._conn() as c:
            # ppolicy account lock: a fixed past time locks the account.
            c.modify(dn, {"pwdAccountLockedTime": [(MODIFY_REPLACE, ["000001010000Z"])]})


class KeycloakClient:
    def __init__(
        self,
        *,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        ca_cert_file: str | None = None,
        timeout_seconds: float = 10.0,
    ):
        if not base_url.lower().startswith("https://"):
            # Internal CA / TLS everywhere; plaintext Keycloak is not allowed here.
            raise ValueError("Keycloak base_url must be https://")
        self._base = base_url.rstrip("/")
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout_seconds
        # Build an SSL context that trusts the internal CA. If no CA file is
        # given, the default context is used -- in that case the internal CA must
        # be registered in the OS trust store.
        self._ssl = ssl.create_default_context(cafile=ca_cert_file) if ca_cert_file else None

    def _open(self, req):
        return urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl)  # noqa: S310

    def _token(self) -> str:
        data = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        ).encode()
        url = f"{self._base}/realms/{self._realm}/protocol/openid-connect/token"
        with self._open(urllib.request.Request(url, data=data)) as r:
            return json.load(r)["access_token"]

    def revoke_sessions(self, username: str) -> None:
        token = self._token()
        q = urllib.parse.urlencode({"username": username, "exact": "true"})
        url = f"{self._base}/admin/realms/{self._realm}/users?{q}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with self._open(req) as r:
            users = json.load(r)
        for u in users:
            logout = f"{self._base}/admin/realms/{self._realm}/users/{u['id']}/logout"
            lreq = urllib.request.Request(
                logout, method="POST", headers={"Authorization": f"Bearer {token}"}
            )
            with self._open(lreq):
                pass


class DbClient:
    def user_exists(self, user_email: str) -> bool:
        db = _create_session()
        try:
            return db.get(User, user_email) is not None
        finally:
            db.close()

    def suspend(self, user_email: str) -> None:
        db = _create_session()
        try:
            user = db.get(User, user_email)
            if user is not None and user.userstatus != UserStatus.suspended:
                user.userstatus = UserStatus.suspended
                db.commit()
        finally:
            db.close()

    def revoke_api_token(self, user_email: str) -> None:
        db = _create_session()
        try:
            user = db.get(User, user_email)
            if user is not None and user.api_token_id is not None:
                user.api_token_id = None
                user.api_token_hash = None
                user.api_token_expiration = None
                db.commit()
        finally:
            db.close()
