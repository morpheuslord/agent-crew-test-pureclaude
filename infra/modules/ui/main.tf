data "aws_region" "current" {}

data "aws_ssm_parameter" "ami" {
  name = var.ami_ssm_parameter
}

resource "aws_cloudwatch_log_group" "ui" {
  name              = "/${var.name}/ui"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = var.tags
}

resource "aws_security_group" "ui" {
  name        = "${var.name}-ui"
  description = "UI instances: app port from the public load balancer only"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = "${var.name}-ui" })
}

resource "aws_vpc_security_group_ingress_rule" "from_alb" {
  security_group_id            = aws_security_group.ui.id
  description                  = "UI port from the public load balancer"
  referenced_security_group_id = var.alb_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = var.container_port
  to_port                      = var.container_port
}

# HTTPS out through the NAT gateway for ECR, SSM and CloudWatch Logs. API access is added by the
# environment, which knows the API load balancer's security group.
resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.ui.id
  description       = "HTTPS to AWS service endpoints"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

locals {
  image = "${var.image_repository_url}:${var.image_tag}"
}

resource "aws_launch_template" "ui" {
  name_prefix   = "${var.name}-ui-"
  image_id      = data.aws_ssm_parameter.ami.insecure_value
  instance_type = var.instance_type

  iam_instance_profile {
    name = var.instance_profile_name
  }

  vpc_security_group_ids = [aws_security_group.ui.id]

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
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
    log_group               = aws_cloudwatch_log_group.ui.name
    api_base_url            = var.api_base_url
    public_url              = var.public_url
    service_token_parameter = var.service_token_parameter
    ui_secret_parameter     = var.ui_secret_parameter
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = merge(var.tags, { Name = "${var.name}-ui", Service = "ui" })
  }

  tag_specifications {
    resource_type = "volume"
    tags          = merge(var.tags, { Name = "${var.name}-ui" })
  }

  tags = var.tags
}

resource "aws_instance" "ui" {
  count = var.instance_count

  subnet_id = var.private_subnet_ids[count.index % length(var.private_subnet_ids)]

  launch_template {
    id      = aws_launch_template.ui.id
    version = aws_launch_template.ui.latest_version
  }

  tags = merge(var.tags, { Name = "${var.name}-ui-${count.index}", Service = "ui" })
}

resource "aws_lb_target_group_attachment" "ui" {
  count = var.instance_count

  target_group_arn = var.target_group_arn
  target_id        = aws_instance.ui[count.index].id
  port             = var.container_port
}
