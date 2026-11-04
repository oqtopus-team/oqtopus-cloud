"""``oqtopus-cloud-ops`` CLI: on-prem user/admin lifecycle orchestrator.

Secrets are read from files, never from CLI args, env, or logs. The ``user-add``
temp password is generated (not taken from the CLI) and written to a 0600 file
created with ``O_EXCL | O_NOFOLLOW`` for out-of-band delivery; on resume the
original value is re-read from that same file (never regenerated). A resume
(``--operation-id``) must match the stored command / inputs / steps exactly, or
it is refused. A failed or locked operation exits non-zero.
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets as pysecrets
import sys

from oqtopus_cloud.ops import commands
from oqtopus_cloud.ops.adapters import DbClient, KeycloakClient, LdapClient
from oqtopus_cloud.ops.journal import OperationJournal
from oqtopus_cloud.ops.orchestrator import OperationFailed, OperationLocked, run
from oqtopus_cloud.ops.secrets import load_secret_file


def _cfg(args: argparse.Namespace, flag: str, env: str) -> str:
    v = getattr(args, flag.replace("-", "_")) or os.getenv(env)
    if v is None:
        raise SystemExit(f"missing required config: --{flag} or {env}")
    return v


def _ldap(args: argparse.Namespace) -> LdapClient:
    return LdapClient(
        server_uri=_cfg(args, "ldap-server", "LDAP_SERVER_URI"),
        bind_dn=_cfg(args, "ldap-bind-dn", "LDAP_BIND_DN"),
        bind_password=load_secret_file(args.ldap_bind_password_file),
        users_base=_cfg(args, "ldap-users-base", "LDAP_USERS_BASE"),
        admin_group_dn=_cfg(args, "ldap-admin-group-dn", "LDAP_ADMIN_GROUP_DN"),
        use_tls=not args.ldap_insecure,
        ca_certs_file=args.ldap_ca_cert_file,
        allow_insecure=args.ldap_insecure,
    )


def _keycloak(args: argparse.Namespace) -> KeycloakClient:
    return KeycloakClient(
        base_url=_cfg(args, "keycloak-url", "KEYCLOAK_URL"),
        realm=_cfg(args, "keycloak-realm", "KEYCLOAK_REALM"),
        client_id=_cfg(args, "keycloak-client-id", "KEYCLOAK_CLIENT_ID"),
        client_secret=load_secret_file(args.keycloak_secret_file),
        ca_cert_file=args.keycloak_ca_cert_file,
    )


def _endpoints(
    args: argparse.Namespace,
    *,
    keycloak: bool = False,
    db: bool = False,
    users_base: bool = False,
    admin_group: bool = False,
) -> dict:
    """Non-secret identifiers that MUST match on resume: binds the operation to a
    specific deployment and its LDAP/Keycloak/DB endpoints (so devs can't resume
    a half-done operation against prod)."""
    e = {
        "deployment_id": _cfg(args, "deployment-id", "DEPLOYMENT_ID"),
        "ldap_server": _cfg(args, "ldap-server", "LDAP_SERVER_URI"),
    }
    if users_base:
        e["users_base"] = _cfg(args, "ldap-users-base", "LDAP_USERS_BASE")
    if admin_group:
        e["admin_group_dn"] = _cfg(args, "ldap-admin-group-dn", "LDAP_ADMIN_GROUP_DN")
    if keycloak:
        e["keycloak_url"] = _cfg(args, "keycloak-url", "KEYCLOAK_URL")
        e["keycloak_realm"] = _cfg(args, "keycloak-realm", "KEYCLOAK_REALM")
        e["keycloak_client_id"] = _cfg(args, "keycloak-client-id", "KEYCLOAK_CLIENT_ID")
    if db:
        e["db_host"] = os.getenv("DB_HOST", "")
        e["db_name"] = os.getenv("DB_NAME", "")
    return e


def _write_new_temp_password(path: str) -> str:
    # Strong temp password, written exclusively (no overwrite) without following
    # a symlink; 0600; never logged / stdout / journaled.
    pw = pysecrets.token_urlsafe(18)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(pw + "\n")
    return pw


def _run(journal, command, target, steps, inputs, operation_id) -> None:
    step_names = list(steps)
    if operation_id:
        op = journal.load(operation_id)
        if op.command != command or op.inputs != inputs or op.step_names() != step_names:
            print(
                f"ERROR: --operation-id {operation_id} does not match this invocation "
                "(command/inputs/steps differ); refusing to resume against a different target",
                file=sys.stderr,
            )
            raise SystemExit(2)
    else:
        op = journal.create(command, target, step_names, inputs)
    try:
        run(journal, op, steps)
    except OperationLocked as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    except OperationFailed as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print(f"re-run with --operation-id {op.operation_id} to resume", file=sys.stderr)
        raise SystemExit(1) from e
    print(f"OK: {command} completed (operation_id={op.operation_id})", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    p = argparse.ArgumentParser(prog="oqtopus-cloud-ops")
    p.add_argument("--journal-dir", default=os.getenv("OPS_JOURNAL_DIR", "./ops-journal"))
    p.add_argument("--operation-id", default=None, help="resume a prior operation")
    p.add_argument("--deployment-id", default=None, help="explicit env id bound into the journal")
    p.add_argument("--keycloak-ca-cert-file", default=os.getenv("KEYCLOAK_CA_CERT_FILE"))
    for flag in (
        "ldap-server", "ldap-bind-dn", "ldap-users-base", "ldap-admin-group-dn",
        "keycloak-url", "keycloak-realm", "keycloak-client-id",
    ):
        p.add_argument(f"--{flag}", default=None)
    p.add_argument("--ldap-ca-cert-file", default=os.getenv("LDAP_CA_CERT_FILE"))
    p.add_argument("--ldap-insecure", action="store_true", help="demo only: plaintext LDAP (no TLS)")
    p.add_argument("--ldap-bind-password-file", default=os.getenv("LDAP_BIND_PASSWORD_FILE"))
    p.add_argument("--keycloak-secret-file", default=os.getenv("KEYCLOAK_SECRET_FILE"))

    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("user-add")
    for f in ("uid", "email", "cn", "sn", "given-name"):
        a.add_argument(f"--{f}", required=True)
    a.add_argument("--temp-password-out", required=True, help="0600 file for the generated temp password")
    for name in ("user-disable", "user-delete"):
        d = sub.add_parser(name)
        d.add_argument("--uid", required=True)
        d.add_argument("--email", required=True)
    for name in ("admin-grant", "admin-revoke"):
        g = sub.add_parser(name)
        g.add_argument("--uid", required=True)

    args = p.parse_args(argv)
    journal = OperationJournal(args.journal_dir)

    if args.command == "user-add":
        # Build the adapter (validates LDAP config + loads the bind secret) and
        # resolve inputs (validates endpoints) BEFORE generating the temp
        # password file, so a config error never leaves an orphaned password.
        ldap = _ldap(args)
        inputs = {
            "uid": args.uid, "email": args.email, "cn": args.cn, "sn": args.sn,
            "given_name": args.given_name, "temp_password_out": args.temp_password_out,
            **_endpoints(args, users_base=True),
        }
        temp_pw = (
            load_secret_file(args.temp_password_out)
            if args.operation_id
            else _write_new_temp_password(args.temp_password_out)
        )
        steps = commands.user_add_steps(
            ldap, uid=args.uid, email=args.email, cn=args.cn, sn=args.sn,
            given_name=args.given_name, temp_password=temp_pw,
        )
        _run(journal, "user-add", args.uid, steps, inputs, args.operation_id)
    elif args.command in ("user-disable", "user-delete"):
        steps = commands.user_disable_steps(
            _ldap(args), _keycloak(args), DbClient(), uid=args.uid, email=args.email
        )
        if args.command == "user-delete":
            print("note: Phase 1 user-delete is a LOGICAL delete (no physical removal)", file=sys.stderr)
        inputs = {
            "uid": args.uid, "email": args.email,
            **_endpoints(args, keycloak=True, db=True, users_base=True, admin_group=True),
        }
        _run(journal, args.command, args.uid, steps, inputs, args.operation_id)
    elif args.command == "admin-grant":
        steps = commands.admin_grant_steps(_ldap(args), _keycloak(args), uid=args.uid)
        inputs = {"uid": args.uid, **_endpoints(args, keycloak=True, admin_group=True)}
        _run(journal, "admin-grant", args.uid, steps, inputs, args.operation_id)
    elif args.command == "admin-revoke":
        steps = commands.admin_revoke_steps(_ldap(args), _keycloak(args), uid=args.uid)
        inputs = {"uid": args.uid, **_endpoints(args, keycloak=True, admin_group=True)}
        _run(journal, "admin-revoke", args.uid, steps, inputs, args.operation_id)


if __name__ == "__main__":
    main()
