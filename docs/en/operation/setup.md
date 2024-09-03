
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

.PHONY: help port-forward session db-init

include .env

bastion:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --profile $(PROFILE)

port-forward:
  @aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --local-forwarding $(MYSQL_PORT):$(MYSQL_HOST):$(MYSQL_PORT) --profile $(PROFILE)

db-session:
  @export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && 	export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD $(DB_NAME)

db-init:
  @export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && 	export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD < ./db/init.sql
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

## Initializing the DB

Run the following command to initialize the DB.

```bash
make db-init
```

> [!NOTE]
> `make db-init` runs the following command in the background:
>
> ```bash
> export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .username) &&     export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id <SECRET_NAME> --profile <PROFILE> | jq -r .SecretString | jq -r .password) &&     mysql --protocol TCP -h localhost -P <MYSQL_PORT> -u $$MYSQL_USER --password=$$MYSQL_PASSWORD <DB_NAME> < ./db/init.sql
>```

Run `make db-session` to connect to the DB and verify that the initialization is complete. If the tables are created, the initialization is complete.

```sql
mysql> show tables;
+---------------------+
| Tables_in_main      |
+---------------------+
| devices             |
| results             |
| tasks               |
+---------------------+
4 rows in set (0.05 sec)
```
