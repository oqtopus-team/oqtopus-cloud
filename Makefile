SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: setup-aqua doctor copy docs run terraform-docs generate-oas help

ifeq ($(AQUA_ROOT_DIR),)
ifeq ($(XDG_DATA_HOME),)
    AQUA_ROOT_DIR := $(HOME)/.local/share/aquaproj-aqua
else
    AQUA_ROOT_DIR := $(XDG_DATA_HOME)/aquaproj-aqua
endif
endif

PATH := $(AQUA_ROOT_DIR)/bin:$(PATH)

setup-aqua: ## Setup Aqua
	@bash scripts/setup_aqua.sh
	@aqua i

doctor: ## Check the environment
	@printf "Checking the environment...\n"
	@printf "\033[0;34mAqua version:\033[0m %s\n" "$$(aqua --version)"
	@printf "\033[0;34mPython version:\033[0m %s\n" "$$(python --version)"
	@printf "\033[0;34mPoetry version:\033[0m %s\n" "$$(poetry --version)"
	@printf "\033[0;34mDocker version:\033[0m %s\n" "$$(docker --version)"

copy: generate-oas terraform-docs
	@cp ./backend/oas/user/openapi.yaml ./docs/oas/user/openapi.yaml
	@cp ./backend/oas/provider/openapi.yaml ./docs/oas/provider/openapi.yaml
	@cp ./terraform/infrastructure/modules/cognito/README.md ./docs/terraform_modules/cognito/README.md
	@cp ./terraform/infrastructure/modules/db/README.md ./docs/terraform_modules/db/README.md
	@cp ./terraform/infrastructure/modules/management/README.md ./docs/terraform_modules/management/README.md
	@cp ./terraform/infrastructure/modules/network/README.md ./docs/terraform_modules/network/README.md
	@cp ./terraform/infrastructure/modules/security-group/README.md ./docs/terraform_modules/security-group/README.md
	@cp ./terraform/service/modules/api-server/README.md ./docs/terraform_modules/api-server/README.md
	@cp ./terraform/service/modules/vpc-endpoint/README.md ./docs/terraform_modules/vpc-endpoint/README.md
	@cp .github/CONTRIBUTING.md ./docs/en/CONTRIBUTING.md
	@cp .github/CODE_OF_CONDUCT.md ./docs/en/CODE_OF_CONDUCT.md
	@cp .github/SECURITY.md ./docs/en/SECURITY.md
	@cp ./docs/README.md ./docs/en/index.md
	@cp ./docs/README.ja.md ./docs/ja/index.md

docs: copy ## Build MkDocs
	@poetry run mkdocs build

run: copy ## Run MkDocs
	@poetry run mkdocs serve

terraform-docs: ## Generate Terraform Docs
	@$(MAKE) -C terraform/service docs
	@$(MAKE) -C terraform/infrastructure docs

tbls-docs: ## Generate DB Schema Docs
	@tbls doc -c .tbls.yml -f

generate-oas: ## Generate OpenAPI Specifcation
	@cd backend/oas && $(MAKE) generate-all

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
