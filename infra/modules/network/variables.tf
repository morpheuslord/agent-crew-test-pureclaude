variable "name" {
  type        = string
  description = "Name prefix for every resource, e.g. taskboard-dev."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.name))
    error_message = "name must be 3-31 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "vpc_cidr" {
  type        = string
  description = "IPv4 CIDR block of the VPC."

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability zones to spread subnets across (at least two)."

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two availability zones are required."
  }
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "One public subnet CIDR per availability zone (load balancer and NAT only)."

  validation {
    condition     = alltrue([for cidr in var.public_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "Every public subnet CIDR must be a valid IPv4 CIDR block."
  }

  validation {
    condition     = length(var.public_subnet_cidrs) == length(var.availability_zones)
    error_message = "Give exactly one public subnet CIDR per availability zone."
  }
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "One private subnet CIDR per availability zone (instances, database, cache)."

  validation {
    condition     = alltrue([for cidr in var.private_subnet_cidrs : can(cidrnetmask(cidr))])
    error_message = "Every private subnet CIDR must be a valid IPv4 CIDR block."
  }

  validation {
    condition     = length(var.private_subnet_cidrs) == length(var.availability_zones)
    error_message = "Give exactly one private subnet CIDR per availability zone."
  }
}

variable "single_nat_gateway" {
  type        = bool
  description = "Use one NAT gateway for all private subnets (cheaper) instead of one per zone."
  default     = true
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key used to encrypt the VPC flow log group."

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:kms:", var.kms_key_arn))
    error_message = "kms_key_arn must be a KMS key ARN."
  }
}

variable "flow_log_retention_days" {
  type        = number
  description = "Retention of VPC flow logs in CloudWatch Logs."
  default     = 90

  validation {
    condition     = contains([30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.flow_log_retention_days)
    error_message = "flow_log_retention_days must be a CloudWatch Logs retention value of at least 30."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
