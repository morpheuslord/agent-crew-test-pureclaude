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
  description = "VPC of the database."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets in at least two zones for the DB subnet group."

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "RDS needs subnets in at least two availability zones."
  }
}

variable "engine_version" {
  type        = string
  description = "PostgreSQL 16 engine version."
  default     = "16"

  validation {
    condition     = can(regex("^16(\\.[0-9]+)?$", var.engine_version))
    error_message = "engine_version must be PostgreSQL 16 (e.g. 16 or 16.4)."
  }
}

variable "instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.small"

  validation {
    condition     = startswith(var.instance_class, "db.")
    error_message = "instance_class must be an RDS instance class such as db.t4g.small."
  }
}

variable "allocated_storage_gb" {
  type        = number
  description = "Initial storage in GiB."
  default     = 20

  validation {
    condition     = var.allocated_storage_gb >= 20 && var.allocated_storage_gb <= 1000
    error_message = "allocated_storage_gb must be between 20 and 1000."
  }
}

variable "max_allocated_storage_gb" {
  type        = number
  description = "Storage autoscaling ceiling in GiB."
  default     = 100

  validation {
    condition     = var.max_allocated_storage_gb >= var.allocated_storage_gb
    error_message = "max_allocated_storage_gb must not be smaller than allocated_storage_gb."
  }
}

variable "database_name" {
  type        = string
  description = "Name of the application database."
  default     = "taskboard"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,62}$", var.database_name))
    error_message = "database_name must be a lowercase PostgreSQL identifier."
  }
}

variable "master_username" {
  type        = string
  description = "Master user name; its password is generated and stored by RDS in Secrets Manager."
  default     = "taskboard"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,15}$", var.master_username)) && !contains(["admin", "postgres", "rdsadmin"], var.master_username)
    error_message = "master_username must be a lowercase identifier of up to 16 characters and not a reserved name."
  }
}

variable "multi_az" {
  type        = bool
  description = "Run a standby in a second zone."
  default     = true
}

variable "backup_retention_days" {
  type        = number
  description = "Days of automated backups."
  default     = 14

  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 7 and 35."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "Protect the database from deletion."
  default     = true
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key for storage, Performance Insights and the master user secret."
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
