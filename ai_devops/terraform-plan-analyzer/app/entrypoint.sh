#!/bin/bash
set -e

# Install dependencies
pip install -r /app/requirements.txt
pip install python-gitlab

# Set default values for optional variables
PLAN_FILE=${PLAN_FILE:-"tf_output.json"}
OUTPUT_FILE=${OUTPUT_FILE:-"terraform_analysis.md"}
SAVE_SANITIZED=${SAVE_SANITIZED:-""}
GEMINI_MODEL=${GEMINI_MODEL:-"gemini-2.0-flash"}
TF_DIR=${TF_DIR:-"."}
SKIP_CODE=${SKIP_CODE:-"false"}
MAX_FILES=${MAX_FILES:-""}
SAVE_PROMPT=${SAVE_PROMPT:-""}
SEND_TO_GEMINI=${SEND_TO_GEMINI:-"false"}
GITLAB_COMMENT=${GITLAB_COMMENT:-"false"}

# Debug information
echo "Working directory: $(pwd)"
echo "Files in /app:"
ls -la /app

# Create a symlink for prompt.txt in the current directory
if [ -f "/app/prompt.txt" ]; then
  echo "Copying prompt.txt to current directory"
  cp /app/prompt.txt ./prompt.txt
fi

# Check if we need the API key
if [ "$SEND_TO_GEMINI" = "true" ]; then
  if [ -z "$GEMINI_API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY environment variable is not set but --send-to-gemini is enabled"
    exit 1
  fi
fi

# Build the command with absolute path to the script
CMD="python /app/terraform_plan_analyzer.py --plan $PLAN_FILE --output $OUTPUT_FILE --tf-dir $TF_DIR"

if [ "$SAVE_SANITIZED" != "false" ] && [ -n "$SAVE_SANITIZED" ]; then
  CMD="$CMD --save-sanitized $SAVE_SANITIZED"
fi

if [ "$SKIP_CODE" = "true" ]; then
  CMD="$CMD --skip-code"
fi

if [ -n "$MAX_FILES" ]; then
  CMD="$CMD --max-files $MAX_FILES"
fi

if [ "$SAVE_PROMPT" = "true" ]; then
  # Use an actual filename for save-prompt
  CMD="$CMD --save-prompt prompt_output.txt"
elif [ -n "$SAVE_PROMPT" ] && [ "$SAVE_PROMPT" != "false" ]; then
  CMD="$CMD --save-prompt $SAVE_PROMPT"
fi

if [ "$SEND_TO_GEMINI" = "true" ]; then
  CMD="$CMD --send-to-gemini"
fi

if [ "$GITLAB_COMMENT" = "true" ]; then
  CMD="$CMD --gitlab-comment"
fi

# Execute the analyzer
echo "Analyzing Terraform plan: $PLAN_FILE"
if [ "$SEND_TO_GEMINI" = "true" ]; then
  echo "Using Gemini model: $GEMINI_MODEL"
else
  echo "DRY RUN MODE - Not sending to Gemini"
fi

echo "Terraform directory: $TF_DIR"
echo "Output will be written to: $OUTPUT_FILE"
echo "Current directory: $(pwd)"
echo "Directory listing before execution:"
ls -la

# Modify the terraform_plan_analyzer.py script to use the local prompt.txt
sed -i 's|with open("app/prompt.txt", "r") as f:|with open("prompt.txt", "r") as f:|g' /app/terraform_plan_analyzer.py

# Execute the command
eval $CMD

echo "Directory listing after execution:"
ls -la

# Ensure files exist for artifacts
touch $OUTPUT_FILE

# Copy output files to a known location if they don't exist in the expected location
if [ ! -f "$OUTPUT_FILE" ]; then
  echo "Output file not found at $OUTPUT_FILE, creating empty file"
  echo "No changes detected in the Terraform plan." > $OUTPUT_FILE
fi

if [ "$SAVE_PROMPT" = "true" ] && [ ! -f "prompt_output.txt" ]; then
  echo "Prompt file not found, creating empty file"
  echo "No prompt was generated." > prompt_output.txt
fi

echo "Analysis complete!"