#!/bin/bash

# File Organizer

# Set the source directory
source_dir="/path/to/source"

# Move files to appropriate directories based on their file type
find "$source_dir" -type f -exec sh -c '
    file="$1"
    file_type=$(file -b --mime-type "$file" | awk -F/ "{print \$1}")

    # Create the destination directory based on file type
    destination_dir="$source_dir/$file_type"
    mkdir -p "$destination_dir"

    # Move the file to the destination directory
    mv "$file" "$destination_dir"
' sh {} \;
