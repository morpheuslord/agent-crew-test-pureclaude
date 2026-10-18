# Generated secrets shared by the UI and API. They are ephemeral and written with write-only
# arguments, so their values never appear in plan output or in Terraform state.
ephemeral "random_password" "service_token" {
  length  = 64
  special = false
}

ephemeral "random_password" "ui_secret" {
  length  = 64
  special = false
}

resource "aws_ssm_parameter" "service_token" {
  name             = "/${local.name}/service-token"
  description      = "Shared secret the UI server sends to the API in X-Service-Token"
  type             = "SecureString"
  key_id           = aws_kms_key.main.arn
  value_wo         = ephemeral.random_password.service_token.result
  value_wo_version = var.secret_version
}

resource "aws_ssm_parameter" "ui_secret" {
  name             = "/${local.name}/ui-secret"
  description      = "UI server secret for CSRF tokens and signed cookies"
  type             = "SecureString"
  key_id           = aws_kms_key.main.arn
  value_wo         = ephemeral.random_password.ui_secret.result
  value_wo_version = var.secret_version
}
