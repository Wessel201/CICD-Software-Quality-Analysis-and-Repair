variable "db_password" {
  description = "The master password for the PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "api_key" {
  description = "Shared API key used by the backend to authorize frontend proxy requests"
  type        = string
  sensitive   = true
}

variable "db_engine_version" {
  description = "PostgreSQL engine version for RDS. Use major version '16' to let AWS select the latest supported 16.x minor in the region."
  type        = string
  default     = "16"

  validation {
    condition     = can(regex("^16(\\.[0-9]+)?$", var.db_engine_version))
    error_message = "db_engine_version must be PostgreSQL major 16 (for example '16' or '16.6')."
  }
}

variable "frontend_allowed_origins" {
  description = "Allowed browser origins for direct S3 uploads/downloads via CORS"
  type        = list(string)
  default = [
    "*",
  ]
}