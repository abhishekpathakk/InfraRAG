# Retrieve AWS Caller Identity for account ID interpolation
data "aws_caller_identity" "current" {}

# Generate random suffix for unique S3 bucket name
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

locals {
  bucket_name = "${var.project_name}-storage-${random_string.suffix.result}"
}

# ---------------------------------------------------------------------------
# S3 Storage (Runbooks & Serialized FAISS Vectors)
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "storage" {
  bucket        = local.bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "storage_block" {
  bucket = aws_s3_bucket.storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "storage_crypto" {
  bucket = aws_s3_bucket.storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# CloudWatch Log Groups (7-Day Retention for Cost Containment)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ingest_logs" {
  name              = "/aws/lambda/${var.project_name}-ingest"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "ask_logs" {
  name              = "/aws/lambda/${var.project_name}-ask"
  retention_in_days = 7
}

# ---------------------------------------------------------------------------
# IAM Roles & Policies (Separated Least-Privilege per Lambda)
# ---------------------------------------------------------------------------
# Ingest Role: Needs S3 PutObject/GetObject and Titan Embeddings
resource "aws_iam_role" "lambda_ingest_exec" {
  name = "${var.project_name}-lambda-ingest-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "lambda_ingest_policy" {
  name        = "${var.project_name}-ingest-policy"
  description = "Scoped permissions for S3 write, Bedrock embeddings, and CloudWatch logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BucketList"
        Effect = "Allow"
        Action = ["s3:ListBucket"]
        Resource = [aws_s3_bucket.storage.arn]
      },
      {
        Sid    = "S3ObjectReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = ["${aws_s3_bucket.storage.arn}/*"]
      },
      {
        Sid    = "BedrockEmbeddingAccess"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embedding_model_id}",
          "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      },
      {
        Sid    = "CloudWatchLogsIngest"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.ingest_logs.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ingest_policy_attach" {
  role       = aws_iam_role.lambda_ingest_exec.name
  policy_arn = aws_iam_policy.lambda_ingest_policy.arn
}

# Ask Role: Read-ONLY access to FAISS vectors and Bedrock InvokeModel
resource "aws_iam_role" "lambda_ask_exec" {
  name = "${var.project_name}-lambda-ask-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "lambda_ask_policy" {
  name        = "${var.project_name}-ask-policy"
  description = "Read-only permissions for S3 faiss_index, Bedrock models, and CloudWatch logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "S3BucketListScoped"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = [aws_s3_bucket.storage.arn]
        Condition = {
          StringLike = {
            "s3:prefix" = ["faiss_index/*", "faiss_index"]
          }
        }
      },
      {
        Sid      = "S3IndexReadOnly"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = ["${aws_s3_bucket.storage.arn}/faiss_index/*"]
      },
      {
        Sid    = "BedrockRuntimeAccess"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embedding_model_id}",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.llm_model_id}",
          "arn:aws:bedrock:us-east-1::foundation-model/*",
          "arn:aws:bedrock:us-west-2::foundation-model/*",
          "arn:aws:bedrock:ap-southeast-1::foundation-model/*",
          "arn:aws:bedrock:ap-northeast-1::foundation-model/*",
          "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      },
      {
        Sid    = "CloudWatchLogsAsk"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.ask_logs.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_ask_policy_attach" {
  role       = aws_iam_role.lambda_ask_exec.name
  policy_arn = aws_iam_policy.lambda_ask_policy.arn
}

# ---------------------------------------------------------------------------
# Lambda Functions
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "ingest" {
  function_name    = "${var.project_name}-ingest"
  role             = aws_iam_role.lambda_ingest_exec.arn
  handler          = "src.lambda_handlers.ingest.handler"
  runtime          = "python3.12"
  filename         = "${path.module}/build/lambda_payload.zip"
  source_code_hash = fileexists("${path.module}/build/lambda_payload.zip") ? filebase64sha256("${path.module}/build/lambda_payload.zip") : null
  timeout          = 60
  memory_size      = 1024

  environment {
    variables = {
      S3_BUCKET_NAME             = local.bucket_name
      BEDROCK_EMBEDDING_MODEL_ID = var.embedding_model_id
      USE_MOCK_BEDROCK           = var.use_mock_bedrock
    }
  }

  depends_on = [aws_cloudwatch_log_group.ingest_logs]
}

resource "aws_lambda_function" "ask" {
  function_name    = "${var.project_name}-ask"
  role             = aws_iam_role.lambda_ask_exec.arn
  handler          = "src.lambda_handlers.ask.handler"
  runtime          = "python3.12"
  filename         = "${path.module}/build/lambda_payload.zip"
  source_code_hash = fileexists("${path.module}/build/lambda_payload.zip") ? filebase64sha256("${path.module}/build/lambda_payload.zip") : null
  timeout          = 30
  memory_size      = 1024

  environment {
    variables = {
      S3_BUCKET_NAME             = local.bucket_name
      BEDROCK_EMBEDDING_MODEL_ID = var.embedding_model_id
      BEDROCK_LLM_MODEL_ID       = var.llm_model_id
      USE_MOCK_BEDROCK           = var.use_mock_bedrock
      INFRARAG_API_KEY           = var.infrarag_api_key
    }
  }

  depends_on = [aws_cloudwatch_log_group.ask_logs]
}

# ---------------------------------------------------------------------------
# API Gateway HTTP API ($0 Free Tier eligible) with Rate Limiting
# ---------------------------------------------------------------------------
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "x-api-key"]
  }
}


resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5
  }
}

# Route /ask (Ingest is kept private and not exposed via public API Gateway)
resource "aws_apigatewayv2_integration" "ask_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ask.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ask_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /ask"
  target    = "integrations/${aws_apigatewayv2_integration.ask_integration.id}"
}

resource "aws_lambda_permission" "apigw_ask" {
  statement_id  = "AllowAPIGatewayInvokeAsk"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ask.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*/ask"
}
