"""On-prem operator orchestrator (``oqtopus-cloud-ops``).

A Python orchestrator (not a shell command list) for the LDAP-backed user and
admin lifecycle on the single-server on-prem deployment. Every operation has a
unique ``operation_id`` and a persistent journal of its steps, so a re-run
resumes from the first incomplete step. Steps are idempotent; a partial failure
exits non-zero and never reports success, and deactivation operations are
fail-closed (they disable DB access first and never re-grant on recovery).
"""
