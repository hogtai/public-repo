# Define variables
variable "instance_type" {
  type    = string
  default = "t2.micro"
}

# Define S3 bucket for Jenkins artifacts
resource "random_id" "random_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "jenkins-artifacts" {
  bucket = "jenkins-artifacts-${random_id.random_suffix.hex}"
}

# Define IAM role for EC2 instance
resource "aws_iam_role" "jenkins-s3-role" {
  name = "jenkins-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

# Define IAM instance profile for EC2 instance
resource "aws_iam_instance_profile" "jenkins-s3-instance-profile" {
  name = "jenkins-s3-instance-profile"
  role = aws_iam_role.jenkins-s3-role.name
}

# Define IAM policy for S3 access
resource "aws_iam_policy" "jenkins-s3-policy" {
  name        = "jenkins-s3-policy"
  policy      = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${aws_s3_bucket.jenkins-artifacts.arn}/*",
          "${aws_s3_bucket.jenkins-artifacts.arn}"
        ]
      }
    ]
  })
}

# Attach IAM policy to IAM role
resource "aws_iam_role_policy_attachment" "jenkins-s3-policy-attachment" {
  policy_arn = aws_iam_policy.jenkins-s3-policy.arn
  role       = aws_iam_role.jenkins-s3-role.name
}

# Define ACL for S3 bucket
resource "aws_s3_bucket_acl" "jenkins-artifacts-acl" {
  bucket = aws_s3_bucket.jenkins-artifacts.id

  # Set bucket ACL to private
  acl = "private"
}

# Define EC2 instance running Jenkins
resource "aws_instance" "jenkins" {
  ami           = "ami-0533def491c57d991"
  instance_type = var.instance_type
  user_data = <<-EOF
    #!/bin/bash
    sudo yum update -y
    sudo wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo
    sudo rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io.key
    sudo yum upgrade -y
    sudo amazon-linux-extras install java-openjdk11 -y
    sudo yum install jenkins -y
    sudo systemctl enable jenkins
    sudo systemctl start jenkins
  EOF

  # Assign IAM role to EC2 instance
  iam_instance_profile = aws_iam_instance_profile.jenkins-s3-instance-profile.id

  # Assign security group to EC2 instance allowing traffic on port 22 and 8080
  vpc_security_group_ids = [aws_security_group.jenkins-sg.id]

  # Tag EC2
  tags = {
    Name = "jenkins-instance"
  }
}

# Define security group allowing traffic on port 22 and 8080
resource "aws_security_group" "jenkins-sg" {
  name_prefix = "jenkins-sg"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
