
# Operations

## Setting Up the Bastion Server

Create a directory for the environment under `operation/` (copying
`operation/example-dev/` is the quickest start) and put its settings in a `.env`
file there.

> [!NOTE]
> Replace the `<>` with appropriate values.*

```.env
MYSQL_HOST=<DB_HOST>
MYSQL_PORT=<DB_PORT>
DB_NAME=<DB_NAME>
PROFILE=<YOUR_PROFILE>
BASTION_HOST=<BASTION_HOST_ID>
SECRET_ID=<SECRET_NAME>
```

The `Makefile` next to it only loads that `.env` and includes the shared targets:

```Makefile
include .env
export

include ../Makefile.common
```

Every target lives in `operation/Makefile.common`, so all environments share one
implementation. Add targets there rather than in an environment's `Makefile`:
duplicating recipes per environment is what previously let a fix land in one
environment and not the others. Run `make help` in the environment directory to
list what is available.

Now, run `make bastion` to connect to the bastion server.

```bash
make bastion
```

> [!NOTE]
> `make bastion` runs the following command in the background:
>
> ```bash
> aws ec2-instance-connect ssh --instance-id <BASTION_SERVER_ID> --profile <EXECUTION_ENV_PROFILE>
> ```

Once connected to the bastion server, run the following command to install the MySQL client on the bastion server.

```bash
sudo yum install -y mysql
```

This completes the setup of the bastion server.

## Connecting to RDS via Port Forwarding

Run the following command to port forward to the remote RDS.

```bash
make port-forward
```

> [!NOTE]
> `make port-forward` runs the following command in the background:
>
> ```bash
> aws ec2-instance-connect ssh --instance-id <BASTION_SERVER_ID> --connection-type eice --local-forwarding <PORT>:<RDS_ENDPOINT>:<PORT> --profile <EXECUTION_ENV_PROFILE>
> ```

## Connecting to the DB

With the remote RDS port forwarded via `make port-forward`, run the following command in a separate session to connect to the DB.

```bash
make db-session
```

> [!NOTE]
> `make db-session` runs the following command in the background:
>
> ```bash
> export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .username) &&     export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .password) &&     mysql --protocol TCP -h localhost -P <MYSQL_PORT> -u $$MYSQL_USER --password=$$MYSQL_PASSWORD <DB_NAME>
> ```

Now, you have successfully connected to the RDS.

## Migrating the DB

The DB schema is managed with Alembic migrations (`backend/alembic/`). With the remote RDS port-forwarded via `make port-forward`, run the following in a separate session to apply any pending migrations.

```bash
make migrate-current   # read-only: which revision is the DB at?
make migrate-up        # apply everything still pending
make migrate-current   # read-only: confirm it reached head
```

> [!NOTE]
> `make migrate-up` runs the following in the background. It applies `alembic upgrade head` against the port-forwarded RDS on `localhost` (overriding the connection via `ALEMBIC_DATABASE_URL`):
>
> ```bash
> SECRET=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString) && \
> export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:<MYSQL_PORT>/<DB_NAME>" && \
> cd ../../backend && uv run alembic upgrade head
> ```
>
> Alembic is invoked directly rather than through `backend/Makefile`, which
> configures the *local* docker stack and exports `ENV=local`. A sub-make applies
> that over anything passed in, which would make `alembic/env.py` treat a
> production database as the local container and skip TLS.

> [!WARNING]
> Run these from `operation/<env>/`, never the `migrate-*` targets in `backend/`.
> Those target the local docker database (`backend/Makefile` exports `ENV=local`
> and `DB_HOST=localhost`), and while this port-forward is open `localhost:3306`
> is the *remote* RDS — so they would act on a real environment while behaving as
> if it were the local container, including skipping TLS. Every connection logs
> its host and TLS state, so check that line if a migration behaves unexpectedly:
>
> ```
> INFO  [alembic.env] connecting to mysql+pymysql://admin:***@localhost:3306/main (TLS: on)
> ```

TLS needs no configuration here. `alembic/env.py` attaches the RDS CA bundle from
`backend/oqtopus_cloud/common/certs` for any non-local target, exactly as the
application does, because the RDS Proxy rejects plaintext connections with
`ERROR 3159 (HY000): This RDS Proxy requires TLS connections`. Hostname
verification is skipped only when the target host is a loopback address, since a
port-forward means the proxy certificate can never match the host being dialed.

> [!IMPORTANT]
> When applying to a database that existed before Alembic was introduced (tables
> already created), run `make migrate-stamp` **once** *before* `make migrate-up`.
> It records the root revision of the migration chain — the one whose schema the
> pre-Alembic database already has — without running any DDL, and then
> `make migrate-up` applies every revision created after it.
>
> This is deliberately not `alembic stamp head`: that marks the revisions between
> the baseline and head as applied while their DDL never runs, leaving the schema
> silently behind what Alembic reports as deployed. `make migrate-stamp` refuses
> to run against a database that already has a revision, so it cannot rewind a
> database that is already tracked.

`make migrate-check` reports drift between the models and the DB. On a database
created before Alembic this is expected to list the legacy columns and indexes
that the old `init.sql` created but the models no longer declare; treat it as
information, not a failure. Note that a future `alembic revision --autogenerate`
will propose **dropping** those, which has to be removed from the generated
revision by hand.

Run `make db-session` to connect to the DB and verify the tables exist. If you see the following tables, the migration is complete.

```sql
mysql> show tables;
+-----------------+
| Tables_in_main  |
+-----------------+
| alembic_version |
| announcements   |
| devices         |
| jobs            |
| users           |
| whitelist_users |
+-----------------+
6 rows in set (0.05 sec)
```
