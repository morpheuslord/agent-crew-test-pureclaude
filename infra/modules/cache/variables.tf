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
  description = "VPC of the cache."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for the cache subnet group."

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "Use subnets in at least two zones for the replica."
  }
}

variable "engine" {
  type        = string
  description = "Cache engine: valkey or redis (Redis OSS)."
  default     = "valkey"

  validation {
    condition     = contains(["valkey", "redis"], var.engine)
    error_message = "engine must be valkey or redis."
  }
}

variable "engine_version" {
  type        = string
  description = "Engine version (Valkey 7.2+/8.x or Redis OSS 7.x)."
  default     = "8.0"

  validation {
    condition     = can(regex("^[78]\\.[0-9]+$", var.engine_version))
    error_message = "engine_version must be a 7.x or 8.x version."
  }
}

variable "node_type" {
  type        = string
  description = "Cache node type."
  default     = "cache.t4g.micro"

  validation {
    condition     = startswith(var.node_type, "cache.")
    error_message = "node_type must be an ElastiCache node type such as cache.t4g.micro."
  }
}

variable "replicas" {
  type        = number
  description = "Number of cache nodes including the primary (2 or more enables automatic failover)."
  default     = 2

  validation {
    condition     = var.replicas >= 1 && var.replicas <= 6
    error_message = "replicas must be between 1 and 6."
  }
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key for data at rest and the auth token secret."
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
