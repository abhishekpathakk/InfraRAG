output "api_gateway_endpoint" {
  description = "Base URL of the API Gateway HTTP API"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket storing runbooks and FAISS indexes"
  value       = aws_s3_bucket.storage.id
}

output "ingest_lambda_arn" {
  description = "ARN of the Ingest Lambda function"
  value       = aws_lambda_function.ingest.arn
}

output "ask_lambda_arn" {
  description = "ARN of the Ask Lambda function"
  value       = aws_lambda_function.ask.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository for sovereign container images"
  value       = aws_ecr_repository.ask_repo.repository_url
}
