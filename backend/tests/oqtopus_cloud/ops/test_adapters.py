"""Real-adapter safety: LDAP failures are never swallowed; TLS/HTTPS required."""

import pytest
from ldap3.core.exceptions import (
    LDAPAttributeOrValueExistsResult,
    LDAPEntryAlreadyExistsResult,
    LDAPInsufficientAccessRightsResult,
    LDAPNoSuchAttributeResult,
)

from oqtopus_cloud.ops.adapters import KeycloakClient, LdapClient


class _Std:
    def __init__(self, ok):
        self._ok = ok

    def modify_password(self, user=None, new_password=None):
        return self._ok


class _Ext:
    def __init__(self, ok):
        self.standard = _Std(ok)


class FakeConn:
    def __init__(self, *, add_exc=None, modify_exc=None, pw_ok=True):
        self._add_exc = add_exc
        self._modify_exc = modify_exc
        self.extend = _Ext(pw_ok)
        self.result = {"description": "test"}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def add(self, *a, **k):
        if self._add_exc:
            raise self._add_exc

    def modify(self, *a, **k):
        if self._modify_exc:
            raise self._modify_exc


def _client(conn):
    return LdapClient(
        server_uri="ldap://x", bind_dn="cn=x", bind_password="p",
        users_base="ou=people,dc=x", admin_group_dn="cn=admins,dc=x",
        use_tls=False, allow_insecure=True, conn_factory=lambda: conn,
    )


def test_add_failure_is_not_swallowed():
    c = _client(FakeConn(add_exc=LDAPInsufficientAccessRightsResult("acl")))
    with pytest.raises(LDAPInsufficientAccessRightsResult):
        c.create_user("u", "u@x", "c", "s", "g")


def test_add_already_exists_fails_closed():
    # A concurrent create after preflight must NOT be swallowed (it would let
    # set_temp_password reset another operation's account).
    c = _client(FakeConn(add_exc=LDAPEntryAlreadyExistsResult("dup")))
    with pytest.raises(LDAPEntryAlreadyExistsResult):
        c.create_user("u", "u@x", "c", "s", "g")


def test_modify_failure_is_not_swallowed():
    c = _client(FakeConn(modify_exc=LDAPInsufficientAccessRightsResult("acl")))
    with pytest.raises(LDAPInsufficientAccessRightsResult):
        c.disable_account("u")


def test_add_group_already_member_is_idempotent():
    c = _client(FakeConn(modify_exc=LDAPAttributeOrValueExistsResult("dup")))
    c.add_to_admin_group("u")  # no raise


def test_remove_group_not_member_is_idempotent():
    c = _client(FakeConn(modify_exc=LDAPNoSuchAttributeResult("none")))
    c.remove_from_admin_group("u")  # no raise


def test_password_modify_failure_raises():
    c = _client(FakeConn(pw_ok=False))
    with pytest.raises(RuntimeError):
        c.set_temp_password("u", "secret")


def test_tls_requires_ca_cert():
    with pytest.raises(ValueError):
        LdapClient(
            server_uri="ldaps://x", bind_dn="cn=x", bind_password="p",
            users_base="ou=people", admin_group_dn="cn=admins",
            use_tls=True, ca_certs_file=None,
        )


def test_plaintext_requires_insecure_flag():
    with pytest.raises(ValueError):
        LdapClient(
            server_uri="ldap://x", bind_dn="cn=x", bind_password="p",
            users_base="ou=people", admin_group_dn="cn=admins",
            use_tls=False, allow_insecure=False,
        )


def test_keycloak_requires_https():
    with pytest.raises(ValueError):
        KeycloakClient(base_url="http://kc", realm="r", client_id="c", client_secret="s")
