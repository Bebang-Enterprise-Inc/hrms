variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "key_pair_name" {
  description = "AWS Key Pair name for EC2 SSH access"
  type        = string
}


