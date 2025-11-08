module "ec2_complete" {
  source = "../../"

  name = local.name

  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = var.instance_type
  availability_zone           = element(module.vpc.azs, 0)
  subnet_id                   = element(module.vpc.private_subnets, 0)
  vpc_security_group_ids      = [module.security_group.security_group_id]
  placement_group             = aws_placement_group.web.id
  associate_public_ip_address = var.associate_public_ip_address
  disable_api_stop            = var.disable_api_stop

  create_iam_instance_profile = var.create_iam_instance_profile
  iam_role_description        = var.iam_role_description
  iam_role_policies           = var.iam_role_policies

  hibernation                 = var.hibernation

  user_data_base64            = base64encode(local.user_data)
  user_data_replace_on_change = var.user_data_replace_on_change

  cpu_options                 = var.cpu_options
  enable_volume_tags          = var.enable_volume_tags
  root_block_device           = var.root_block_device
  ebs_block_device            = var.ebs_block_device

  tags = local.tags
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "c5.xlarge"
}

variable "associate_public_ip_address" {
  description = "Whether to associate a public IP address with the EC2 instance"
  type        = bool
  default     = true
}

variable "disable_api_stop" {
  description = "Whether to disable API termination for the EC2 instance"
  type        = bool
  default     = false
}

variable "create_iam_instance_profile" {
  description = "Whether to create an IAM instance profile for the EC2 instance"
  type        = bool
  default     = true
}

variable "iam_role_description" {
  description = "Description for the IAM role attached to the EC2 instance"
  type        = string
  default     = "IAM role for EC2 instance"
}

variable "iam_role_policies" {
  description = "IAM policies to attach to the IAM role"
  type        = map(string)
  default = {
    AdministratorAccess = "arn:aws:iam::aws:policy/AdministratorAccess"
  }
}

variable "hibernation" {
  description = "Whether to enable hibernation for the EC2 instance"
  type        = bool
  default     = true
}

variable "user_data_replace_on_change" {
  description = "Whether to replace user data on changes"
  type        = bool
  default     = true
}

variable "cpu_options" {
  description = "CPU options for the EC2 instance"
  type        = map(any)
  default = {
    core_count       = 2
    threads_per_core = 1
  }
}

variable "enable_volume_tags" {
  description = "Whether to enable volume tags"
  type        = bool
  default     = false
}

variable "root_block_device" {
  description = "Configuration for the root block device of the EC2 instance"
  type        = list(map(any))
  default = [
    {
      encrypted   = true
      volume_type = "gp3"
      throughput  = 200
      volume_size = 50
      tags = {
        Name = "my-root-block"
      }
    }
  ]
}

variable "ebs_block_device" {
  description = "Additional EBS block devices to attach to the instance"
  type        = list(map(any))
  default = [
    {
      device_name = "/dev/sdf"
      volume_type = "gp3"
      volume_size = 5
      throughput  = 200
      encrypted   = true
      tags = {
        MountPoint = "/mnt/data"
      }
    }
  ]
}
