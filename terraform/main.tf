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
# IAM Roles & Policies (Least Privilege)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-exec-role"

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

resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.project_name}-least-privilege-policy"
  description = "Scoped permissions for S3 bucket, Bedrock runtime, and CloudWatch logs"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.storage.arn,
          "${aws_s3_bucket.storage.arn}/*"
        ]
      },
      {
        Sid    = "BedrockRuntimeAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:Converse"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embedding_model_id}",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.llm_model_id}",
          "arn:aws:bedrock:us-east-1::foundation-model/*"
        ]
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

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
# Lambda Functions
# ---------------------------------------------------------------------------
resource "aws_lambda_function" "ingest" {
  function_name    = "${var.project_name}-ingest"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "src.lambda_handlers.ingest.handler"
  runtime          = "python3.12"
  filename         = "${path.module}/build/lambda_payload.zip"
  source_code_hash = filebase64sha256("${path.module}/build/lambda_payload.zip")
  timeout          = 60
  memory_size      = 1024

  environment {
    variables = {
      S3_BUCKET_NAME             = local.bucket_name
      BEDROCK_EMBEDDING_MODEL_ID = var.embedding_model_id
      USE_MOCK_BEDROCK           = "true"
    }
  }

  depends_on = [aws_cloudwatch_log_group.ingest_logs]
}

resource "aws_lambda_function" "ask" {
  function_name    = "${var.project_name}-ask"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "src.lambda_handlers.ask.handler"
  runtime          = "python3.12"
  filename         = "${path.module}/build/lambda_payload.zip"
  source_code_hash = filebase64sha256("${path.module}/build/lambda_payload.zip")
  timeout          = 30
  memory_size      = 1024

  environment {
    variables = {
      S3_BUCKET_NAME             = local.bucket_name
      BEDROCK_EMBEDDING_MODEL_ID = var.embedding_model_id
      BEDROCK_LLM_MODEL_ID       = var.llm_model_id
      USE_MOCK_BEDROCK           = "true"
    }
  }

  depends_on = [aws_cloudwatch_log_group.ask_logs]
}

# ---------------------------------------------------------------------------
# API Gateway HTTP API ($0 Free Tier eligible)
# ---------------------------------------------------------------------------
resource "aws_apigatewayv2_api" "http_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

# Route /ingest
resource "aws_apigatewayv2_integration" "ingest_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.ingest.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "ingest_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /ingest"
  target    = "integrations/${aws_apigatewayv2_integration.ingest_integration.id}"
}

resource "aws_lambda_permission" "apigw_ingest" {
  statement_id  = "AllowAPIGatewayInvokeIngest"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*/ingest"
}

# Route /ask
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
