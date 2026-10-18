# Security group rules between modules. Each module owns its group; the environment wires the
# allowed paths: client -> ALB -> UI -> internal API LB -> API -> PostgreSQL / cache.

resource "aws_vpc_security_group_egress_rule" "alb_to_ui" {
  security_group_id            = module.alb.security_group_id
  description                  = "Forward to the UI instances"
  referenced_security_group_id = module.ui.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 3000
  to_port                      = 3000
}

resource "aws_vpc_security_group_egress_rule" "ui_to_api_lb" {
  security_group_id            = module.ui.security_group_id
  description                  = "Call the internal API load balancer"
  referenced_security_group_id = module.api.load_balancer_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}

resource "aws_vpc_security_group_ingress_rule" "api_lb_from_ui" {
  security_group_id            = module.api.load_balancer_security_group_id
  description                  = "HTTP from the UI instances"
  referenced_security_group_id = module.ui.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}

resource "aws_vpc_security_group_egress_rule" "api_to_db" {
  security_group_id            = module.api.security_group_id
  description                  = "PostgreSQL"
  referenced_security_group_id = module.database.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_ingress_rule" "db_from_api" {
  security_group_id            = module.database.security_group_id
  description                  = "PostgreSQL from the API instances"
  referenced_security_group_id = module.api.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_vpc_security_group_egress_rule" "api_to_cache" {
  security_group_id            = module.api.security_group_id
  description                  = "Valkey/Redis over TLS"
  referenced_security_group_id = module.cache.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_ingress_rule" "cache_from_api" {
  security_group_id            = module.cache.security_group_id
  description                  = "Valkey/Redis from the API instances"
  referenced_security_group_id = module.api.security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}
