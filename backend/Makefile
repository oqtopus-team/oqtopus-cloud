SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: generate-user-schema generate-provider-schema generate-admin-schema generate-user_signup-schema generate-all-schema run-user run-provider run-admin run-user_signup run-worker up infra-up down infra-down infra-status check-presigned-post benchmark-presigned-post fmt lint test test-scripts test-storage-compatibility help

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


generate-admin-schema: ## Generate admin schema
	@cd oas && $(MAKE) generate-admin
	@$(MAKE) generate \
	INPUT=./oas/admin/openapi.yaml \
	OUTPUT=oqtopus_cloud/admin/schemas
	@$(MAKE) fmt-admin

generate-user_signup-schema: ## Generate user_signup schema
	@cd oas && $(MAKE) generate-user_signup
	@$(MAKE) generate \
	INPUT=./oas/user_signup/openapi.yaml \
	OUTPUT=oqtopus_cloud/user_signup/schemas
	@$(MAKE) fmt-user_signup


generate:
	@uv run datamodel-codegen \
	--use-schema-description \
	--target-python-version 3.12 \
	--field-constraints \
	--use-annotated \
	--use-field-description \
	--input ${INPUT} \
	--input-file-type openapi \
	--collapse-root-models \
	--enum-field-as-literal one \
	--output-datetime-class AwareDatetime \
	--use-union-operator \
	--use-subclass-enum \
	--custom-file-header-path "oqtopus_cloud/datamodel_codegen/datamodel-codegen-template.j2" \
	--output-model-type pydantic_v2.BaseModel \
	--disable-timestamp \
	--use-standard-collections \
	--strict-nullable \
	--use-default \
	--output ${OUTPUT}

generate-all-schema: ## Generate user, provider, and admin schemas
	@$(MAKE) generate-user-schema
	@$(MAKE) generate-provider-schema
	@$(MAKE) generate-admin-schema
	@$(MAKE) generate-user_signup-schema

export ENV=local
export DB_HOST=localhost
export DB_NAME=main
export DB_CONNECTOR=mysql+pymysql
export ALLOW_ORIGINS=http://127.0.0.1:8000# pass the allowed origins -> http://localhost:3000,http://localhost:3001
export ALLOW_CREDENTIALS=true
export ALLOW_METHODS=*# pass the allowed methods -> GET,POST,PUT,DELETE
export ALLOW_HEADERS=*# pass the allowed headers -> Content-Type,Authorization
export LOG_LEVEL=DEBUG
# Which local object storage to run against. `minio` selects the deprecated
# stack, kept runnable until the `local:minio` driver is removed. The stack's
# structure (services, driver) lives in oqtopus_cloud/infra.py; STORAGE_DRIVER
# is derived from STORAGE_STACK there, so it is not set here.
export STORAGE_STACK ?= seaweedfs
export DB_USERNAME=admin
export DB_PASSWORD=password
export STORAGE_SEAWEEDFS_BUCKET_NAME=oqtopus-oqtopus-dev
export STORAGE_SEAWEEDFS_USERNAME=devadmin
export STORAGE_SEAWEEDFS_PASSWORD=devadmin123
export STORAGE_SEAWEEDFS_ENDPOINT_URL=http://localhost:8333
export STORAGE_SEAWEEDFS_PUBLIC_ENDPOINT_URL=http://localhost:8333
export STORAGE_LOCAL_MINIO_BUCKET_NAME=oqtopus-oqtopus-dev
export STORAGE_LOCAL_MINIO_USERNAME=minioadmin
export STORAGE_LOCAL_MINIO_PASSWORD=minioadmin
export STORAGE_LOCAL_MINIO_ENDPOINT_URL=http://localhost:9000
# Keep comments off the `export` lines: make would include the space before a
# trailing `#` in the value (`true ` is not `TRUE` for the application).
# flag to control whether users can delete their accounts
export ALLOW_DELETION=true
# list of user fields which can be edited by the user
export EDITABLE_FIELDS=["name", "organization"]
# list of user fields which user can view
export VISIBLE_FIELDS=["id", "email", "name", "organization", "created_at"]
# flag to control whether user login history should be included in GET user API response
export LOGIN_HISTORY_ENABLED=true
export LOCAL_WORKER_SCHEDULING_RATE_S=60
# uvicorn options for `make run-*`, per API (<SCOPE>_<OPTION>). Override on the
# command line or in the environment, e.g. `make run-user USER_API_HOST=127.0.0.1`.
# Any option listed in `uvicorn --help` can be set the same way.
# <SCOPE>_POWERTOOLS_* are handed to POWERTOOLS_* by oqtopus_cloud/local_entry.py.
export USER_API_HOST ?= 0.0.0.0
export USER_API_PORT ?= 8080
export USER_API_RELOAD ?= true
export USER_API_LOG_LEVEL ?= debug
export USER_API_POWERTOOLS_SERVICE_NAME ?= user-api
export USER_API_POWERTOOLS_METRICS_NAMESPACE ?= user-api
export PROVIDER_API_HOST ?= 0.0.0.0
export PROVIDER_API_PORT ?= 8888
export PROVIDER_API_RELOAD ?= true
export PROVIDER_API_LOG_LEVEL ?= debug
export PROVIDER_API_POWERTOOLS_SERVICE_NAME ?= provider-api
export PROVIDER_API_POWERTOOLS_METRICS_NAMESPACE ?= provider-api
export ADMIN_API_HOST ?= 0.0.0.0
export ADMIN_API_PORT ?= 8889
export ADMIN_API_RELOAD ?= true
export ADMIN_API_LOG_LEVEL ?= debug
export ADMIN_API_POWERTOOLS_SERVICE_NAME ?= admin-api
export ADMIN_API_POWERTOOLS_METRICS_NAMESPACE ?= admin-api
export USER_SIGNUP_API_HOST ?= 0.0.0.0
export USER_SIGNUP_API_PORT ?= 8890
export USER_SIGNUP_API_RELOAD ?= true
export USER_SIGNUP_API_LOG_LEVEL ?= debug
export USER_SIGNUP_API_POWERTOOLS_SERVICE_NAME ?= user_signup-api
export USER_SIGNUP_API_POWERTOOLS_METRICS_NAMESPACE ?= user_signup-api

run-user: ## Start the User API
	@uv run oqtopus-cloud-user-api

run-provider: ## Start the Provider API
	@uv run oqtopus-cloud-provider-api

run-admin: ## Start the Admin API
	@uv run oqtopus-cloud-admin-api

run-user_signup: ## Start the user_signup API
	@uv run oqtopus-cloud-user-signup-api

COUNT_PENDING_JOBS_SINCE ?= 10d

run-worker:
	@export COUNT_PENDING_JOBS_SINCE=$(COUNT_PENDING_JOBS_SINCE) && \
	uv run oqtopus-cloud-worker

infra-up: ## Start the DB and storage (STORAGE_STACK=seaweedfs|minio selects the storage stack)
	@uv run oqtopus-cloud-infra start

infra-down: ## Stop the DB and storage only; other containers are left running
	@uv run oqtopus-cloud-infra stop

infra-status: ## Show whether the DB and storage are running (fails only if the state is unknown)
	@# Stopped (exit code 3) is a normal state, not an error. Use
	@# `uv run oqtopus-cloud-infra status` directly to get the exit code.
	@rc=0; uv run oqtopus-cloud-infra status || rc=$$?; [ $$rc -eq 3 ] || exit $$rc

up: infra-up ## Start the DB, storage and otel-collector
	@docker compose up -d otel-collector

seed: ## Seed the local DB with test data (idempotent)
	@uv run python scripts/seed.py

down: infra-down ## Stop and remove all containers of this compose project
	@docker compose down

PRESIGNED_POST_COUNT ?= 100
PRESIGNED_POST_WORKERS ?= 10
PRESIGNED_POST_PAYLOAD_BYTES ?= 4096
PRESIGNED_POST_ROUNDS ?= 3
PRESIGNED_POST_WARMUP_ROUNDS ?= 1
# Label shown in the benchmark results. Empty: the script uses STORAGE_STACK.
PRESIGNED_POST_LABEL ?=
PRESIGNED_POST_OUTPUT_JSON ?= benchmark-results/presigned-storage.json
check-presigned-post: ## Run concurrent presigned POST E2E against the local storage stack
	@uv run python scripts/check_presigned_post.py \
		--count $(PRESIGNED_POST_COUNT) \
		--workers $(PRESIGNED_POST_WORKERS) \
		--payload-bytes $(PRESIGNED_POST_PAYLOAD_BYTES)

benchmark-presigned-post: ## Benchmark presigned POST/GET throughput and latency
	@uv run python scripts/check_presigned_post.py \
		--benchmark \
		$(if $(PRESIGNED_POST_LABEL),--label "$(PRESIGNED_POST_LABEL)") \
		--count $(PRESIGNED_POST_COUNT) \
		--workers $(PRESIGNED_POST_WORKERS) \
		--payload-bytes $(PRESIGNED_POST_PAYLOAD_BYTES) \
		--rounds $(PRESIGNED_POST_ROUNDS) \
		--warmup-rounds $(PRESIGNED_POST_WARMUP_ROUNDS) \
		--output-json $(PRESIGNED_POST_OUTPUT_JSON)

migrate-create: ## Generate a migration from current models. Usage: make migrate-create NAME=<slug>
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make migrate-create NAME=<slug>"; exit 1; \
	fi
	@uv run alembic revision --autogenerate -m "$(NAME)"

migrate-up: ## Apply all pending migrations to the local DB
	@uv run alembic upgrade head

migrate-down: ## Roll back the most recent applied migration
	@uv run alembic downgrade -1

migrate-current: ## Show the currently applied revision
	@uv run alembic current

migrate-history: ## Show the migration history
	@uv run alembic history --verbose

fmt-common: ## Format common code
	@uv run ruff format oqtopus_cloud/common

fmt-user: ## Format user code
	@uv run ruff format oqtopus_cloud/user

fmt-provider: ## Format provider code
	@uv run ruff format oqtopus_cloud/provider

fmt-worker: ## Format worker code
	@uv run ruff format oqtopus_cloud/worker

fmt-admin: ## Format admin code
	@uv run ruff format oqtopus_cloud/admin

fmt-lambda_auth: ## Format lambda_auth code
	@uv run ruff format oqtopus_cloud/lambda_auth

fmt-maintenance: ## Format maintenance code
	@uv run ruff format oqtopus_cloud/maintenance

fmt-user_signup: ## Format user_signup code
	@uv run ruff format oqtopus_cloud/user_signup

fmt-all: fmt-common fmt-user fmt-provider fmt-admin fmt-lambda_auth fmt-maintenance fmt-user_signup fmt-worker ## Format all code

lint-common: ## Run common linters
	@uv run ruff check oqtopus_cloud/common
	@uv run mypy -p oqtopus_cloud.common

lint-user: ## Run user linters
	@uv run mypy -p oqtopus_cloud.user
	@uv run ruff check oqtopus_cloud/user

lint-provider: ## Run provider linters
	@uv run ruff check oqtopus_cloud/provider
	@uv run mypy -p oqtopus_cloud.provider

lint-worker: ## Run worker linters
	@uv run ruff check oqtopus_cloud/worker
	@uv run mypy -p oqtopus_cloud.worker

lint-admin: ## Run admin linters
	@uv run ruff check oqtopus_cloud/admin
	@uv run mypy -p oqtopus_cloud.admin

lint-lambda_auth:
	@uv run ruff check ./oqtopus_cloud/lambda_auth
	@uv run mypy -p oqtopus_cloud.lambda_auth

lint-maintenance:
	@uv run ruff check ./oqtopus_cloud/maintenance
	@uv run mypy -p oqtopus_cloud.maintenance

lint-user_signup: ## Run user_signup linters
	@uv run ruff check oqtopus_cloud/user_signup
	@uv run mypy -p oqtopus_cloud.user_signup

lint-all: lint-common lint-user lint-provider lint-admin lint-lambda_auth lint-maintenance lint-user_signup lint-worker ## Run all linters

test-common: fmt-common lint-common ## Run common tests
	@export POWERTOOLS_METRICS_NAMESPACE=common && \
	export POWERTOOLS_SERVICE_NAME=common && \
	uv run pytest tests/oqtopus_cloud/common/ -vv --cov=oqtopus_cloud/common --cov-report=xml:coverage-common.xml --cov-report=html:htmlcov-common
	@mv .coverage .coverage-common

test-user: fmt-user lint-user ## Run User API tests
	@export POWERTOOLS_METRICS_NAMESPACE=user-api && \
	export POWERTOOLS_SERVICE_NAME=user-api && \
	uv run pytest tests/oqtopus_cloud/user/ -vv --cov=oqtopus_cloud/user --cov-report=xml:coverage-user.xml --cov-report=html:htmlcov-user
	@mv .coverage .coverage-user

test-provider: fmt-provider lint-provider ## Run Provider tests
	@export POWERTOOLS_METRICS_NAMESPACE=provider-api && \
	export POWERTOOLS_SERVICE_NAME=provider-api && \
	uv run pytest tests/oqtopus_cloud/provider/ -vv --cov=oqtopus_cloud/provider --cov-report=xml:coverage-provider.xml --cov-report=html:htmlcov-provider
	@mv .coverage .coverage-provider

test-worker: fmt-worker lint-worker ## Run worker tests
	@export POWERTOOLS_METRICS_NAMESPACE=worker && \
	export POWERTOOLS_SERVICE_NAME=worker && \
	export COUNT_PENDING_JOBS_SINCE=10d && \
	uv run pytest tests/oqtopus_cloud/worker/ -vv --cov=oqtopus_cloud/worker --cov-report=xml:coverage-worker.xml --cov-report=html:htmlcov-worker
	@mv .coverage .coverage-worker

test-admin: fmt-admin lint-admin ## Run admin tests
	@export POWERTOOLS_METRICS_NAMESPACE=admin-api && \
	export POWERTOOLS_SERVICE_NAME=admin-api && \
	uv run pytest tests/oqtopus_cloud/admin/ -vv --cov=oqtopus_cloud/admin --cov-report=xml:coverage-admin.xml --cov-report=html:htmlcov-admin
	@mv .coverage .coverage-admin

test-lambda_auth: fmt-lambda_auth lint-lambda_auth ## Run lambda_auth tests
	  @export POWERTOOLS_METRICS_NAMESPACE=lambda_auth && \
    export POWERTOOLS_SERVICE_NAME=lambda_auth && \
    uv run pytest tests/oqtopus_cloud/lambda_auth/ -vv --cov=oqtopus_cloud/lambda_auth --cov-report=xml:coverage-lambda_auth.xml --cov-report=html:htmlcov-lambda_auth
	  @mv .coverage .coverage-lambda_auth

test-user_signup: fmt-user_signup lint-user_signup ## Run user_signup tests
	@export POWERTOOLS_METRICS_NAMESPACE=user_signup-api && \
	export POWERTOOLS_SERVICE_NAME=user_signup-api && \
	uv run pytest tests/oqtopus_cloud/user_signup/ -vv --cov=oqtopus_cloud/user_signup --cov-report=xml:coverage-user_signup.xml --cov-report=html:htmlcov-user_signup
	@mv .coverage .coverage-user_signup

# Both backends are required for the release compatibility check. The dedicated
# project uses separate ports and disposable data, without starting DB or APIs.
STORAGE_COMPATIBILITY_COMPOSE = docker compose -p oqtopus-storage-compatibility -f tests/storage_compatibility/compose.yaml
test-storage-compatibility: ## Verify the same storage contract on SeaweedFS and MinIO
	@mkdir -p storage-compatibility-results
	@trap '$(STORAGE_COMPATIBILITY_COMPOSE) down --volumes' EXIT; \
	$(STORAGE_COMPATIBILITY_COMPOSE) up -d --wait --wait-timeout 90; \
	$(STORAGE_COMPATIBILITY_COMPOSE) images --format json > storage-compatibility-results/images.json; \
	RUN_STORAGE_COMPATIBILITY=1 uv run pytest tests/storage_compatibility -o addopts= \
		-v --junitxml=storage-compatibility-results/results.xml

test-scripts: ## Run helper script tests
	@uv run ruff check scripts
	@uv run mypy scripts
	@uv run pytest tests/scripts -vv

test-all: fmt-all lint-all ## Run All tests
	@export POWERTOOLS_METRICS_NAMESPACE=all && \
	export POWERTOOLS_SERVICE_NAME=all && \
	uv run pytest tests/oqtopus_cloud -vv --cov=oqtopus_cloud --cov-report=xml:coverage.xml --cov-report=html:htmlcov


help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
