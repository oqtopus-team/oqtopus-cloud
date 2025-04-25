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
	@echo -e '# infrastructure/oqtopus-dev.tfbackend\nbucket         = "tfstate.oqtopus-oqtopus-dev"\nkey            = "infrastructure.tfstate"\nencrypt        = true\nprofile        = "oqtopus-dev"\nregion         = "ap-northeast-1"\ndynamodb_table = "terraform-lock"' > infrastructure/oqtopus-dev/oqtopus-dev.tfbackend
	@echo "[infrastructure] tfbackend configuration generated."

	@echo -e '# infrastructure/terraform.tfvars\nproduct="oqtopus"\norg="oqtopus"\nenv="dev"\nregion = "ap-northeast-1"' > infrastructure/oqtopus-dev/terraform.tfvars
	@echo "[infrastructure] tfvars configuration generated."

	@echo -e '# service/oqtopus-dev.tfbackend\nbucket         = "tfstate.oqtopus-oqtopus-dev"\nkey            = "service.tfstate"\nencrypt        = true\nprofile        = "oqtopus-dev"\nregion         = "ap-northeast-1"\ndynamodb_table = "terraform-lock"' > service/oqtopus-dev/oqtopus-dev.tfbackend
	@echo "[service] tfbackend configuration generated."

	@echo -e '# service/terraform.tfvars\nproduct          = "oqtopus"\norg              = "oqtopus"\nenv              = "dev"\nregion           = "ap-northeast-1"\nstate_bucket     = "tfstate.oqtopus-oqtopus-dev"\nremote_state_key = "infrastructure.tfstate"\nprofile          = "oqtopus-dev"\n\nrepository       = "oqtopus-cloud"\ngithub_user      = "oqtopus-team"\nbranch           = "develop"\naws_account_id   = ""' > service/oqtopus-dev/terraform.tfvars
	@echo "[service] tfvars configuration generated."
