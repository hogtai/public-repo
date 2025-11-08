resource "aws_autoscaling_group" "web_tier_autoscaling_group" {
  name_prefix               = var.asg_name_prefix
  desired_capacity          = var.asg_desired_capacity
  min_size                  = var.asg_min_size
  max_size                  = var.asg_max_size
  health_check_type         = var.asg_health_check_type
  health_check_grace_period = var.asg_health_check_grace_period
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
