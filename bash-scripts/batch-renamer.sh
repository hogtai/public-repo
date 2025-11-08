#!/bin/bash

# Batch Renamer

# Set the source directory
source_dir="/path/to/source"

# Set the pattern to match and the new name format
pattern="*.txt"
new_name_format="file_"

# Counter for numbering the files
counter=1

# Iterate over the files in the source directory
for file in "$source_dir/$pattern"; do
    if [[ -f "$file" ]]; then
        # Get the file extension
        extension="${file##*.}"
        
        # Create the new file name
        new_name="${new_name_format}${counter}.${extension}"

        # Rename the file
        mv "$file" "$source_dir/$new_name"
        
        # Increment the counter
        ((counter++))
    fi
done
