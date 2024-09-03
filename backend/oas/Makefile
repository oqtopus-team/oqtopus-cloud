SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: lint-user lint-provider lint-all generate-user generate-provider generate-all help

lint-user: ## Lint user openapi.yaml
	@docker run --rm -v $(PWD):/spec redocly/cli lint user/openapi.yaml

lint-provider: ## Lint provider openapi.yaml
	@docker run --rm -v $(PWD):/spec redocly/cli lint provider/openapi.yaml

lint-all: lint-user lint-provider ## Lint user and provider

generate-user: ## Generate user openapi.yaml
	@docker pull redocly/cli
	@docker run --rm -v $(PWD):/spec redocly/cli bundle /spec/user/root.yaml -o /spec/user/openapi.yaml
	@$(MAKE) lint-user

generate-provider: ## Generate provider openapi.yaml
	@docker pull redocly/cli
	@docker run --rm -v $(PWD):/spec redocly/cli bundle /spec/provider/root.yaml -o /spec/provider/openapi.yaml
	@$(MAKE) lint-provider

generate-all: generate-user generate-provider ## Generate user and provider openapi.yaml

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
