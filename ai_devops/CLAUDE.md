# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Google Cloud Run service that provides automated code review for GitLab merge requests using Google's Gemini Pro model via Vertex AI. It receives GitLab webhook events, enqueues processing tasks via Cloud Tasks, and posts detailed code review comments and summaries back to merge requests.

## Architecture

### Request Flow
1. **Webhook Receiver** (`/webhook` endpoint): Receives GitLab MR webhooks, validates the secret token, and enqueues a Cloud Task
2. **Task Handler** (`/process_mr` endpoint): Processes the enqueued task asynchronously, fetches diffs, calls Gemini for review, and posts comments back to GitLab
3. **Cloud Tasks**: Decouples webhook reception from processing to avoid GitLab webhook timeouts

### Key Components

**Flask Application** ([main.py](app/main.py))
- Two main endpoints: `/webhook` (webhook receiver) and `/process_mr` (task processor)
- Uses OIDC token authentication for Cloud Tasks
- Runs on Gunicorn with 290-second timeout (configured in [Dockerfile](Dockerfile))

**Prompt System** ([app/prompts/](app/prompts/))
- `default.md`: Contains three parsed sections (summary_system, review, summary_user)
- Project-specific prompts: Named as `{project_path_with_namespace}.md` (slashes replaced with underscores)
- Example: `lifechurch_io_digital-product_data_data-operations_data-models_lc-data-warehouse.md` for the lc-data-warehouse project
- Prompts are loaded at startup and parsed by markers in `load_and_parse_default_prompts()`

**Core Logic Functions**
- `handle_merge_request_logic()`: Main processing flow, posts errors to MR if failures occur
- `get_code_review_response_from_gemini()`: Fetches structured JSON review from Gemini
- `get_code_review_summary_from_gemini()`: Generates markdown summary of all comments
- `deduplicate_gemini_responses()`: Removes duplicate comments, keeping most comprehensive
- `post_diff_discussion()`: Posts inline comments to specific diff lines, checks for existing discussions to avoid duplicates
- `build_position()`: Constructs GitLab position objects for inline comments using diff_refs (base_sha, head_sha, start_sha)

### Diff Handling
- **For `open`/`reopen` actions**: Fetches full MR diffs via `get_merge_diffs()`
- **For `update` actions**: Fetches only latest commit diff via `get_latest_commit_diff()`
- Each diff is enriched with `full_file_content` from the source branch for context
- Diff content is decoded from bytes to UTF-8 strings before sending to Gemini

### Line Number Convention
- **1-based indexing**: All line numbers (new_line, old_line) use 1-based indexing throughout the codebase
- Gemini is instructed to return 1-based line numbers in its JSON schema
- When no valid line number exists, use `None` (not 0 or -1)

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r app/requirements.txt

# Run locally with Flask dev server
cd app
python main.py  # Runs on port 8080

# Run with Gunicorn (production-like)
gunicorn --bind 0.0.0.0:8080 --timeout 290 main:app
```

### Testing with Docker
```bash
# Build the Docker image
docker build -t code-analyzer .

# Run container locally
docker run -p 8080:8080 \
  -e GITLAB_PAT_SECRET_ID=<your-token> \
  -e GITLAB_WEBHOOK_SECRET_ID=<your-secret> \
  -e PROJECT_ID=<gcp-project-id> \
  -e GITLAB_URL=https://gitlab.com \
  code-analyzer
```

### CI/CD Deployment
The [.gitlab-ci.yml](.gitlab-ci.yml) pipeline automatically:
1. **Build stage**: Uses Kaniko to build and push Docker image to GCR
2. **Setup stage**: Creates Cloud Tasks queue (idempotent)
3. **Deploy stage**: Deploys to Cloud Run with environment variables

Deploy happens automatically on pushes to `main` branch using the `rock-rms` runner.

## Environment Variables

**Required:**
- `GITLAB_PAT_SECRET_ID`: GitLab Personal Access Token with `api` scope
- `GITLAB_WEBHOOK_SECRET_ID`: Secret token matching GitLab webhook configuration
- `PROJECT_ID`: GCP Project ID for Vertex AI and Cloud Logging
- `CLOUD_TASKS_QUEUE_PATH`: Full queue path (e.g., `projects/PROJECT_ID/locations/REGION/queues/QUEUE_NAME`)
- `SERVICE_ACCOUNT_EMAIL`: Service account email for Cloud Tasks OIDC authentication

**Optional:**
- `DEBUG_MODE`: Set to `true` for verbose logging (default: `false`)
- `GEMINI_MODEL`: Model ID to use (default: `gemini-2.5-pro`)
- `GITLAB_URL`: GitLab instance URL (default: `https://gitlab.com`)
- `CLOUD_TASKS_LOCATION`: Region for Cloud Tasks (e.g., `us-central1`)
- `CLOUD_TASKS_QUEUE_NAME`: Queue name (e.g., `code-analyzer`)

## Adding Project-Specific Review Prompts

To create custom review instructions for a specific GitLab project:

1. Get the project's `path_with_namespace` (e.g., `lifechurch/io/digital-product/data/data-operations/data-models/lc-data-warehouse`)
2. Replace slashes with underscores: `lifechurch_io_digital-product_data_data-operations_data-models_lc-data-warehouse`
3. Create `app/prompts/{sanitized_name}.md` with your custom review prompt
4. The system will automatically use this prompt instead of `default.md` for that project

The prompt should follow the same structure as `default.md` and will be used for the review phase (not summary).

## GitLab API Interaction

**Authentication**: Uses python-gitlab library with PAT
**Key Operations**:
- Fetch project: `gl.projects.get(project_id)`
- Fetch MR: `project.mergerequests.get(mr_iid)`
- Get diffs: `mr.changes()` or `commit.diff()`
- Create discussions: `mr.discussions.create({'body': comment, 'position': position})`
- Create notes: `mr.notes.create({'body': note})`
- Check existing discussions: `mr.discussions.list(get_all=True)` to avoid duplicates

## Gemini/Vertex AI Integration

**Model**: Configurable via `GEMINI_MODEL` env var (default: `gemini-2.5-pro`)
**Location**: `us-central1` (hardcoded in [main.py:75](app/main.py#L75))
**Response Format**: JSON with strict schema enforcement
**Review Schema**: Array of response objects with `new_line`, `old_line`, `new_file_path`, `comment`, `severity`
**Summary**: Plain markdown text (no schema)

**Important Notes:**
- Diff content is sanitized before sending (full_file_content removed, bytes decoded)
- Large diffs are truncated to 50,000 chars
- Response validation ensures line numbers are integers or None

## Error Handling

- Errors during MR processing post a formatted error comment to the MR with stack trace (truncated to 15,000 chars)
- Webhook validation failures return 403
- Task processing failures return 500 to trigger Cloud Tasks retry
- All exceptions are logged with full traceback when `DEBUG_MODE=true`

## Important Constraints

- **No merge action processing**: MRs with action `merge` are skipped (no review)
- **Update action**: Only reviews latest commit, not full MR diff
- **Cloud Run timeout**: 290 seconds (set in Gunicorn CMD)
- **Comment deduplication**: Uses (file_path, new_line, old_line) as key, keeps longest comment
- **Discussion position**: Requires valid diff_refs (base_sha, head_sha, start_sha) from MR object
- **Existing discussion check**: Before posting, checks if discussion already exists at same position to prevent duplicates

## Logging

Uses Google Cloud Logging with StructuredLogHandler for GCP environments. Falls back to standard logging if GCP is unavailable.

**Log Levels:**
- INFO: Standard operations (webhook received, task enqueued, comments posted)
- DEBUG: Verbose output (full prompts, full responses) - only when `DEBUG_MODE=true`
- WARNING: Non-critical issues (no diffs found, empty responses)
- ERROR: Failures with stack traces

## Testing Considerations

When testing changes:
1. Use a test GitLab project with test MRs
2. Set `DEBUG_MODE=true` to see full prompts and responses in logs
3. Check Cloud Logging for detailed execution traces
4. Verify discussions are posted to correct lines with proper position objects
5. Test with renamed files, deleted files, and new files
6. Ensure duplicate comment detection works across MR updates
