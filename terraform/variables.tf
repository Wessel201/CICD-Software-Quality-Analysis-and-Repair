variable "db_password" {
  description = "The master password for the PostgreSQL database"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}