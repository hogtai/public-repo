#!/bin/bash

# Backup script

# Set the source directory and destination directory
source_dir="/path/to/source"
destination_dir="/path/to/backup"

# Create a timestamp for the backup file
timestamp=$(date +"%Y%m%d%H%M%S")

# Create a tar archive of the source directory
backup_file="$destination_dir/backup_$timestamp.tar.gz"
tar -czf "$backup_file" "$source_dir"

# Check if the backup was successful
if [ $? -eq 0 ]; then
    echo "Backup completed successfully: $backup_file"
else
    echo "Backup failed!"
fi
