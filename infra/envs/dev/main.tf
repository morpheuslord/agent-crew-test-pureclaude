locals {
  name = "taskboard-${var.environment}"
  tags = {
    Application = "taskboard"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  public_subnets  = [for index, _ in var.availability_zones : cidrsubnet(var.vpc_cidr, 8, index)]
  private_subnets = [for index, _ in var.availability_zones : cidrsubnet(var.vpc_cidr, 8, index + 100)]
}

module "network" {
  source = "../../modules/network"

  name                 = local.name
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = local.public_subnets
  private_subnet_cidrs = local.private_subnets
  single_nat_gateway   = true
  kms_key_arn          = aws_kms_key.main.arn
}

module "registry" {
  source = "../../modules/registry"

  name        = local.name
  kms_key_arn = aws_kms_key.main.arn
}

module "storage" {
  source = "../../modules/storage"

  name        = local.name
  kms_key_arn = aws_kms_key.main.arn
}

module "database" {
  source = "../../modules/database"

  name                = local.name
  vpc_id              = module.network.vpc_id
  private_subnet_ids  = module.network.private_subnet_ids
  instance_class      = var.db_instance_class
  multi_az            = var.db_multi_az
  deletion_protection = var.deletion_protection
  kms_key_arn         = aws_kms_key.main.arn
}

module "cache" {
  source = "../../modules/cache"

  name               = local.name
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  node_type          = var.cache_node_type
  kms_key_arn        = aws_kms_key.main.arn
}

module "iam" {
  source = "../../modules/iam"

  name                   = local.name
  repository_arns        = module.registry.repository_arns
  ui_parameter_arns      = [aws_ssm_parameter.service_token.arn, aws_ssm_parameter.ui_secret.arn]
  api_parameter_arns     = [aws_ssm_parameter.service_token.arn]
  api_secret_arns        = [module.database.master_user_secret_arn, module.cache.auth_token_secret_arn]
  attachments_bucket_arn = module.storage.bucket_arn
  kms_key_arn            = aws_kms_key.main.arn
}

module "alb" {
  source = "../../modules/alb"

  name                = local.name
  vpc_id              = module.network.vpc_id
  public_subnet_ids   = module.network.public_subnet_ids
  certificate_arn     = var.certificate_arn
  ingress_cidrs       = var.allowed_client_cidrs
  deletion_protection = var.deletion_protection
}

module "api" {
  source = "../../modules/api"

  name                    = local.name
  vpc_id                  = module.network.vpc_id
  private_subnet_ids      = module.network.private_subnet_ids
  instance_type           = var.instance_type
  instance_count          = var.api_instance_count
  instance_profile_name   = module.iam.api_instance_profile_name
  image_repository_url    = module.registry.repository_urls["api"]
  image_tag               = var.image_tag
  public_ui_url           = var.public_url
  service_token_parameter = aws_ssm_parameter.service_token.name
  attachments_bucket      = module.storage.bucket_name
  kms_key_arn             = aws_kms_key.main.arn

  database = {
    host       = module.database.host
    port       = module.database.port
    name       = module.database.database_name
    secret_arn = module.database.master_user_secret_arn
  }

  cache = {
    host       = module.cache.host
    port       = module.cache.port
    secret_arn = module.cache.auth_token_secret_arn
  }
}

module "ui" {
  source = "../../modules/ui"

  name                    = local.name
  vpc_id                  = module.network.vpc_id
  private_subnet_ids      = module.network.private_subnet_ids
  instance_type           = var.instance_type
  instance_count          = var.ui_instance_count
  instance_profile_name   = module.iam.ui_instance_profile_name
  alb_security_group_id   = module.alb.security_group_id
  target_group_arn        = module.alb.target_group_arn
  image_repository_url    = module.registry.repository_urls["ui"]
  image_tag               = var.image_tag
  api_base_url            = module.api.internal_url
  public_url              = var.public_url
  service_token_parameter = aws_ssm_parameter.service_token.name
  ui_secret_parameter     = aws_ssm_parameter.ui_secret.name
  kms_key_arn             = aws_kms_key.main.arn
}
