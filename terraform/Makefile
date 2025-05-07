SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help fmt, lint, scan, docs

ifeq ($(AQUA_ROOT_DIR),)
ifeq ($(XDG_DATA_HOME),)
    AQUA_ROOT_DIR := $(HOME)/.local/share/aquaproj-aqua
else
    AQUA_ROOT_DIR := $(XDG_DATA_HOME)/aquaproj-aqua
endif
endif

fmt: ## Run terraform fmt
	@terraform fmt -recursive

lint: ## Run tflint
	@tflint --init
	@tflint --recursive --config $(PWD)/.tflint.hcl --fix

lint-ci: ## Run tflint in CI mode
	@tflint --init
	@tflint --recursive --config $(PWD)/.tflint.hcl --fix --format json > tflint_report.json

scan: ## Run trivy
	@trivy config .


help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

generate-env: ## Generate environment configuration
	@echo "Generating environment configuration..."
	@cp ./example/example-infrastructure.tfbackend.txt ./infrastructure/oqtopus-dev/oqtopus-dev.tfbackend
	@cp ./example/example-infrastructure.tfvars.txt ./infrastructure/oqtopus-dev/terraform.tfvars
	@cp ./example/example-service.tfbackend.txt ./service/oqtopus-dev/oqtopus-dev.tfbackend
	@cp ./example/example-service.tfvars.txt ./service/oqtopus-dev/terraform.tfvars
	@echo "Environment configuration generated."
