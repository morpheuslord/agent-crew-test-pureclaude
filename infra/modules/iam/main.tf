data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_partition" "current" {}

locals {
  log_group_arn = {
    for service in ["ui", "api"] :
    service => "arn:${data.aws_partition.current.partition}:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/${var.name}/${service}"
  }
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  for_each = toset(["ui", "api"])

  name               = "${var.name}-${each.key}"
  description        = "Taskboard ${each.key} instances"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json

  tags = var.tags
}

# Shell access goes through SSM Session Manager; no SSH keys or inbound SSH.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  for_each = aws_iam_role.this

  role       = each.value.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "common" {
  for_each = toset(["ui", "api"])

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid = "PullOwnImage"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
    resources = [var.repository_arns[each.key]]
  }

  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${local.log_group_arn[each.key]}:*"]
  }

  statement {
    sid       = "ReadOwnParameters"
    actions   = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = each.key == "ui" ? var.ui_parameter_arns : var.api_parameter_arns
  }

  statement {
    sid       = "UseEnvironmentKey"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "common" {
  for_each = aws_iam_role.this

  name   = "taskboard-${each.key}-runtime"
  role   = each.value.id
  policy = data.aws_iam_policy_document.common[each.key].json
}

data "aws_iam_policy_document" "api_data" {
  statement {
    sid       = "ReadApiSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.api_secret_arns
  }

  statement {
    sid       = "AttachmentObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.attachments_bucket_arn}/attachments/*"]
  }

  # HeadBucket (used by the API readiness probe) is authorised by s3:ListBucket.
  statement {
    sid       = "AttachmentBucket"
    actions   = ["s3:ListBucket"]
    resources = [var.attachments_bucket_arn]
  }

  statement {
    sid       = "EncryptAttachments"
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "api_data" {
  name   = "taskboard-api-data"
  role   = aws_iam_role.this["api"].id
  policy = data.aws_iam_policy_document.api_data.json
}

resource "aws_iam_instance_profile" "this" {
  for_each = aws_iam_role.this

  name = "${var.name}-${each.key}"
  role = each.value.name

  tags = var.tags
}
