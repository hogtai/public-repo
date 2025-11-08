# Define AWS Region for Deployment
variable "aws_region" {
  description = "The AWS region to deploy resources in"
  default     = "us-east-2"
}

# VPC Configuration (with Internet Gateway)
variable "vpc_cidr_block" {
  description = "The CIDR block for the VPC"
  default     = "10.10.0.0/16"
}

variable "vpc_instance_tenancy" {
  description = "The instance tenancy for the VPC"
  default     = "default"
}

variable "vpc_name_tag" {
  description = "The name tag for the VPC"
  default     = "Project_21-Terraform"
}

variable "internet_gateway_name_tag" {
  description = "The name tag for the Internet Gateway"
  default     = "project_21_internet_gateway"
}

# Subnet Configurations (2 Public / 2 Private)
variable "public_subnet1_cidr_block" {
  description = "The CIDR block for public subnet 1"
  default     = "10.10.1.0/24"
}

variable "public_subnet2_cidr_block" {
  description = "The CIDR block for public subnet 2"
  default     = "10.10.2.0/24"
}

variable "private_subnet1_cidr_block" {
  description = "The CIDR block for private subnet 1"
  default     = "10.10.3.0/24"
}

variable "private_subnet2_cidr_block" {
  description = "The CIDR block for private subnet 2"
  default     = "10.10.4.0/24"
}

variable "availability_zone_a" {
  description = "The first availability zone"
  default     = "us-east-2a"
}

variable "availability_zone_b" {
  description = "The second availability zone"
  default     = "us-east-2b"
}

variable "public_subnet1_name_tag" {
  description = "The name tag for public subnet 1"
  default     = "public_subnet1_project21"
}

variable "public_subnet2_name_tag" {
  description = "The name tag for public subnet 2"
  default     = "public_subnet2_project21"
}

variable "private_subnet1_name_tag" {
  description = "The name tag for private subnet 1"
  default     = "private_subnet1_project21"
}

variable "private_subnet2_name_tag" {
  description = "The name tag for private subnet 2"
  default     = "private_subnet2_project21"
}

# NAT Gateway Configuration (1 Per Public Subnet)
variable "nat_eip1_name_tag" {
  description = "The name tag for the NAT Elastic IP 1"
  default     = "public_subnet1_NAT_eip"
}

variable "nat_gateway1_name_tag" {
  description = "The name tag for the NAT Gateway 1"
  default     = "public_subnet1_NAT_gateway"
}

variable "nat_eip2_name_tag" {
  description = "The name tag for the NAT Elastic IP 2"
  default     = "public_subnet2_NAT_eip"
}

variable "nat_gateway2_name_tag" {
  description = "The name tag for the NAT Gateway 2"
  default     = "public_subnet2_NAT_gateway"
}

# Public Route Table Configuration
variable "public_route_table_name_tag" {
  description = "The name tag for the public route table"
  default     = "project21_vpc_public_route_table"
}

# Private Route Table Configuration
variable "private_route_table1_name_tag" {
  description = "The name tag for the first private route table"
  default     = "project21_vpc_private_route_table1"
}

variable "private_route_table2_name_tag" {
  description = "The name tag for the second private route table"
  default     = "project21_vpc_private_route_table2"
}

# Web Tier Security Group Settings
variable "sg_name" {
  default = "project21_webtier_sg"
}

variable "sg_description" {
  default = "Allows access to webserver"
}

variable "sg_ingress_ports" {
  type = list(object({
    from_port = number
    to_port   = number
    protocol  = string
  }))
  default = [
    {
      from_port = 80
      to_port   = 80
      protocol  = "tcp"
    },
    {
      from_port = 443
      to_port   = 443
      protocol  = "tcp"
    },
    {
      from_port = 22
      to_port   = 22
      protocol  = "tcp"
    }
  ]
}

variable "sg_ssh_cidr_blocks" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}

variable "sg_egress_rule" {
  type = object({
    from_port   = number
    to_port     = number
    protocol    = string
    cidr_blocks = list(string)
  })
  default = {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

variable "sg_tags" {
  type = map(string)
  default = {
    Name = "project21_webtier_sg"
  }
}

# Web Tier Launch Template
variable "launch_template_name" {
  description = "The name of the launch template"
  default     = "WebServerTemplate"
}

variable "launch_template_description" {
  description = "The description of the launch template"
  default     = "prod webserver"
}

variable "launch_template_image_id" {
  description = "The AMI ID for the launch template"
  default     = "ami-029940b2e685ba541"
}

variable "launch_template_instance_type" {
  description = "The instance type for the launch template"
  default     = "t2.micro"
}

variable "launch_template_key_name" {
  description = "The key pair name for the launch template"
  default     = "Project18-KeyPair"
}

variable "launch_template_network_interface" {
  description = "The network interface configuration for the launch template"
  default = {
    associate_public_ip_address = true
  }
}

#Web Tier Target Group
variable "target_group_name" {
  description = "The name of the target group"
  default     = "web-target-group"
}

variable "target_group_port" {
  description = "The port on which the target group listens"
  default     = 80
}

variable "target_group_protocol" {
  description = "The protocol used by the target group"
  default     = "HTTP"
}

variable "health_check_enabled" {
  description = "Indicates whether health checks are enabled for the target group"
  default     = true
}

variable "health_check_interval" {
  description = "The approximate amount of time, in seconds, between health checks of an individual target"
  default     = 30
}

variable "health_check_path" {
  description = "The destination for the health check request"
  default     = "/"
}

variable "health_check_timeout" {
  description = "The amount of time, in seconds, during which no response means a failed health check"
  default     = 5
}

variable "healthy_threshold" {
  description = "The number of consecutive health checks successes required before considering an unhealthy target healthy"
  default     = 2
}

variable "unhealthy_threshold" {
  description = "The number of consecutive health check failures required before considering a target unhealthy"
  default     = 2
}

# Web Tier Load Balancer Configuration
variable "load_balancer_name" {
  type        = string
  description = "Name of the load balancer"
  default     = "WebServerLoadBalancer"
}

variable "load_balancer_internal" {
  type        = bool
  description = "Whether the load balancer is internal or not"
  default     = false
}

variable "load_balancer_type" {
  type        = string
  description = "Type of load balancer"
  default     = "application"
}

variable "ip_address_type" {
  type        = string
  description = "IP address type for the load balancer"
  default     = "ipv4"
}

variable "listener_port" {
  type        = number
  description = "Port for the load balancer listener"
  default     = 80
}

variable "listener_protocol" {
  type        = string
  description = "Protocol for the load balancer listener"
  default     = "HTTP"
}

variable "default_action_type" {
  type        = string
  description = "Default action type for the load balancer listener"
  default     = "forward"
}

#Auto Scaling Group Web-Tier

variable "asg_name_prefix" {
  description = "Name prefix for the auto-scaling group"
  default     = "web-tier-auto-scaling-group"
}

variable "asg_desired_capacity" {
  description = "The desired capacity of the auto-scaling group"
  default     = 2
}

variable "asg_min_size" {
  description = "The minimum size of the auto-scaling group"
  default     = 2
}

variable "asg_max_size" {
  description = "The maximum size of the auto-scaling group"
  default     = 5
}

variable "asg_health_check_type" {
  description = "The health check type for the auto-scaling group"
  default     = "ELB"
}

variable "asg_health_check_grace_period" {
  description = "The health check grace period for the auto-scaling group"
  default     = 300
}

#Database Tier Security Group Confiuration
variable "db_tier_sg_name" {
  description = "The name of the DB Tier Security Group"
  default     = "db_tier_sg"
}

variable "db_tier_sg_description" {
  description = "The description of the DB Tier Security Group"
  default     = "Allows inbound traffic from the Web Tier Security Group and SSH from any IP"
}

variable "db_tier_sg_web_ingress_from_port" {
  description = "The starting port for the Web Tier Security Group ingress rule"
  default     = 0
}

variable "db_tier_sg_web_ingress_to_port" {
  description = "The ending port for the Web Tier Security Group ingress rule"
  default     = 65535
}

variable "db_tier_sg_web_ingress_protocol" {
  description = "The protocol for the Web Tier Security Group ingress rule"
  default     = "tcp"
}

variable "db_tier_sg_ssh_ingress_from_port" {
  description = "The starting port for the SSH ingress rule"
  default     = 22
}

variable "db_tier_sg_ssh_ingress_to_port" {
  description = "The ending port for the SSH ingress rule"
  default     = 22
}

variable "db_tier_sg_ssh_ingress_protocol" {
  description = "The protocol for the SSH ingress rule"
  default     = "tcp"
}

variable "db_tier_sg_ssh_ingress_cidr_blocks" {
  description = "The CIDR blocks for the SSH ingress rule"
  default     = ["0.0.0.0/0"]
}

variable "db_tier_sg_egress_from_port" {
  description = "The starting port for the egress rule"
  default     = 0
}

variable "db_tier_sg_egress_to_port" {
  description = "The ending port for the egress rule"
  default     = 0
}

variable "db_tier_sg_egress_protocol" {
  description = "The protocol for the egress rule"
  default     = "-1"
}

variable "db_tier_sg_egress_cidr_blocks" {
  description = "The CIDR blocks for the egress rule"
  default     = ["0.0.0.0/0"]
}

variable "db_tier_sg_name_tag" {
  description = "The name tag for the DB Tier Security Group"
  default     = "Project_21_DB_Tier_SG"
}

# Database Tier Configuration
variable "db_cluster_identifier" {
  description = "The DB Cluster identifier"
  default     = "thoglund-database-84135"
}

variable "db_master_username" {
  description = "The master username for the database"
  default     = "thoglund"
}

variable "db_master_password" {
  description = "The master password for the database"
  default     = "123456abcDEF"
}

variable "db_name" {
  description = "The name of the database in the RDS instance"
  default     = "wordpress"
}

variable "db_instance_class" {
  description = "The database instance class"
  default     = "db.r5.large"
}

variable "db_storage_type" {
  description = "The storage type for the database"
  default     = "io1"
}

variable "db_allocated_storage" {
  description = "The allocated storage for the database (in GB)"
  default     = 100
}

variable "db_provisioned_iops" {
  description = "The provisioned IOPS for the database"
  default     = 1000
}

variable "db_subnet_group_name" {
  description = "The name for the database subnet group"
  default     = "private-db-subnet-group"
}
