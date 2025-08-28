SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: help init plan apply

ifeq ($(AQUA_ROOT_DIR),)
ifeq ($(XDG_DATA_HOME),)
    AQUA_ROOT_DIR := $(HOME)/.local/share/aquaproj-aqua
else
    AQUA_ROOT_DIR := $(XDG_DATA_HOME)/aquaproj-aqua
endif
endif

init: ## Run terraform init
	@terraform init -backend-config=oqtopus-prod.tfbackend

init-standby: ## Run terraform init for standby
	@terraform init -backend-config=oqtopus-prod-standby.tfbackend

lint: ## Run tflint
	@tflint --init
	@tflint --recursive --config $(PWD)/.tflint.hcl --fix

scan: ## Run trivy
	@trivy config .

plan: ## Run terraform plan
	@terraform plan > diffs.ansi

plan-standby: ## Run terraform plan for standby
	@terraform plan -var-file=terraform-standby.tfvars > diffs.ansi

plan-standby-db: ## Run terraform plan for standby db
	@terraform plan -var-file=terraform-standby.tfvars -target=module.db > diffs.ansi

apply: ## Run terraform apply
	@terraform apply

apply-standby: ## Run terraform apply for standby
	@terraform apply -var-file=terraform-standby.tfvars

apply-standby-db: ## Run terraform apply for standby db
	@terraform apply -var-file=terraform-standby.tfvars -target=module.db

destroy-standby-db: ## Run terraform destroy for standby db
	@terraform destroy -var-file=terraform-standby.tfvars -target=module.db

plan-destroy-standby-db: ## Run terraform plan for destroy standby db
	@terraform plan -destroy -var-file=terraform-standby.tfvars -target=module.db > diffs.ansi

standby-init: ## Run terraform init for standby
	@terraform init -backend-config=oqtopus-prod-standby.tfbackend

standby-plan: ## Run terraform plan for standby
	@terraform plan -var-file=terraform.tfvars.standby > diffs.ansi

standby-apply: ## Run terraform apply for standby
	@terraform apply -var-file=terraform.tfvars.standby


help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
