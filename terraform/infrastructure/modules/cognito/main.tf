/**
*
* # Cognito Module
*
* ## Description
*
* This module creates a Cognito User Pool and User Pool Client.
*
* ## Usage
*
* ```hcl
* module "user_cognito" {
*   source = "./modules/cognito"
*   product = "oqtopus"
*   org = "example"
*   env = "dev"
*   identifier = "user"
* }
* ```
*
*/

resource "aws_cognito_user_pool" "this" {
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = "1"
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = "false"
  }

  # deletion_protection = "ACTIVE"

  device_configuration {
    challenge_required_on_new_device      = "true"
    device_only_remembered_on_user_prompt = "true"
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # mfa_configuration = "ON"
  name = "${var.product}-${var.org}-${var.env}-${var.identifier}"

  password_policy {
    minimum_length                   = "12"
    require_lowercase                = "true"
    require_numbers                  = "true"
    require_symbols                  = "true"
    require_uppercase                = "true"
    temporary_password_validity_days = "7"
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = "false"
    mutable                  = "true"
    name                     = "email"
    required                 = "true"

    string_attribute_constraints {
      max_length = "2048"
      min_length = "0"
    }
  }

  # software_token_mfa_configuration {
  #   enabled = "true"
  # }

  username_configuration {
    case_sensitive = "false"
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }
}

resource "aws_cognito_user_pool_client" "this" {
  access_token_validity                         = "60"
  allowed_oauth_flows                           = ["code"]
  allowed_oauth_flows_user_pool_client          = "true"
  allowed_oauth_scopes                          = ["email", "openid"]
  auth_session_validity                         = "3"
  callback_urls                                 = ["https://amazon.com"]
  enable_propagate_additional_user_context_data = "false"
  enable_token_revocation                       = "true"
  explicit_auth_flows = [
    # 認証フローの指定
    "ADMIN_NO_SRP_AUTH"
  ]
  id_token_validity             = "60"
  name                          = "${var.product}-${var.org}-${var.env}-${var.identifier}"
  prevent_user_existence_errors = "ENABLED"
  read_attributes               = ["address", "birthdate", "email", "email_verified", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "phone_number_verified", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo"]
  refresh_token_validity        = "30"
  supported_identity_providers  = ["COGNITO"]

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  user_pool_id     = aws_cognito_user_pool.this.id
  write_attributes = ["address", "birthdate", "email", "family_name", "gender", "given_name", "locale", "middle_name", "name", "nickname", "phone_number", "picture", "preferred_username", "profile", "updated_at", "website", "zoneinfo"]
}
