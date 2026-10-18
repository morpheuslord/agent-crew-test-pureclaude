output "repository_urls" {
  description = "Push/pull URLs of the image repositories, keyed by service (api, ui)."
  value       = { for service, repo in aws_ecr_repository.this : service => repo.repository_url }
}

output "repository_arns" {
  description = "ARNs of the image repositories, keyed by service (api, ui)."
  value       = { for service, repo in aws_ecr_repository.this : service => repo.arn }
}
