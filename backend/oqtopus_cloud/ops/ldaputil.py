"""LDAP DN / search-filter construction with library escaping.

Never build a DN or a search filter by string concatenation of untrusted input.
These helpers escape with ldap3 (RFC 4514 for RDN values, RFC 4515 for filter
assertion values).
"""

from __future__ import annotations

from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn


def user_dn(uid: str, users_base: str) -> str:
    """Return ``uid=<escaped>,<users_base>`` for a people-subtree entry."""
    return f"uid={escape_rdn(uid)},{users_base}"


def uid_filter(uid: str) -> str:
    """An ``(uid=<escaped>)`` equality filter."""
    return f"(uid={escape_filter_chars(uid)})"


def mail_filter(mail: str) -> str:
    """A ``(mail=<escaped>)`` equality filter."""
    return f"(mail={escape_filter_chars(mail)})"


def member_value(uid: str, users_base: str) -> str:
    """The ``member`` attribute value (the user's DN) for a groupOfNames."""
    return user_dn(uid, users_base)
