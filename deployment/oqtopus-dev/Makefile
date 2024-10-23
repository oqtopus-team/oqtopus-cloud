SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help zip-user zip-provider zip-all zip deploy-user deploy-provider deploy-all deploy test-user test-provider test-all test all-user all-provider all

include .env
export


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

zip-all: zip-user zip-provider ## Build All Lambda Packages

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
  /root/.cargo/bin/uv pip install --system --no-cache-dir --requirement /requirements.txt --target /${DEPLOY_PACKAGES_DIR}"
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

deploy-all: deploy-user deploy-provider ## Deploy All Lambda Packages


deploy:
	@echo "Deploy ${FUNCTION_NAME} ..."
	@export AWS_PAGER="" && \
	aws lambda update-function-code \
	--function-name ${FUNCTION_NAME} \
	--zip-file fileb://${BIN}/lambda.zip \
	--profile $(PROFILE)
	@echo "Deploy Completed"

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

test-all: test-user test-provider ## Test All APIs(connect to the dev environment)

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

all:all-user all-provider ## Deploy All Lambda Packages and Test

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
