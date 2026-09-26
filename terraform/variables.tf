variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model ID"
  type        = string
  default     = "amazon.amazon.nova-2-lite-v1:0"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60
}

variable "api_throttle_burst_limit" {
  description = "API Gateway throttle burst limit"
  type        = number
  default     = 10
}

variable "api_throttle_rate_limit" {
  description = "API Gateway throttle rate limit"
  type        = number
  default     = 5
}

variable "use_custom_domain" {
  description = "Attach a custom domain to CloudFront"
  type        = bool
  default     = false
}

variable "root_domain" {
  description = "Apex domain name, e.g. mydomain.com"
  type        = string
  default     = ""
}

variable "ld_library_path" {
  description = "For using poppler custom layer"
  type        = string
  sensitive   = false
}

variable "poppler_path" {
  description = "Path for popper"
  type        = string
  sensitive   = false
}

variable "openai_api_key" {
  description = "OpenAI API key used by the backend for observability and OpenAI API calls"
  type        = string
  sensitive   = true
}

variable "pdf_dpi" {
  description = "DPI for PDF to image conversion"
  type        = string
  default     = "350"
}

variable "gpt_model" {
  description = "OpenAI GPT model ID for parsing"
  type        = string
  default     = "gpt-4o-2024-11-20"
}

variable "lambda_snap_start" {
  description = "SnapStart configuration for Lambda function (PublishedVersions or None)"
  type        = string
  default     = "PublishedVersions"
  validation {
    condition     = contains(["PublishedVersions", "None"], var.lambda_snap_start)
    error_message = "lambda_snap_start must be either 'PublishedVersions' or 'None'."
  }
}
