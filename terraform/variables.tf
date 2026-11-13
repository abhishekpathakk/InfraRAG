variable "aws_region" {
  description = "AWS deployment region (default: ap-south-1 Mumbai)"
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Project name prefix for all AWS resources"
  type        = string
  default     = "infrarag"
}

variable "environment" {
  description = "Deployment environment (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

variable "embedding_model_id" {
  description = "Amazon Bedrock embedding model ID"
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "llm_model_id" {
  description = "Amazon Bedrock LLM model ID"
  type        = string
  default     = "amazon.nova-micro-v1:0"
}

variable "infrarag_api_key" {
  description = "Optional API key for /ask endpoint (enforces x-api-key authentication when non-empty)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "use_mock_bedrock" {
  description = "Set to true for zero-cost free-tier mock execution, or false for live Amazon Bedrock models"
  type        = string
  default     = "true"
}

variable "embedding_provider" {
  description = "Embedding provider for Lambda execution (default: local for benchmarked neural pipeline, or bedrock/mock when configured)"
  type        = string
  default     = "local"
}

variable "embedding_dimension" {
  description = "Embedding vector dimension matching active model (384 for BAAI/bge-small-en-v1.5, 1024 for Titan/Mock)"
  type        = number
  default     = 384
}

variable "lambda_layers" {
  description = "Optional list of Lambda Layer ARNs (e.g. AWS-managed NumPy/SciPy layer)"
  type        = list(string)
  default     = []
}

variable "lambda_package_type" {
  description = "Lambda package type: 'Image' for sovereign container image (benchmarked neural pipeline), or 'Zip' for legacy zip payload"
  type        = string
  default     = "Image"
}

variable "lambda_image_uri" {
  description = "ECR or local container image URI for the /ask Lambda function when package_type is 'Image'"
  type        = string
  default     = ""
}

variable "lambda_image_digest" {
  description = "Pinned immutable SHA-256 digest of the ECR container image (e.g. sha256:...)"
  type        = string
  default     = ""
}

