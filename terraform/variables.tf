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
