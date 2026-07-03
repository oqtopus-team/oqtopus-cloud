SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help bastion port-forward db-session migrate-up migrate-stamp

include .env
export

bastion: ## SSH into the bastion host
	@aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --profile $(PROFILE)

port-forward: ## Port forward to the RDS instance
	@aws ec2-instance-connect ssh --instance-id $(BASTION_HOST) --connection-type eice --local-forwarding $(MYSQL_PORT):$(MYSQL_HOST):$(MYSQL_PORT) --profile $(PROFILE)


db-session: ## Start a MySQL session
	@export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && \
	export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && \
	mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD $(DB_NAME)

migrate-up: ## Apply Alembic migrations to the DB (run with `make port-forward` active in another shell)
	@SECRET=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString) && \
	export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:$(MYSQL_PORT)/$(DB_NAME)" && \
	$(MAKE) -C ../../backend migrate-up

migrate-stamp: ## One-time baseline for a DB created before Alembic: mark it at head WITHOUT running DDL
	@SECRET=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString) && \
	export ALEMBIC_DATABASE_URL="mysql+pymysql://$$(echo "$$SECRET" | jq -j '.username|@uri'):$$(echo "$$SECRET" | jq -j '.password|@uri')@localhost:$(MYSQL_PORT)/$(DB_NAME)" && \
	cd ../../backend && uv run alembic stamp head

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
