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
  description = "VPC to create the load balancer in."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets in at least two availability zones."

  validation {
    condition     = length(var.public_subnet_ids) >= 2
    error_message = "An application load balancer needs subnets in at least two zones."
  }
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate for the HTTPS listener."

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:acm:[a-z0-9-]+:[0-9]{12}:certificate/", var.certificate_arn))
    error_message = "certificate_arn must be an ACM certificate ARN."
  }
}

variable "ingress_cidrs" {
  type        = list(string)
  description = "Client address ranges allowed to reach the load balancer (an internal tool may restrict this to office or VPN ranges)."

  validation {
    condition     = length(var.ingress_cidrs) > 0 && alltrue([for cidr in var.ingress_cidrs : can(cidrnetmask(cidr))])
    error_message = "ingress_cidrs must be a non-empty list of IPv4 CIDR blocks."
  }
}

variable "target_port" {
  type        = number
  description = "Port the UI server listens on."
  default     = 3000

  validation {
    condition     = var.target_port > 1024 && var.target_port < 65536
    error_message = "target_port must be an unprivileged port."
  }
}

variable "ssl_policy" {
  type        = string
  description = "TLS policy of the HTTPS listener."
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  validation {
    condition     = startswith(var.ssl_policy, "ELBSecurityPolicy-TLS13")
    error_message = "Use a TLS 1.3 capable ELBSecurityPolicy-TLS13-* policy."
  }
}

variable "deletion_protection" {
  type        = bool
  description = "Protect the load balancer from accidental deletion."
  default     = true
}

variable "log_retention_days" {
  type        = number
  description = "Days to keep load balancer access logs."
  default     = 90

  validation {
    condition     = var.log_retention_days >= 7 && var.log_retention_days <= 3650
    error_message = "log_retention_days must be between 7 and 3650."
  }
}

variable "tags" {
  type        = map(string)
  description = "Tags added to every resource."
  default     = {}
}
