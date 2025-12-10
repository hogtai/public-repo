# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Terraform Plan Analyzer** - a CI/CD tool that analyzes Terraform infrastructure-as-code plans and provides AI-powered insights using Google's Gemini API. It integrates into GitLab CI/CD pipelines to automatically review infrastructure changes in merge requests.

## Commands

### Development and Testing

```bash
# Install dependencies
pip install -r app/requirements.txt

# Run analysis (dry-run mode - no API call)
python app/terraform_plan_analyzer.py --plan <plan_file.json> --output analysis.md

# Run with Gemini API analysis
python app/terraform_plan_analyzer.py --plan <plan_file.json> --output analysis.md --send-to-gemini

# Save sanitized plan (useful for debugging redaction)
python app/terraform_plan_analyzer.py --plan <plan_file.json> --save-sanitized sanitized.json

# Save generated prompt without sending to API
python app/terraform_plan_analyzer.py --plan <plan_file.json> --save-prompt prompt.txt

# Post results to GitLab MR (requires GITLAB_TOKEN env var)
python app/terraform_plan_analyzer.py --plan <plan_file.json> --send-to-gemini --gitlab-comment

# Skip Terraform source code analysis (faster, less context)
python app/terraform_plan_analyzer.py --plan <plan_file.json> --skip-code

# Limit number of Terraform files included for context
python app/terraform_plan_analyzer.py --plan <plan_file.json> --max-files 10
```

### Docker Build and Run

```bash
# Build Docker image
docker build -t terraform-plan-analyzer .

# Run in container (dry-run)
docker run -v $(pwd):/workspace terraform-plan-analyzer

# Run with environment variables
docker run -e GEMINI_API_KEY=<key> -e SEND_TO_GEMINI=true \
  -v $(pwd):/workspace terraform-plan-analyzer
```

## Architecture Overview

### Core Components

1. **terraform_plan_analyzer.py** - Main analysis engine with these key responsibilities:
   - Parses Terraform `plan.json` files to extract resource changes
   - **Automatically redacts 16+ sensitive field patterns** (passwords, API keys, secrets, tokens, certificates, SSH keys, etc.)
   - Identifies sensitive paths marked by Terraform (`after_sensitive`, `before_sensitive`)
   - Formats resource changes in Terraform-like syntax with provider documentation URLs
   - Reads Terraform source files (`.tf`) for additional context (optional)
   - Estimates token count and warns if approaching Gemini's context window limits
   - Sends formatted prompt to Gemini API for AI-powered analysis
   - Posts analysis results as comments on GitLab merge requests (optional)

2. **prompt.txt** - Instructions for Gemini AI model that defines the analysis structure:
   - 7-point analysis per resource (Change Summary, Suggested Tests, Risk Analysis, Benefits, Affected Resources, Recommendation)
   - Markdown format with collapsible sections for GitLab MR display
   - Footnote system for documentation references
   - Severity-based recommendations (warning, caution, important, tip, note)

3. **entrypoint.sh** - Docker entry point that:
   - Installs Python dependencies
   - Configures environment variables with defaults
   - Validates required environment variables (GEMINI_API_KEY if sending to Gemini)
   - Patches the Python script to find prompt.txt in the container
   - Ensures output files exist for CI/CD artifact collection

### Data Flow

```
Terraform Plan JSON
  ↓
Parse & Extract Changes
  ↓
Sanitize Sensitive Values (automatic redaction)
  ↓
Format Changes (Terraform syntax + doc URLs)
  ↓
Read Source Code (optional .tf files)
  ↓
Create Prompt (inject changes + instructions)
  ↓
Estimate Tokens (check context limits)
  ↓
Send to Gemini (or dry-run)
  ↓
Post to GitLab MR (optional)
  ↓
Output Files: terraform_analysis.md, prompt_output.txt, sanitized_plan.json
```

### Environment Variables

**Required (if using Gemini):**
- `GEMINI_API_KEY` - Google Gemini API key

**Required (if posting to GitLab):**
- `GITLAB_TOKEN` - GitLab API token with MR comment permissions
- `CI_MERGE_REQUEST_IID` - GitLab MR ID (auto-set in CI)
- `CI_PROJECT_ID` - GitLab project ID (auto-set in CI)
- `CI_API_V4_URL` - GitLab API URL (auto-set in CI)

**Optional:**
- `PLAN_FILE` - Path to Terraform plan.json (default: `tf_output.json`)
- `OUTPUT_FILE` - Analysis output file (default: `terraform_analysis.md`)
- `GEMINI_MODEL` - Model to use (default: `gemini-2.0-flash`)
- `TF_DIR` - Directory with Terraform files (default: `.`)
- `SKIP_CODE` - Skip reading .tf files (default: `false`)
- `MAX_FILES` - Limit number of .tf files analyzed
- `SAVE_SANITIZED` - Output sanitized plan to file
- `SAVE_PROMPT` - Output generated prompt to file
- `SEND_TO_GEMINI` - Actually call Gemini API (default: `false`)
- `GITLAB_COMMENT` - Post results to GitLab MR (default: `false`)

### Provider Support

The tool supports 10+ Terraform providers with automatic documentation URL generation:
- AWS, Google Cloud, Azure
- Fastly, NewRelic, DigitalOcean
- Cloudflare, Datadog
- Kubernetes, Helm

Provider documentation URLs are automatically injected into the analysis prompt to give Gemini context about each resource type.

### Security Features

1. **Automatic Sensitive Data Redaction** - The following patterns are automatically detected and redacted:
   - `password`, `secret`, `token`, `api_key`, `access_key`
   - `private_key`, `client_secret`, `auth`, `credential`
   - `passphrase`, `certificate`, `ssh_key`, `license_key`
   - Plus 4+ additional patterns

2. **Terraform-Native Sensitivity Markers** - Respects Terraform's `after_sensitive` and `before_sensitive` fields

3. **No Credentials in Output** - Sanitized plans and prompts never contain redacted values

## GitLab CI Integration

### Using the Template

Projects can use this analyzer by including the template in their `.gitlab-ci.yml`:

```yaml
include:
  - project: 'path/to/terraform-plan-analyzer'
    file: 'template/terraform-plan-analysis.gitlab-ci.yml'
```

### Pipeline Requirements

The analysis job expects:
1. A previous job named "build plan" that generates `tf_output.json`
2. Triggers only on merge requests
3. Outputs 3 artifacts: `terraform_analysis.md`, `prompt_output.txt`, `sanitized_plan.json`

### CI/CD Variables to Configure

Set these in GitLab project/group settings:
- `GEMINI_API_KEY` - Required for AI analysis
- `GITLAB_TOKEN` - Required for posting MR comments

## Key Implementation Details

### Token Context Management

- Gemini 1.5 Flash/Pro and 2.0 models: 1,000,000 token context window
- Token estimation: ~0.25 tokens per character
- The tool warns and suggests remediation if prompt exceeds limits (use `--max-files` or `--skip-code`)

### Terraform Source Code Handling

- Recursively reads all `.tf` files in `--tf-dir` for context
- Includes in prompt to help Gemini understand the infrastructure architecture
- Can be disabled with `--skip-code` flag to reduce context size
- Can be limited with `--max-files N` to include only first N files

### Change Detection

The analyzer identifies and categorizes:
- **Create** - New resources being added
- **Update** - Existing resources being modified
- **Delete** - Resources being removed
- **No-op** - Resources that won't change (not included in analysis)

For each change, it extracts:
- Resource type and name
- Before/after values (with sensitive data redacted)
- Which specific attributes are changing

### Output Format

The analysis is formatted as Markdown with:
- Collapsible `<details>` sections per resource
- Severity indicators (`[!warning]`, `[!caution]`, `[!important]`, `[!tip]`, `[!note]`)
- Emoji indicators for quick visual scanning
- Footnote references to provider documentation
- Overall recommendation with checklist of review items
