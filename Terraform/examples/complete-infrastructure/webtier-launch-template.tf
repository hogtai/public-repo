locals {
  launch_template_user_data = <<-EOF
#!/bin/bash
yum update -y
amazon-linux-extras install -y lamp-mariadb10.2-php7.2 php7.2
yum install -y httpd
systemctl start httpd
systemctl enable httpd
wget https://wordpress.org/latest.tar.gz
tar -xzf latest.tar.gz
cp -R wordpress/* /var/www/html/
chown -R apache:apache /var/www/html/
chmod -R 755 /var/www/html/
# Update Apache configuration to use index.php as the default index file
echo 'DirectoryIndex index.php index.html' > /etc/httpd/conf.d/wordpress.conf
systemctl restart httpd

# Create the WordPress configuration file with the database details
cat > /var/www/html/wp-config.php <<EOT
<?php
define( 'DB_NAME', '${var.db_name}' );
define( 'DB_USER', '${var.db_master_username}' );
define( 'DB_PASSWORD', '${var.db_master_password}' );
define( 'DB_HOST', '${aws_rds_cluster.aurora_mysql_cluster.endpoint}' );
define( 'DB_CHARSET', 'utf8' );
define( 'DB_COLLATE', '' );
EOT

# Add the salt values to the WordPress configuration file
curl -s https://api.wordpress.org/secret-key/1.1/salt/ >> /var/www/html/wp-config.php

# Finish the WordPress configuration file
cat >> /var/www/html/wp-config.php <<EOT
\$table_prefix = 'wp_';
define( 'WP_DEBUG', false );
if ( ! defined( 'ABSPATH' ) ) {
    define( 'ABSPATH', dirname( __FILE__ ) . '/' );
}
require_once( ABSPATH . 'wp-settings.php' );
EOT
EOF
}

resource "aws_launch_template" "WebServerTemplate" {
  name        = var.launch_template_name
  description = var.launch_template_description

  update_default_version = true

  image_id      = var.launch_template_image_id
  instance_type = var.launch_template_instance_type

  key_name = var.launch_template_key_name

  network_interfaces {
    associate_public_ip_address = var.launch_template_network_interface.associate_public_ip_address
    security_groups             = [aws_security_group.project21_webtier_sg.id]
  }

  user_data = base64encode(local.launch_template_user_data)
}
