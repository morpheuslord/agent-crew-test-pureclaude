variable "name" {
  type        = string
  description = "Name prefix of the repositories."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.name))
    error_message = "name must be 3-31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key for image encryption."
}

variable "keep_images" {
  type        = number
  description = "How many images to keep per repository."
  default     = 30

  validation {
    condition     = var.keep_images >= 5 && var.keep_images <= 1000
    error_message = "keep_images must be between 5 and 1000."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
