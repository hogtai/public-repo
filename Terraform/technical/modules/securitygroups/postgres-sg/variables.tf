variable "security_group_name" {
  description = "The name of the security group"
  type        = string
  default     = "my-security-group"
}

variable "security_group_description" {
  description = "The description of the security group"
  type        = string
  default     = "Security group for allowing inbound traffic on ports 80 & 443"
}

variable "inbound_port1" {
  description = "The first inbound port to allow traffic on"
  type        = number
  default     = 5432
}


