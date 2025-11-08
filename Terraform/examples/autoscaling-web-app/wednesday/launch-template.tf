resource "aws_launch_template" "WebServerTemplate" {
  name        = "WebServerTemplate"
  description = "prod webserver"

  update_default_version = true

  image_id      = "ami-02f97949d306b597a"
  instance_type = "t2.micro"

  key_name = "Project18-KeyPair"

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [aws_security_group.project21_webtier_sg.id]
  }

  user_data = base64encode(<<EOT
#!/bin/bash
yum update -y
yum install httpd -y
systemctl start httpd
systemctl enable httpd
amazon-linux-extras install opel -y
yum install stress -y
EOT
  )
}

