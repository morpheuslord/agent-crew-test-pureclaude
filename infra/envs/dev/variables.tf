variable "region" {
  type        = string
  description = "AWS region of the environment."

  validation {
    condition     = can(regex("^[a-z]{2}(-gov)?-[a-z]+-[0-9]$", var.region))
    error_message = "region must be an AWS region name such as eu-west-1."
  }
}

variable "environment" {
  type        = string
  description = "Environment name, used in resource names and tags."
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,9}$", var.environment))
    error_message = "environment must be 2-10 lowercase letters or digits."
  }
}

variable "availability_zones" {
  type        = list(string)
  description = "Two or more availability zones in the region."

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two availability zones are required."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block of the VPC."
  default     = "10.40.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "public_url" {
  type        = string
  description = "HTTPS URL users open (the DNS name pointing at the load balancer)."

  validation {
    condition     = can(regex("^https://[a-z0-9.-]+$", var.public_url))
    error_message = "public_url must be https://<host> without a path."
  }
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate covering the public_url host."

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:acm:[a-z0-9-]+:[0-9]{12}:certificate/", var.certificate_arn))
    error_message = "certificate_arn must be an ACM certificate ARN."
  }
}

variable "allowed_client_cidrs" {
  type        = list(string)
  description = "Client ranges allowed to reach the load balancer, e.g. office and VPN egress ranges."

  validation {
    condition     = length(var.allowed_client_cidrs) > 0 && alltrue([for cidr in var.allowed_client_cidrs : can(cidrnetmask(cidr))])
    error_message = "allowed_client_cidrs must be a non-empty list of IPv4 CIDR blocks."
  }
}

variable "image_tag" {
  type        = string
  description = "Immutable image tag (git SHA) of both images to deploy."

  validation {
    condition     = can(regex("^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.image_tag)) && var.image_tag != "latest"
    error_message = "image_tag must be a valid, immutable Docker tag (not \"latest\")."
  }
}

variable "ui_instance_count" {
  type        = number
  description = "Number of UI instances."
  default     = 2

  validation {
    condition     = var.ui_instance_count >= 1 && var.ui_instance_count <= 10
    error_message = "ui_instance_count must be between 1 and 10."
  }
}

variable "api_instance_count" {
  type        = number
  description = "Number of API instances."
  default     = 2

  validation {
    condition     = var.api_instance_count >= 1 && var.api_instance_count <= 10
    error_message = "api_instance_count must be between 1 and 10."
  }
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type of the UI and API instances."
  default     = "t3.small"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]*\\.[a-z0-9]+$", var.instance_type))
    error_message = "instance_type must look like an EC2 instance type, e.g. t3.small."
  }
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class."
  default     = "db.t4g.small"

  validation {
    condition     = startswith(var.db_instance_class, "db.")
    error_message = "db_instance_class must be an RDS instance class."
  }
}

variable "db_multi_az" {
  type        = bool
  description = "Run the database with a standby in a second zone."
  default     = false
}

variable "cache_node_type" {
  type        = string
  description = "ElastiCache node type."
  default     = "cache.t4g.micro"

  validation {
    condition     = startswith(var.cache_node_type, "cache.")
    error_message = "cache_node_type must be an ElastiCache node type."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "Protect the load balancer and database from deletion."
  default     = true
}

variable "secret_version" {
  type        = number
  description = "Increase to rotate the generated service token and UI secret on the next apply."
  default     = 1

  validation {
    condition     = var.secret_version >= 1 && floor(var.secret_version) == var.secret_version
    error_message = "secret_version must be a positive whole number."
  }
}
