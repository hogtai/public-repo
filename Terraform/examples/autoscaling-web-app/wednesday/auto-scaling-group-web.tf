resource "aws_autoscaling_group" "web_tier_autoscaling_group" {
  name_prefix               = "web-tier-auto-scaling-group"
  desired_capacity          = 2
  min_size                  = 2
  max_size                  = 5
  health_check_type         = "ELB"
  health_check_grace_period = 300
  vpc_zone_identifier       = [aws_subnet.public_subnet1_project21.id, aws_subnet.public_subnet2_project21.id]

  launch_template {
    id      = aws_launch_template.WebServerTemplate.id
    version = "$Latest"
  }

  target_group_arns = [aws_lb_target_group.web_target_group.arn]

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_subnet.public_subnet1_project21,
    aws_subnet.public_subnet2_project21,
    aws_subnet.private_subnet1_project21,
    aws_subnet.private_subnet2_project21,
    aws_lb_target_group.web_target_group,
    aws_launch_template.WebServerTemplate,
  ]
}

