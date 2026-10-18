data "aws_region" "current" {}

data "aws_ssm_parameter" "ami" {
  name = var.ami_ssm_parameter
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/${var.name}/api"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

# Internal load balancer in front of the API instances; never reachable from the internet.
resource "aws_security_group" "lb" {
  name        = "${var.name}-api-lb"
  description = "Internal API load balancer; ingress from the UI instances is added by the environment"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-api-lb" })
}

resource "aws_security_group" "api" {
  name        = "${var.name}-api"
  description = "API instances: app port from the internal load balancer only"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-api" })
}

resource "aws_vpc_security_group_egress_rule" "lb_to_api" {
  security_group_id            = aws_security_group.lb.id
  description                  = "Forward to the API instances"
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

resource "aws_vpc_security_group_ingress_rule" "api_from_lb" {
  security_group_id            = aws_security_group.api.id
  description                  = "API port from the internal load balancer"
  referenced_security_group_id = aws_security_group.lb.id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

# HTTPS out through NAT: AWS APIs (ECR, SSM, Secrets Manager, S3, Logs) and project webhooks,
# whose destinations are user supplied (the application blocks private and metadata addresses).
resource "aws_vpc_security_group_egress_rule" "api_https" {
  security_group_id = aws_security_group.api.id
  description       = "HTTPS to AWS APIs and webhook receivers"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

resource "aws_lb" "internal" {
  name                       = substr("${var.name}-api", 0, 32)
  load_balancer_type         = "application"
  internal                   = true
  security_groups            = [aws_security_group.lb.id]
  subnets                    = var.private_subnet_ids
  drop_invalid_header_fields = true
  desync_mitigation_mode     = "strictest"
  idle_timeout               = 60

  tags = var.tags
}

resource "aws_lb_target_group" "api" {
  name                 = substr("${var.name}-api", 0, 32)
  port                 = var.container_port
  protocol             = "HTTP"
  target_type          = "instance"
  vpc_id               = var.vpc_id
  deregistration_delay = 30

  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = var.tags
}

resource "aws_lb_listener" "internal" {
  load_balancer_arn = aws_lb.internal.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  tags = var.tags
}

locals {
  image = "${var.image_repository_url}:${var.image_tag}"
}

resource "aws_launch_template" "api" {
  name_prefix   = "${var.name}-api-"
  image_id      = data.aws_ssm_parameter.ami.insecure_value
  instance_type = var.instance_type

  iam_instance_profile {
    name = var.instance_profile_name
  }

  vpc_security_group_ids = [aws_security_group.api.id]

  # IMDSv2 only. Hop limit 2 lets the container (one network hop away) use the instance role
  # for S3; nothing else on the instance runs untrusted code.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "disabled"
  }

  monitoring {
    enabled = true
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      kms_key_id            = var.kms_key_arn
      delete_on_termination = true
    }
  }

  user_data = base64encode(templatefile("${path.module}/templates/user_data.sh.tftpl", {
    region                  = data.aws_region.current.region
    registry                = split("/", var.image_repository_url)[0]
    image                   = local.image
    port                    = var.container_port
    log_group               = aws_cloudwatch_log_group.api.name
    public_ui_url           = var.public_ui_url
    service_token_parameter = var.service_token_parameter
    db_host                 = var.database.host
    db_port                 = var.database.port
    db_name                 = var.database.name
    db_secret_arn           = var.database.secret_arn
    cache_host              = var.cache.host
    cache_port              = var.cache.port
    cache_secret_arn        = var.cache.secret_arn
    bucket                  = var.attachments_bucket
    kms_key_arn             = var.kms_key_arn
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tags, { Name = "${var.name}-api", Service = "api" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(var.tags, { Name = "${var.name}-api" })
  }

  tags = var.tags
}

resource "aws_instance" "api" {
  count = var.instance_count

  subnet_id = var.private_subnet_ids[count.index % length(var.private_subnet_ids)]

  launch_template {
    id      = aws_launch_template.api.id
    version = aws_launch_template.api.latest_version
  }

  tags = merge(var.tags, { Name = "${var.name}-api-${count.index}", Service = "api" })
}

resource "aws_lb_target_group_attachment" "api" {
  count = var.instance_count

  target_group_arn = aws_lb_target_group.api.arn
  target_id        = aws_instance.api[count.index].id
  port             = var.container_port
}
