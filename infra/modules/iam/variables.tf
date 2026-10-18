variable "name" {
  type        = string
  description = "Name prefix of the roles; also the prefix of the log groups (/<name>/ui, /<name>/api)."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.name))
    error_message = "name must be 3-31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "repository_arns" {
  type        = map(string)
  description = "ECR repository ARNs keyed by service (api, ui)."

  validation {
    condition     = contains(keys(var.repository_arns), "api") && contains(keys(var.repository_arns), "ui")
    error_message = "repository_arns needs entries for api and ui."
  }
}

variable "ui_parameter_arns" {
  type        = list(string)
  description = "SSM parameters the UI instances may read."
}

variable "api_parameter_arns" {
  type        = list(string)
  description = "SSM parameters the API instances may read."
}

variable "api_secret_arns" {
  type        = list(string)
  description = "Secrets Manager secrets the API instances may read (database credentials, cache token)."
}

variable "attachments_bucket_arn" {
  type        = string
  description = "Attachments bucket the API instances read and write."
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key protecting parameters, secrets, attachments and logs."
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
