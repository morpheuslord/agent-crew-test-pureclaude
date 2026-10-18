variable "name" {
  type        = string
  description = "Name prefix for every resource."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.name))
    error_message = "name must be 3-31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key for attachment encryption (SSE-KMS)."
}

variable "noncurrent_version_days" {
  type        = number
  description = "Days to keep previous versions of overwritten or deleted attachments."
  default     = 30

  validation {
    condition     = var.noncurrent_version_days >= 1 && var.noncurrent_version_days <= 365
    error_message = "noncurrent_version_days must be between 1 and 365."
  }
}

variable "force_destroy" {
  type        = bool
  description = "Allow deleting the buckets while they contain objects (only for throwaway environments)."
  default     = false
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
