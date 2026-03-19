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

variable "enable_debug_instance" {
  description = "Create a public EC2 debug host to connect to the private Postgres instance."
  type        = bool
  default     = true
}

variable "debug_instance_type" {
  description = "EC2 instance type for the debug host."
  type        = string
  default     = "t3.micro"
}

variable "debug_key_name" {
  description = "Existing EC2 key pair name for SSH access to the debug host. Required when enable_debug_instance is true."
  type        = string
  default     = "debug-instance"

  validation {
    condition     = var.enable_debug_instance == false || length(trimspace(var.debug_key_name)) > 0
    error_message = "debug_key_name must be set when enable_debug_instance is true."
  }
}

variable "debug_ssh_cidr" {
  description = "CIDR allowed to SSH into the debug host (for example, your office/home IP with /32)."
  type        = string
  default     = "0.0.0.0/0"
}