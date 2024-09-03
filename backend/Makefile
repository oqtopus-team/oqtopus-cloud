SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: generate-user-schema generate-provider-schema generate-all-schema run-user run-provider up down fmt lint test help

generate-user-schema: ## Generate user schema
	@cd oas && $(MAKE) generate-user
	@$(MAKE) generate \
	INPUT=./oas/user/openapi.yaml \
	OUTPUT=oqtopus_cloud/user/schemas
	@$(MAKE) fmt-user

generate-provider-schema: ## Generate provider schema
	@cd oas && $(MAKE) generate-provider
	@$(MAKE) generate \
	INPUT=./oas/provider/openapi.yaml \
	OUTPUT=oqtopus_cloud/provider/schemas
	@$(MAKE) fmt-provider

generate:
	@poetry run datamodel-codegen \
	--use-schema-description \
	--target-python-version 3.12 \
	--enable-version-header \
	--field-constraints \
	--use-annotated \
	--use-field-description \
	--input ${INPUT} \
	--input-file-type openapi \
	--output-model-type pydantic_v2.BaseModel \
	--enum-field-as-literal all \
	--use-standard-collections \
	--strict-nullable \
	--use-default \
	--output ${OUTPUT}

generate-all-schema: ## Generate user and provider schemas
	@$(MAKE) generate-user-schema
	@$(MAKE) generate-provider-schema

export ENV=local
export DB_HOST=localhost
export DB_NAME=main
export DB_CONNECTOR=mysql+pymysql

run-user: ## Start the User API
	@export POWERTOOLS_METRICS_NAMESPACE=user-api && \
	export POWERTOOLS_SERVICE_NAME=user-api && \
	poetry run uvicorn oqtopus_cloud.user.lambda_function:app --host 0.0.0.0 --port 8080 --reload

run-provider: ## Start the Provider API
	@export POWERTOOLS_METRICS_NAMESPACE=provider-api && \
	export POWERTOOLS_SERVICE_NAME=provider-api && \
	poetry run uvicorn oqtopus_cloud.provider.lambda_function:app --host 0.0.0.0 --port 8888 --reload

up: ## Start the DB
	@docker compose up

down: ## Stop the DB
	@docker compose down

fmt-common: ## Format common code
	@poetry run ruff format oqtopus_cloud/common

fmt-user: ## Format user code
	@poetry run ruff format oqtopus_cloud/user

fmt-provider: ## Format provider code
	@poetry run ruff format oqtopus_cloud/provider

fmt-all: fmt-common fmt-user fmt-provider ## Format all code

lint-common: ## Run common linters
	@poetry run ruff check oqtopus_cloud/common
	@poetry run mypy -p oqtopus_cloud.common

lint-user: ## Run user linters
	@poetry run ruff check oqtopus_cloud/user
	@poetry run mypy -p oqtopus_cloud.user

lint-provider: ## Run provider linters
	@poetry run ruff check oqtopus_cloud/provider
	@poetry run mypy -p oqtopus_cloud.provider

lint-all: lint-common lint-user lint-provider ## Run all linters

test-common: fmt-common lint-common ## Run common tests
	@export POWERTOOLS_METRICS_NAMESPACE=common && \
	export POWERTOOLS_SERVICE_NAME=common && \
	poetry run pytest tests/oqtopus_cloud/common/ -vv --cov=oqtopus_cloud/common --cov-report=xml:../coverage.xml --cov-report=html:../htmlcov

test-user: fmt-user lint-user ## Run User API tests
	@export POWERTOOLS_METRICS_NAMESPACE=user-api && \
	export POWERTOOLS_SERVICE_NAME=user-api && \
	poetry run pytest tests/oqtopus_cloud/user/ -vv --cov=oqtopus_cloud/user --cov-report=xml:../coverage.xml --cov-report=html:../htmlcov

test-provider: fmt-provider lint-provider ## Run Provider tests
	@export POWERTOOLS_METRICS_NAMESPACE=provider-api && \
	export POWERTOOLS_SERVICE_NAME=provider-api && \
	poetry run pytest tests/oqtopus_cloud/provider/ -vv --cov=oqtopus_cloud/provider --cov-report=xml:../coverage.xml --cov-report=html:../htmlcov

test-all: fmt-all lint-all ## Run All tests
	@export POWERTOOLS_METRICS_NAMESPACE=all && \
	export POWERTOOLS_SERVICE_NAME=all && \
	poetry run pytest tests/oqtopus_cloud -vv --cov=oqtopus_cloud --cov-report=xml:../coverage.xml --cov-report=html:../htmlcov


help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
