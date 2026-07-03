
# Operations

## Setting Up the Bastion Server

Navigate to the `backend/operation` directory and create the following configuration file.

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

The same directory contains a Makefile that is set up to read the `.env` file.

```Makefile
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help bastion port-forward db-session migrate-up migrate-stamp

include .env

bastion:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --profile $(PROFILE)

port-forward:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --local-forwarding $(MYSQL_PORT):$(MYSQL_HOST):$(MYSQL_PORT) --profile $(PROFILE)

db-session:
  @export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && 	export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD $(DB_NAME)

migrate-up:
  @SECRET=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString) && \
  export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:$(MYSQL_PORT)/$(DB_NAME)" && \
  $(MAKE) -C ../../backend migrate-up

migrate-stamp:
  @SECRET=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString) && \
  export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:$(MYSQL_PORT)/$(DB_NAME)" && \
  cd ../../backend && uv run alembic stamp head
```

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
make migrate-up
```

> [!NOTE]
> `make migrate-up` runs the following in the background. It applies `alembic upgrade head` against the port-forwarded RDS on `localhost` (overriding the connection via `ALEMBIC_DATABASE_URL`):
>
> ```bash
> SECRET=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString) && \
> export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:<MYSQL_PORT>/<DB_NAME>" && \
> make -C ../../backend migrate-up
> ```

> [!IMPORTANT]
> When applying to a database that existed before Alembic was introduced (tables already created), run `make migrate-stamp` **once** instead of `make migrate-up`. It records the current schema as the migration baseline (head) without running any DDL. Subsequent changes are then applied with `make migrate-up`.

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
