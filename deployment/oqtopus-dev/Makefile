SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help zip-user zip-provider zip-admin zip-lambda_auth zip-user_signup zip-pending-jobs-updater-worker zip-all zip deploy-user deploy-provider deploy-admin deploy-pending-jobs-updater-worker deploy-lambda_auth deploy-user_signup deploy-all deploy test-user test-provider test-admin test-lambda_auth test-user_signup test-all test all-user all-provider all-admin all-lambda_auth all-user_signup all

-include .env
export

OPENAPI_URL ?= "http://localhost:8080"
OPENAPI_DESCRIPTION ?= "Local server url"

upload-openapi-user: ## Generate and Push User API OpenAPI Specification to S3
	@TARGET_DIR=$(shell cd ../../backend/oas/user && pwd) \
	TARGET_NAME="user" \
	$(MAKE) upload-openapi

upload-openapi: ## Generate and Push OpenAPI Specification to S3
	@echo ""
	@echo "▶️ Generating OpenAPI Specification ..."
	@OPENAPI_URL=$(OPENAPI_URL) OPENAPI_DESCRIPTION=$(OPENAPI_DESCRIPTION) envsubst '$$OPENAPI_URL $$OPENAPI_DESCRIPTION' < $(TARGET_DIR)/root.yaml > $(TARGET_DIR)/root_dummy.yaml
	@docker run --rm -v $(TARGET_DIR):/spec redocly/cli bundle /spec/root_dummy.yaml -o /spec/openapi_dummy.yaml
	@rm $(TARGET_DIR)/root_dummy.yaml
	@mv $(TARGET_DIR)/openapi_dummy.yaml ./openapi.yaml
	@echo "✅ Generating Completed"
	@echo ""
	@echo "▶️ Pushing OpenAPI Specification to S3 Bucket ..."
	@aws s3 cp ./openapi.yaml s3://$(OPENAPI_S3_BUCKET)/$(TARGET_NAME).yaml --profile $(PROFILE)
	@rm ./openapi.yaml
	@echo "✅ Pushing Completed"
	@echo ""

zip-user: ## Build User API Lambda Package
	@$(MAKE) zip \
	WORKSPACE=../../backend \
	DEPLOY_PACKAGES_DIR=./deploy-packages \
	APP=oqtopus_cloud/user \
	LIB=oqtopus_cloud/common \
	BIN=./bin/user

zip-provider: ## Build provider API Lambda Package
	@$(MAKE) zip WORKSPACE=../../backend \
	DEPLOY_PACKAGES_DIR=./deploy-packages \
	APP=oqtopus_cloud/provider \
	LIB=oqtopus_cloud/common \
	BIN=./bin/provider

zip-admin: ## Build admin API Lambda Package
	@$(MAKE) zip WORKSPACE=../../backend \
	DEPLOY_PACKAGES_DIR=./deploy-packages \
	APP=oqtopus_cloud/admin \
	LIB=oqtopus_cloud/common \
	BIN=./bin/admin

zip-pending-jobs-updater-worker: ## Build pending-jobs-updater Lambda Package
	@$(MAKE) zip \
	WORKSPACE=../../backend \
	DEPLOY_PACKAGES_DIR=./deploy-packages \
	APP=oqtopus_cloud/worker/pending_jobs_updater \
	LIB=oqtopus_cloud/common \
	BIN=./bin/pending-jobs-updater

zip-lambda_auth: ## Build lambda_auth API Lambda Package
	@$(MAKE) zip WORKSPACE=../../backend \
	DEPLOY_PACKAGES_DIR=./deploy-packages \
	APP=oqtopus_cloud/lambda_auth \
	LIB=oqtopus_cloud/common \
	BIN=./bin/lambda_auth

zip-user_signup: ## Build user_signup API Lambda Package
	@$(MAKE) zip WORKSPACE=../../backend \
	DEPLOY_PACKAGES_DIR=./deploy-packages \
	APP=oqtopus_cloud/user_signup \
	LIB=oqtopus_cloud/common \
	BIN=./bin/user_signup

zip-all: zip-user zip-provider zip-admin zip-lambda_auth zip-user_signup zip-pending-jobs-updater-worker## Build All Lambda Packages

zip:
	@echo "Building ${APP} Lambda Package"
	@mkdir -p ${DEPLOY_PACKAGES_DIR}
	@mkdir -p ${BIN}
	@echo "Project Location: ${WORKSPACE}/${APP}"
	@echo "Library Location: ${DEPLOY_PACKAGES_DIR}"
	@poetry export -f requirements.txt --output requirements.txt
	@docker run --platform linux/x86_64 --user $(id -u):$(id -g) \
  -v ./${DEPLOY_PACKAGES_DIR}:/${DEPLOY_PACKAGES_DIR} \
  -v ./requirements.txt:/requirements.txt \
  python:3.12 /bin/bash -c "\
  curl -fsSL https://astral.sh/uv/install.sh | bash && \
  /root/.local/bin/uv pip install --system --no-cache-dir --requirement /requirements.txt --target /${DEPLOY_PACKAGES_DIR}" --link-mode=copy
	@cd ${DEPLOY_PACKAGES_DIR} && rm -rf __pycache__ && zip -r ../${BIN}/lambda.zip * -q
	@cd ${WORKSPACE} && zip -r ../deployment/$(PROFILE)/${BIN}/lambda.zip ${APP} -q
	@cd ${WORKSPACE} && zip -r ../deployment/$(PROFILE)/${BIN}/lambda.zip ${LIB} -q
	@echo "Lambda Package Created: ${BIN}/lambda.zip"
	@rm -rf ${DEPLOY_PACKAGES_DIR}
	@rm requirements.txt


deploy-user: zip-user ## Deploy User API Lambda Package
	@$(MAKE) deploy \
	FUNCTION_NAME=oqtopus-$(PROFILE)-user-api \
	BIN=./bin/user

deploy-provider: zip-provider	## Deploy Provider API Lambda Package
	@$(MAKE) deploy \
	FUNCTION_NAME=oqtopus-$(PROFILE)-provider-api \
	BIN=./bin/provider

deploy-admin: zip-admin	## Deploy Admin API Lambda Package
	@$(MAKE) deploy \
	FUNCTION_NAME=oqtopus-$(PROFILE)-admin-api \
	BIN=./bin/admin

deploy-lambda_auth: zip-lambda_auth	## Deploy lambda_auth API Lambda Package
	@$(MAKE) deploy \
	FUNCTION_NAME=oqtopus-$(PROFILE)-lambda_auth \
	BIN=./bin/lambda_auth

deploy-user_signup: zip-user_signup	## Deploy user_signup API Lambda Package
	@$(MAKE) deploy \
	FUNCTION_NAME=oqtopus-$(PROFILE)-user_signup-api \
	BIN=./bin/user_signup

deploy-pending-jobs-updater-worker: zip-pending-jobs-updater-worker	## Deploy pending-jobs-updater-worker Lambda Package
	@$(MAKE) deploy \
	FUNCTION_NAME=oqtopus-$(PROFILE)-pending-jobs-updater-worker \
	BIN=./bin/pending-jobs-updater

deploy-all: deploy-user deploy-provider deploy-admin deploy-lambda_auth deploy-user_signup deploy-pending-jobs-updater-worker ## Deploy All Lambda Packages

deploy: generate-tag
	@echo "Deploy ${FUNCTION_NAME} ..."
	@export AWS_PAGER="" && \
	aws lambda update-function-code \
	--function-name ${FUNCTION_NAME} \
	--zip-file fileb://${BIN}/lambda.zip \
	--profile $(PROFILE)
	@echo "Deploy Completed"

generate-tag: ## Tag version
	@GITHUB_SHA=$$(git rev-parse HEAD) && \
	AWS_ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text --profile $(PROFILE)) && \
	AWS_REGION=$$(aws configure get region --profile $(PROFILE)) && \
	echo "$(PROFILE)" && \
	echo "🏷️ Tagging version: $${GITHUB_SHA}" && \
	aws lambda tag-resource \
	--resource arn:aws:lambda:$${AWS_REGION}:$${AWS_ACCOUNT_ID}:function:$${FUNCTION_NAME} \
  --tags github-sha=$${GITHUB_SHA}
	@echo "🏷️ Tagging Completed"


deploy-user-via-actions: zip-user ## Deploy User API Lambda Package
	@$(MAKE) deploy-via-actions \
	FUNCTION_NAME=oqtopus-$(PROFILE)-user-api \
	BIN=./bin/user

deploy-provider-via-actions: zip-provider	## Deploy Provider API Lambda Package
	@$(MAKE) deploy-via-actions \
	FUNCTION_NAME=oqtopus-$(PROFILE)-provider-api \
	BIN=./bin/provider

deploy-admin-via-actions: zip-admin	## Deploy Admin API Lambda Package
	@$(MAKE) deploy-via-actions \
	FUNCTION_NAME=oqtopus-$(PROFILE)-admin-api \
	BIN=./bin/admin

deploy-lambda_auth-via-actions: zip-lambda_auth	## Deploy lambda_auth API Lambda Package
	@$(MAKE) deploy-via-actions \
	FUNCTION_NAME=oqtopus-$(PROFILE)-lambda_auth \
	BIN=./bin/lambda_auth

deploy-user_signup-via-actions: zip-user_signup	## Deploy user_signup API Lambda Package
	@$(MAKE) deploy-via-actions \
	FUNCTION_NAME=oqtopus-$(PROFILE)-user_signup-api \
	BIN=./bin/user_signup

deploy-via-actions: generate-tag-via-actions ## Deploy Lambda Package via Github Actions
	@echo "Deploy ${FUNCTION_NAME} ..."
	@export AWS_PAGER="" && \
	aws lambda update-function-code \
	--function-name ${FUNCTION_NAME} \
	--zip-file fileb://${BIN}/lambda.zip
	@echo "Deploy Completed"

generate-tag-via-actions: ## Tag version via Github Actions
	@echo "🏷️ Tagging version: ${GITHUB_SHA}"
	@aws lambda tag-resource \
	--resource arn:aws:lambda:${AWS_DEFAULT_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME} \
  --tags github-sha=${GITHUB_SHA}
	@echo "🏷️ Tagging Completed"


create-user-admin: ## Create Admin User
	aws cognito-idp admin-create-user \
			--user-pool-id ${USER_COGNITO_USER_POOL_ID} \
			--username ${USER_COGNITO_USER_NAME} \
			--user-attributes Name=email,Value=${USER_COGNITO_USER_EMAIL} \
			--message-action SUPPRESS \
			--profile $(PROFILE)
	aws cognito-idp admin-set-user-password \
			--user-pool-id ${USER_COGNITO_USER_POOL_ID} \
			--username ${USER_COGNITO_USER_NAME} \
			--password ${USER_COGNITO_USER_PASSWORD} \
			--permanent \
			--profile $(PROFILE)

create-provider-admin: ## Create Admin User
	aws cognito-idp admin-create-user \
			--user-pool-id ${PROVIDER_COGNITO_USER_POOL_ID} \
			--username ${PROVIDER_COGNITO_USER_NAME} \
			--user-attributes Name=email,Value=${PROVIDER_COGNITO_USER_EMAIL} \
			--message-action SUPPRESS \
			--profile $(PROFILE)
	aws cognito-idp admin-set-user-password \
			--user-pool-id ${PROVIDER_COGNITO_USER_POOL_ID} \
			--username ${PROVIDER_COGNITO_USER_NAME} \
			--password ${PROVIDER_COGNITO_USER_PASSWORD} \
			--permanent \
			--profile $(PROFILE)

test-user: ## Test User API(connect to the dev environment)
	@$(MAKE) test \
	COGNITO_USER_POOL_ID=$(USER_COGNITO_USER_POOL_ID) \
	COGNITO_CLIENT_ID=$(USER_COGNITO_CLIENT_ID) \
	COGNITO_USER_NAME=$(USER_COGNITO_USER_NAME) \
	COGNITO_USER_PASSWORD=$(USER_COGNITO_USER_PASSWORD) \
	API_URL=$(USER_API_URL) \
	APP=user

test-provider: ## Test Provider API API(connect to the dev environment)
	@$(MAKE) test \
	COGNITO_USER_POOL_ID=$(PROVIDER_COGNITO_USER_POOL_ID) \
	COGNITO_CLIENT_ID=$(PROVIDER_COGNITO_CLIENT_ID) \
	COGNITO_USER_NAME=$(PROVIDER_COGNITO_USER_NAME) \
	COGNITO_USER_PASSWORD=$(PROVIDER_COGNITO_USER_PASSWORD) \
	API_URL=$(PROVIDER_API_URL) \
	APP=provider

test-admin: ## Test Admin API(connect to the dev environment)
	@$(MAKE) test \
	COGNITO_USER_POOL_ID=$(USER_COGNITO_USER_POOL_ID) \
	COGNITO_CLIENT_ID=$(USER_COGNITO_CLIENT_ID) \
	COGNITO_USER_NAME=$(USER_COGNITO_USER_NAME) \
	COGNITO_USER_PASSWORD=$(USER_COGNITO_USER_PASSWORD) \
	API_URL=$(USER_API_URL) \
	APP=admin

test-user_signup: ## Test user_signup API(connect to the dev environment)
	@$(MAKE) test \
	COGNITO_USER_POOL_ID=$(USER_COGNITO_USER_POOL_ID) \
	COGNITO_CLIENT_ID=$(USER_COGNITO_CLIENT_ID) \
	COGNITO_USER_NAME=$(USER_COGNITO_USER_NAME) \
	COGNITO_USER_PASSWORD=$(USER_COGNITO_USER_PASSWORD) \
	API_URL=$(USER_API_URL) \
	APP=user_signup

test-lambda_auth: ## Test lambda_auth API(connect to the dev environment)
	@$(MAKE) test \
	COGNITO_USER_POOL_ID=$(USER_COGNITO_USER_POOL_ID) \
	COGNITO_CLIENT_ID=$(USER_COGNITO_CLIENT_ID) \
	COGNITO_USER_NAME=$(USER_COGNITO_USER_NAME) \
	COGNITO_USER_PASSWORD=$(USER_COGNITO_USER_PASSWORD) \
	API_URL=$(USER_API_URL) \
	APP=lambda_auth

test-all: test-user test-provider test-admin test-lambda_auth test-user_signup ## Test All APIs(connect to the dev environment)

test:
	@cd ../../ && \
	export IdToken=$$( \
	aws cognito-idp admin-initiate-auth \
	--user-pool-id ${COGNITO_USER_POOL_ID} \
	--client-id ${COGNITO_CLIENT_ID} \
	--auth-flow ADMIN_NO_SRP_AUTH \
	--auth-parameters USERNAME=${COGNITO_USER_NAME},PASSWORD=${COGNITO_USER_PASSWORD} \
	--profile $(PROFILE) | jq -r '.AuthenticationResult.IdToken' \
	) && \
	export API_URL=${API_URL} && \
	runn run runnbooks/${APP}/**/*.yaml --verbose

curl-user:
	@$(MAKE) curl-test \
	COGNITO_USER_POOL_ID=$(USER_COGNITO_USER_POOL_ID) \
	COGNITO_CLIENT_ID=$(USER_COGNITO_CLIENT_ID) \
	COGNITO_USER_NAME=$(USER_COGNITO_USER_NAME) \
	COGNITO_USER_PASSWORD=$(USER_COGNITO_USER_PASSWORD) \
	API_URL=$(USER_API_URL) \

curl-test:
	@export IdToken=$$( \
	aws cognito-idp admin-initiate-auth \
	--user-pool-id ${COGNITO_USER_POOL_ID} \
	--client-id ${COGNITO_CLIENT_ID} \
	--auth-flow ADMIN_NO_SRP_AUTH \
	--auth-parameters USERNAME=${COGNITO_USER_NAME},PASSWORD=${COGNITO_USER_PASSWORD} \
	--profile $(PROFILE) | jq -r '.AuthenticationResult.IdToken' \
	) && \
	export API_URL=${API_URL} && \
	curl -X GET "${API_URL}/v1/tasks/sampling/7af020f6-2e38-4d70-8cf0-4349650ea08c" \
	-H "Authorization: Bearer $${IdToken}"


all-user: ## Deploy User API Lambda Package and Test
	@$(MAKE) deploy-user
	@$(MAKE) test-user

all-provider:	## Deploy Provider API Lambda Package and Test
	@$(MAKE) deploy-provider
	@$(MAKE) test-provider

all-admin:	## Deploy Admin API Lambda Package and Test
	@$(MAKE) deploy-admin
	@$(MAKE) test-admin

all-lambda_auth:	## Deploy lambda_auth API Lambda Package and Test
	@$(MAKE) deploy-lambda_auth
	@$(MAKE) test-lambda_auth

all-user_signup:	## Deploy user_signup API Lambda Package and Test
	@$(MAKE) deploy-user_signup
	@$(MAKE) test-user_signup

all:all-user all-provider all-admin all-lambda_auth all-user_signup ## Deploy All Lambda Packages and Test

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
