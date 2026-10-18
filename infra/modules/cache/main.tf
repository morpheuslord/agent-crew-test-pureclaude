resource "aws_security_group" "cache" {
  name        = "${var.name}-cache"
  description = "Valkey/Redis; ingress from the API instances is added by the environment"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-cache" })
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-cache"
  subnet_ids = var.private_subnet_ids

  tags = var.tags
}

# The replication group needs the token as an argument, so it is stored in Terraform state
# (sensitive). The state backend is encrypted and access-controlled; see docs/DEPLOYMENT.md.
resource "random_password" "auth_token" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "auth_token" {
  name_prefix             = "${var.name}/cache-auth-token-"
  description             = "AUTH token of the Taskboard cache"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = 7

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "auth_token" {
  secret_id     = aws_secretsmanager_secret.auth_token.id
  secret_string = random_password.auth_token.result
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id       = "${var.name}-cache"
  description                = "Taskboard API cache"
  engine                     = var.engine
  engine_version             = var.engine_version
  node_type                  = var.node_type
  num_cache_clusters         = var.replicas
  port                       = 6379
  subnet_group_name          = aws_elasticache_subnet_group.this.name
  security_group_ids         = [aws_security_group.cache.id]
  automatic_failover_enabled = var.replicas > 1
  multi_az_enabled           = var.replicas > 1
  at_rest_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  transit_encryption_enabled = true
  transit_encryption_mode    = "required"
  auth_token                 = random_password.auth_token.result
  auth_token_update_strategy = "ROTATE"
  snapshot_retention_limit   = 1
  auto_minor_version_upgrade = true
  apply_immediately          = false

  tags = var.tags
}
