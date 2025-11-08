#!/bin/bash

# Log Cleaner

# Set the log directory
log_dir="/path/to/logs"

# Set the number of days to keep logs
days_to_keep=7

# Calculate the cutoff date in seconds
cutoff_date=$(date -d "$days_to_keep days ago" +%s)

# Iterate over the log files in the directory
for file in "$log_dir"/*; do
    if [[ -f "$file" ]]; then
        # Get the last modified date of the file in seconds
        last_modified=$(date -r "$file" +%s)

        # Compare the last modified date with the cutoff date
        if [[ $last_modified -lt $cutoff_date ]]; then
            # Remove the log file
            rm "$file"
            echo "Removed: $file"
        fi
    fi
done
