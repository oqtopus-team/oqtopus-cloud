SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help port-forward session db-init

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

db-init: ## Initialize the database
	@export MYSQL_USER=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .username) && \
	export MYSQL_PASSWORD=$$(aws secretsmanager get-secret-value --secret-id $(SECRET_ID) --profile $(PROFILE) | jq -r .SecretString | jq -r .password) && \
	mysql --protocol TCP -h localhost -P $(MYSQL_PORT) -u $$MYSQL_USER --password=$$MYSQL_PASSWORD $(DB_NAME) < ../db/init.sql

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
