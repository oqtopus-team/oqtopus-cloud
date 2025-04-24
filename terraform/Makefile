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
	@cat <<EOF > infrastructure/oqtopus-dev/oqtopus-dev.tfbackend
# infrastructure/oqtopus-dev.tfbackend
bucket         = "tfstate.oqtopus-oqtopus-dev"
key            = "infrastructure.tfstate"
encrypt        = true
profile        = "oqtopus-dev"
region         = "ap-northeast-1"
dynamodb_table = "terraform-lock"
EOF
	@echo "[infrastructure] tfbackend configuration generated."
	@cd infrastructure/oqtopus-dev
	@terraform init -backend-config=oqtopus-dev.tfbackend
	@cd ../..

	@cat <<EOF > infrastructure/oqtopus-dev/terraform.tfvars
# infrastructure/terraform.tfvars
product="oqtopus"
org="oqtopus"
env="dev"
region = "ap-northeast-1"
EOF
	@echo "[infrastructure] tfvars configuration generated."

	@cat <<EOF > service/oqtopus-dev/oqtopus-dev.tfbackend
# service/oqtopus-dev.tfbackend
bucket         = "tfstate.oqtopus-oqtopus-dev"
key            = "service.tfstate"
encrypt        = true
profile        = "oqtopus-dev"
region         = "ap-northeast-1"
dynamodb_table = "terraform-lock"
EOF
	@echo "[service] tfbackend configuration generated."
	@cd service/oqtopus-dev
	@terraform init -backend-config=oqtopus-dev.tfbackend
	@cd ../..

	@cat <<EOF > service/oqtopus-dev/terraform.tfvars
# service/terraform.tfvars
product          = "oqtopus"
org              = "oqtopus"
env              = "dev"
region           = "ap-northeast-1"
state_bucket     = "tfstate.oqtopus-oqtopus-dev"
remote_state_key = "infrastructure.tfstate"
profile          = "oqtopus-dev"

repository       = "oqtopus-cloud"
github_user      = "oqtopus-team"
branch           = "develop"
aws_account_id   = "Write AWS Account ID here"
EOF
	@echo "[service] tfvars configuration generated."
