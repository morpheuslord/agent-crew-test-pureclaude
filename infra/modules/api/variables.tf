variable "name" {
  type        = string
  description = "Name prefix for every resource."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.name))
    error_message = "name must be 3-31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "vpc_id" {
  type        = string
  description = "VPC of the instances."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets; instances are spread across them."

  validation {
    condition     = length(var.private_subnet_ids) >= 1
    error_message = "At least one private subnet is required."
  }
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type of the API servers."
  default     = "t3.small"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]*\\.[a-z0-9]+$", var.instance_type))
    error_message = "instance_type must look like an EC2 instance type, e.g. t3.small."
  }
}

variable "instance_count" {
  type        = number
  description = "Number of API instances."
  default     = 2

  validation {
    condition     = var.instance_count >= 1 && var.instance_count <= 10
    error_message = "instance_count must be between 1 and 10."
  }
}

variable "ami_ssm_parameter" {
  type        = string
  description = "Public SSM parameter holding the Amazon Linux 2023 AMI ID."
  default     = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

variable "instance_profile_name" {
  type        = string
  description = "Instance profile granting ECR pull, secret read, S3 attachment access and log write."
}

variable "container_port" {
  type        = number
  description = "Port the API container listens on."
  default     = 8000

  validation {
    condition     = var.container_port > 1024 && var.container_port < 65536
    error_message = "container_port must be an unprivileged port."
  }
}

variable "image_repository_url" {
  type        = string
  description = "ECR repository URL of the API image."
}

variable "image_tag" {
  type        = string
  description = "Immutable image tag to run, normally the git commit SHA."

  validation {
    condition     = can(regex("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.image_tag)) && var.image_tag != "latest"
    error_message = "image_tag must be a valid, immutable Docker tag (not \"latest\")."
  }
}

variable "public_ui_url" {
  type        = string
  description = "Public HTTPS URL of the UI, used in password reset links."

  validation {
    condition     = can(regex("^https://", var.public_ui_url))
    error_message = "public_ui_url must be an https URL."
  }
}

variable "service_token_parameter" {
  type        = string
  description = "Name of the SecureString SSM parameter with the UI-to-API service token."
}

variable "database" {
  type = object({
    host       = string
    port       = number
    name       = string
    secret_arn = string
  })
  description = "PostgreSQL endpoint and the Secrets Manager secret (RDS-managed) with its credentials."
}

variable "cache" {
  type = object({
    host       = string
    port       = number
    secret_arn = string
  })
  description = "Valkey/Redis primary endpoint (TLS) and the secret holding its auth token."
}

variable "attachments_bucket" {
  type        = string
  description = "S3 bucket for attachments."
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key for EBS volumes and the log group."
}

variable "log_retention_days" {
  type        = number
  description = "Retention of the container log group."
  default     = 30

  validation {
    condition     = contains([7, 14, 30, 60, 90, 120, 150, 180, 365], var.log_retention_days)
    error_message = "log_retention_days must be a CloudWatch Logs retention value up to 365."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
