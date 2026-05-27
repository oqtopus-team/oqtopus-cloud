SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: lint-user lint-provider lint-admin lint-admin lint-user_signup lint-all generate-user generate-provider generate-admin generate-admin generate-user_signup generate-all help

lint-user: ## Lint user openapi.yaml
	@docker run --rm -v $(PWD):/spec redocly/cli lint user/openapi.yaml

lint-provider: ## Lint provider openapi.yaml
	@docker run --rm -v $(PWD):/spec redocly/cli lint provider/openapi.yaml

lint-admin: ## Lint admin openapi.yaml
	@docker run --rm -v $(PWD):/spec redocly/cli lint admin/openapi.yaml

lint-user_signup: ## Lint user_signup openapi.yaml
	@docker run --rm -v $(PWD):/spec redocly/cli lint user_signup/openapi.yaml

lint-all: lint-user lint-provider lint-admin lint-user_signup ## Lint user, provider, and admin

# Substitute ${API_SERVER_URL} / ${API_SERVER_DESCRIPTION} placeholders in the
# bundled openapi.yaml. Callers can override per-API via the *_API_SERVER_URL
# / *_API_SERVER_DESCRIPTION env vars; defaults preserve previous behavior.
# Args: $(1)=env-var prefix (USER/PROVIDER/ADMIN/USER_SIGNUP)
#       $(2)=default URL  $(3)=spec directory
define substitute-servers
	@url="$${$(1)_API_SERVER_URL:-$(2)}"; \
	 desc="$${$(1)_API_SERVER_DESCRIPTION:-Local server url}"; \
	 sed -e 's|$${API_SERVER_URL}|'"$$url"'|g' \
	     -e 's|$${API_SERVER_DESCRIPTION}|'"$$desc"'|g' \
	     $(3)/openapi.yaml > $(3)/openapi.yaml.tmp \
	 && mv $(3)/openapi.yaml.tmp $(3)/openapi.yaml
endef

generate-user: ## Generate user openapi.yaml
	@docker pull redocly/cli
	@docker run --rm -v $(PWD):/spec redocly/cli bundle /spec/user/root.yaml -o /spec/user/openapi.yaml
	$(call substitute-servers,USER,http://localhost:8080,user)
	@$(MAKE) lint-user

generate-provider: ## Generate provider openapi.yaml
	@docker pull redocly/cli
	@docker run --rm -v $(PWD):/spec redocly/cli bundle /spec/provider/root.yaml -o /spec/provider/openapi.yaml
	$(call substitute-servers,PROVIDER,http://localhost:8888,provider)
	@$(MAKE) lint-provider

generate-admin: ## Generate admin openapi.yaml
	@docker pull redocly/cli
	@docker run --rm -v $(PWD):/spec redocly/cli bundle /spec/admin/root.yaml -o /spec/admin/openapi.yaml
	$(call substitute-servers,ADMIN,http://localhost:8080,admin)
	@$(MAKE) lint-admin

generate-user_signup: ## Generate user_signup openapi.yaml
	@docker pull redocly/cli
	@docker run --rm -v $(PWD):/spec redocly/cli bundle /spec/user_signup/root.yaml -o /spec/user_signup/openapi.yaml
	$(call substitute-servers,USER_SIGNUP,http://localhost:8080,user_signup)
	@$(MAKE) lint-user_signup

generate-all: generate-user generate-provider generate-admin generate-user_signup ## Generate user, provider, admin openapi.yaml

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
