variable "security_group_name" {
  description = "The name of the security group"
  type        = string
}

variable "security_group_description" {
  description = "The description of the security group"
  type        = string
}

variable "inbound_port1" {
  description = "The first inbound port to allow traffic on"
  type        = number
}

variable "inbound_port2" {
  description = "The second inbound port to allow traffic on"
  type        = number
}

variable "outbound_port" {
  description = "The outbound port for the security group"
  type        = number
  default     = 0
}

variable "outbound_cidr_blocks" {
  description = "The CIDR blocks for outbound traffic"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

