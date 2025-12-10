import json
import os
import hashlib
from dotenv import load_dotenv
from gitlab import Gitlab
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel
from google.cloud import logging as gcp_logging
from google.cloud.logging.handlers import StructuredLogHandler # Import StructuredLogHandler
from google.cloud import tasks_v2
import logging # Import standard logging
from flask import Flask, request, Response
import traceback # For detailed error logging

# --- Global Initializations ---

# Load environment variables (ideally done once at startup)
load_dotenv()
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true" # Default to False if not set
MODEL_ID = os.environ.get("GEMINI_MODEL", "gemini-2.5-pro") # Use env var or default
GITLAB_WEBHOOK_SECRET = os.environ.get('GITLAB_WEBHOOK_SECRET_ID')
GITLAB_PAT_SECRET = os.environ.get('GITLAB_PAT_SECRET_ID')
PROJECT_ID = os.environ.get('PROJECT_ID') # GCP Project ID
GITLAB_URL = os.environ.get('GITLAB_URL', "https://gitlab.com") # Allow configurable GitLab URL
# Cloud Tasks variables (expecting full path, location, and queue name)
CLOUD_TASKS_QUEUE_PATH = os.environ.get('CLOUD_TASKS_QUEUE_PATH') # e.g., projects/PROJECT_ID/locations/REGION/queues/QUEUE_NAME
CLOUD_TASKS_LOCATION = os.environ.get('CLOUD_TASKS_LOCATION') # e.g., us-central1
CLOUD_TASKS_QUEUE_NAME = os.environ.get('CLOUD_TASKS_QUEUE_NAME') # e.g., code-analyzer
SERVICE_ACCOUNT_EMAIL = os.environ.get('SERVICE_ACCOUNT_EMAIL') # Required for Cloud Tasks HTTP target

# Initialize Flask App
app = Flask(__name__)


# Initialize GCP Logging Client (once)
logger = None # Initialize logger to None first
try:
    if PROJECT_ID:
        # Use StructuredLogHandler for better integration in GCP environments
        handler = StructuredLogHandler()
        # Get the root logger used by Flask/Gunicorn
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO if not DEBUG_MODE else logging.DEBUG) # Set level based on DEBUG_MODE
        # Remove existing handlers if any (important for Cloud Run reloads)
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
        root_logger.addHandler(handler)
        logger = root_logger # Use the configured root logger
        logger.info("StructuredLogHandler initialized and attached to root logger.")
    else:
        raise ValueError("PROJECT_ID environment variable not set.")
except Exception as e:
    # Fallback logger if GCP client fails
    logging.basicConfig(level=logging.INFO if not DEBUG_MODE else logging.DEBUG)
    logger = logging.getLogger("code-analyzer-cloudrun-fallback")
    logger.error(f"Failed to initialize GCP Logging client: {e}. Using standard logger.", exc_info=True)

# Initialize GitLab Client (once)
gl = None # Initialize gl to None
try:
    if GITLAB_PAT_SECRET:
        gl = Gitlab(GITLAB_URL, private_token=GITLAB_PAT_SECRET)
        gl.auth() # Verify authentication early
        logger.info("GitLab client initialized and authenticated successfully.")
    else:
        logger.warning("GITLAB_PAT_SECRET not found. GitLab client not initialized.")
except Exception as e:
    logger.error(f"Error initializing GitLab client: {e}. GitLab features may fail.", exc_info=True)
    gl = None # Ensure gl is None if initialization fails

# Initialize Vertex AI Client (once)
vertex_ai_initialized = False
try:
    if PROJECT_ID:
        vertexai.init(project=PROJECT_ID, location="us-central1")
        logger.info("Vertex AI client initialized successfully.")
        vertex_ai_initialized = True
    else:
        logger.warning("PROJECT_ID environment variable not set. Vertex AI client not initialized.")
except Exception as e:
    logger.error(f"Error initializing Vertex AI client: {e}. AI features may fail.", exc_info=True)

# Initialize Cloud Tasks Client (once)
tasks_client = None
try:
    tasks_client = tasks_v2.CloudTasksClient()
    logger.info("Cloud Tasks client initialized successfully.")
except Exception as e:
    logger.error(f"Error initializing Cloud Tasks client: {e}. Task enqueuing will fail.", exc_info=True)


# --- New Prompt Loading System ---
PARSED_DEFAULT_PROMPTS = {
    "review": "Default review prompt not loaded.",
    "summary_system": "Default summary system instructions not loaded.",
    "summary_user": "Default summary user prompt not loaded."
}

def load_and_parse_default_prompts(logger_obj: logging.Logger):
    """Loads and parses the app/prompts/default.md file into distinct prompt sections."""
    global PARSED_DEFAULT_PROMPTS
    default_prompt_path = "prompts/default.md"
    try:
        with open(default_prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger_obj.info(f"Successfully loaded default prompt file: {default_prompt_path}")

        # Define markers to split the content
        # Marker 1: End of summary system instructions, start of review prompt
        marker1_text = "The Changes will be provided as a JSON Array of Changes."
        # Marker 2: End of review prompt, start of summary user prompt
        marker2_text = "Summarize the following code review comments, which are provided in JSON format:"

        parts = content.split(marker1_text, 1)
        if len(parts) < 2:
            logger_obj.error(f"Marker 1 ('{marker1_text[:50]}...') not found in {default_prompt_path}. Cannot parse prompts.")
            return

        summary_system_text = parts[0].strip()
        remaining_after_marker1 = parts[1]

        parts2 = remaining_after_marker1.split(marker2_text, 1)
        if len(parts2) < 2:
            logger_obj.error(f"Marker 2 ('{marker2_text[:50]}...') not found after Marker 1 in {default_prompt_path}. Cannot parse prompts.")
            return

        review_text = (marker1_text + parts2[0]).strip() # Prepend marker1_text as it's part of review prompt
        summary_user_text = (marker2_text + parts2[1]).strip() # Prepend marker2_text as it's part of summary user prompt

        PARSED_DEFAULT_PROMPTS["summary_system"] = summary_system_text
        PARSED_DEFAULT_PROMPTS["review"] = review_text
        PARSED_DEFAULT_PROMPTS["summary_user"] = summary_user_text

        logger_obj.info("Successfully parsed default prompts from default.md.")
        if DEBUG_MODE:
            logger_obj.debug(f"Parsed Review Prompt (first 100 chars): {PARSED_DEFAULT_PROMPTS['review'][:100]}...")
            logger_obj.debug(f"Parsed Summary System (first 100 chars): {PARSED_DEFAULT_PROMPTS['summary_system'][:100]}...")
            logger_obj.debug(f"Parsed Summary User (first 100 chars): {PARSED_DEFAULT_PROMPTS['summary_user'][:100]}...")

    except FileNotFoundError:
        logger_obj.error(f"Default prompt file not found: {default_prompt_path}. Using fallback strings.")
    except Exception as e:
        logger_obj.error(f"Failed to load or parse default prompt file {default_prompt_path}: {e}", exc_info=True)

def get_review_prompt(project_path_with_namespace: str, logger_obj: logging.Logger) -> str:
    """
    Gets the appropriate review prompt.
    Uses project-specific if available, otherwise falls back to the default review prompt.
    """
    try:
        # Sanitize project path for filesystem: replace / with _
        safe_project_name = project_path_with_namespace.replace('/', '_')
        project_prompt_filename = f"{safe_project_name}.md"
        project_prompt_path = os.path.join("prompts", project_prompt_filename)

        if os.path.exists(project_prompt_path):
            with open(project_prompt_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger_obj.info(f"Using project-specific review prompt for '{project_path_with_namespace}' from {project_prompt_path}")
            return content.strip()
        else:
            logger_obj.info(f"No project-specific review prompt found for '{project_path_with_namespace}'. Using default review prompt.")
            return PARSED_DEFAULT_PROMPTS["review"]
    except Exception as e:
        logger_obj.error(f"Error getting review prompt for '{project_path_with_namespace}': {e}. Falling back to default.", exc_info=True)
        return PARSED_DEFAULT_PROMPTS["review"]

def get_summary_prompts(logger_obj: logging.Logger) -> tuple[str, str]:
    """
    Gets the default summary system instructions and user prompt.
    (Currently no project-specific overrides for summaries).
    """
    logger_obj.info("Using default summary system instructions and user prompt.")
    return PARSED_DEFAULT_PROMPTS["summary_system"], PARSED_DEFAULT_PROMPTS["summary_user"]

# Load and parse default prompts at startup
if logger: # Ensure logger is initialized
    load_and_parse_default_prompts(logger)
else: # Should not happen if logger initialization is robust
    logging.basicConfig(level=logging.INFO)
    fallback_startup_logger = logging.getLogger("startup-prompt-loader")
    fallback_startup_logger.warning("Main logger not available at prompt loading. Using temporary logger.")
    load_and_parse_default_prompts(fallback_startup_logger)

# --- End Global Initializations ---

# --- Webhook Endpoint (/webhook) ---
@app.route("/webhook", methods=["POST"])
def webhook_receiver():
    """
    Receives GitLab webhooks, validates them, and enqueues a task for processing.
    Responds quickly to GitLab to avoid timeouts.
    """
    logger.info("Webhook received at /webhook")

    # 1. Verify Request Authenticity (using Secret Token from Header)
    gitlab_token = request.headers.get('X-Gitlab-Token')
    if not GITLAB_WEBHOOK_SECRET:
        logger.error("GITLAB_WEBHOOK_SECRET environment variable not set. Cannot verify webhook.")
        return "Internal Server Error: Webhook secret not configured", 500

    if gitlab_token != GITLAB_WEBHOOK_SECRET:
        logger.warning(f"Invalid or missing X-Gitlab-Token received.")
        if DEBUG_MODE:
             logger.debug(f"Received token: {gitlab_token}")
        return "Invalid token", 403
    logger.info("Webhook token verified successfully.")

    # 2. Check Event Type (using header) - Basic check before parsing
    event_type = request.headers.get('X-Gitlab-Event')
    logger.info(f"Event type from header: {event_type}")
    if event_type != "Merge Request Hook":
        logger.info(f"Unsupported event type: {event_type}. Skipping.")
        return "Unsupported event type", 200 # Acknowledge unsupported events

    # 3. Parse Payload
    try:
        payload = request.get_json()
        if not payload:
            raise ValueError("Payload is empty or not valid JSON.")
        mr_iid = payload.get('object_attributes', {}).get('iid', 'N/A')
        project_id_from_payload = payload.get('project', {}).get('id', 'N/A') # Rename to avoid conflict
        logger.info(f"Payload received for MR !{mr_iid} in project {project_id_from_payload}")
        if DEBUG_MODE:
            logger.debug(f"Payload sample (first 500 chars): {json.dumps(payload)[:500]}...")
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {e}", exc_info=True)
        if DEBUG_MODE:
            try:
                raw_body = request.get_data(as_text=True)
                logger.debug(f"Raw request body on parse failure: {raw_body[:1000]}...")
            except Exception as read_err:
                logger.error(f"Failed to read raw request body: {read_err}")
        return "Bad Request: Invalid JSON payload", 400

    # 4. Enqueue Task for Processing
    if not tasks_client:
        logger.critical("Cloud Tasks client is not initialized. Cannot enqueue task.")
        return "Internal Server Error: Task client not configured", 500
    if not CLOUD_TASKS_QUEUE_PATH:
        logger.critical("CLOUD_TASKS_QUEUE_PATH environment variable not set. Cannot enqueue task.")
        return "Internal Server Error: Task queue path not configured", 500
    if not SERVICE_ACCOUNT_EMAIL:
        logger.critical("SERVICE_ACCOUNT_EMAIL environment variable not set. Cannot enqueue task with HTTP target.")
        return "Internal Server Error: Service account email not configured for tasks", 500

    try:
        task = {
            "http_request": { # Use http_request for Cloud Run targets
                "http_method": tasks_v2.HttpMethod.POST,
                # Ensure the URL starts with https for OIDC authenticated tasks
                "url": request.url_root.replace("http://", "https://", 1) + "process_mr",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode("utf-8"),
                # OIDC token is needed to authenticate the task request to the Cloud Run service
                "oidc_token": {
                    "service_account_email": SERVICE_ACCOUNT_EMAIL,
                },
            }
        }

        # Create task
        response = tasks_client.create_task(request={"parent": CLOUD_TASKS_QUEUE_PATH, "task": task})
        logger.info(f"Task {response.name} enqueued for MR !{mr_iid} in project {project_id_from_payload}.")
        return "Task enqueued", 202 # Accepted

    except Exception as e:
        logger.error(f"Failed to enqueue task for MR !{mr_iid}: {e}", exc_info=True)
        return "Internal Server Error: Failed to enqueue task", 500

# --- Task Handler Endpoint (/process_mr) ---
@app.route("/process_mr", methods=["POST"])
def process_merge_request_task():
    """
    Handles the asynchronous processing of a merge request event received from Cloud Tasks.
    """
    logger.info("Received task at /process_mr")

    # Task requests are authenticated via OIDC token, no need for X-Gitlab-Token check here.

    # 1. Parse Payload from Task
    try:
        payload = request.get_json()
        if not payload:
            raise ValueError("Payload is empty or not valid JSON in task.")
        mr_iid = payload.get('object_attributes', {}).get('iid', 'N/A')
        project_id_from_payload = payload.get('project', {}).get('id', 'N/A')
        logger.info(f"Processing task for MR !{mr_iid} in project {project_id_from_payload}")
        if DEBUG_MODE:
            logger.debug(f"Task payload sample (first 500 chars): {json.dumps(payload)[:500]}...")
    except Exception as e:
        logger.error(f"Failed to parse JSON payload from task: {e}", exc_info=True)
        # Return 500 to signal Cloud Tasks to retry (if configured)
        return "Bad Request: Invalid JSON payload in task", 500

    # --- GitLab and Vertex AI Client Checks ---
    if gl is None:
        logger.critical("GitLab client is not initialized in task handler. Cannot proceed.")
        return "Internal Server Error: GitLab client not configured", 500

    if not vertex_ai_initialized:
        logger.warning("Vertex AI client is not initialized. AI features disabled for this task execution.")
        # Decide how to handle this - Gemini calls will fail later.

    # --- Process the Merge Request ---
    try:
        # Re-check required fields after successful parsing
        if project_id_from_payload == 'N/A' or mr_iid == 'N/A':
             logger.error("Missing project_id or merge_request_iid in parsed task payload.")
             return "Bad Request: Missing required payload attributes in task", 400 # 400 Bad Request - won't retry

        logger.info(f"Processing task payload for MR !{mr_iid} in project {project_id_from_payload}")

        # Call the core logic function (passing the logger)
        handle_merge_request_logic(payload, gl, logger)

        logger.info(f"Task processing complete for MR !{mr_iid}.")
        return "OK", 200 # Indicate successful processing to Cloud Tasks

    except Exception as e:
        # Log the full traceback for debugging
        logger.error(f"Unhandled error processing task payload for MR !{mr_iid}: {e}", exc_info=True)
        # Return 500 to potentially trigger retries
        return "Internal Server Error during task processing", 500


# --- Core Logic Functions (Refactored) ---

def handle_merge_request_logic(payload, gl_client, logger_obj):
    """
    Core logic to handle merge request events. Includes error handling to post back to MR.
    """
    project = None
    mr = None
    try:
        project_id = payload["project"]["id"]
        merge_request_iid = payload["object_attributes"]["iid"]
        action = payload["object_attributes"]["action"]
        logger_obj.info(f"Handling MR {merge_request_iid} in project {project_id}. Action: {action}")

        project = gl_client.projects.get(project_id)
        mr = project.mergerequests.get(merge_request_iid)
        logger_obj.info(f"Fetched project {project.path_with_namespace} and MR !{mr.iid} ('{mr.title}')")

        if action == "merge":
            logger_obj.info(f"MR !{mr.iid} action is 'merge'. No code review action taken.")
            return

        diffs = []
        if action == "update" and "oldrev" in payload["object_attributes"]:
            logger_obj.info(f"MR !{mr.iid} action is 'update'. Performing code review on latest commit.")
            diffs = get_latest_commit_diff(payload, project, logger_obj)
            logger_obj.info(f"Retrieved {len(diffs)} diffs for latest commit.")
        elif action in ["open", "reopen"]:
            logger_obj.info(f"MR !{mr.iid} action is '{action}'. Performing full code review.")
            diffs = get_merge_diffs(mr, project, logger_obj)
            logger_obj.info(f"Retrieved {len(diffs)} total diffs for MR.")
        else:
            logger_obj.info(f"Merge request action '{action}' for MR !{mr.iid} not handled.")
            return

        if not diffs:
            logger_obj.warning(f"No diffs found for review in MR !{mr.iid}. Skipping.")
            return

        response = get_code_review_response_from_gemini(diffs, logger_obj, payload, project, mr)
        if not response or 'responses' not in response or not response['responses']:
            logger_obj.warning(f"No feedback provided by Gemini for MR !{mr.iid}")
            return

        comments = response.get('responses', [])
        logger_obj.info(f"Received {len(comments)} review responses from Gemini. Processing...")
        comments = deduplicate_gemini_responses(comments, logger_obj)
        logger_obj.info(f"Posting {len(comments)} deduplicated comments for MR !{mr.iid}")

        for line_comment in comments:
            post_diff_discussion(mr, line_comment, logger_obj)

        response_summary = get_code_review_summary_from_gemini(comments, logger_obj, payload, project, mr)
        if response_summary:
            post_merge_request_summary(mr, response_summary, logger_obj)
        else:
            logger_obj.warning(f"No summary generated for MR !{mr.iid}")

    except Exception as e:
        logger_obj.error(f"An error occurred during merge request processing for MR !{payload.get('object_attributes', {}).get('iid', 'N/A')}: {e}", exc_info=True)
        if mr: # If we have the MR object, post a comment
            tb_str = traceback.format_exc()
            post_error_comment_to_mr(mr, tb_str, logger_obj)
        raise # Re-raise the exception to ensure the task fails and can be retried/monitored.


def post_error_comment_to_mr(mr, stack_trace, logger_obj):
    """Posts a formatted error message to the merge request."""
    try:
        error_message = (
            "**Code Analyzer Bot encountered an error and could not complete the review.**\n\n"
            "An internal error occurred. Please check the logs for more details.\n\n"
            "```\n"
            f"{stack_trace}\n"
            "```"
        )
        # Truncate to avoid hitting GitLab API limits
        max_len = 15000
        if len(error_message) > max_len:
            error_message = error_message[:max_len] + "\n... (stack trace truncated) ...\n```"

        mr.notes.create({'body': error_message})
        logger_obj.info(f"Successfully posted error comment to MR !{mr.iid}")
    except Exception as e:
        logger_obj.error(f"Failed to post error comment to MR !{mr.iid}: {e}", exc_info=True)


def deduplicate_gemini_responses(responses, logger_obj):
    """
    Deduplicates Gemini responses by selecting the most comprehensive comment for each line.
    """
    best_comments = {}
    logger_obj.info(f"Deduplicating {len(responses)} responses from Gemini")

    for response in responses:
        # Ensure response is a dictionary and has expected keys
        if not isinstance(response, dict):
            logger_obj.warning(f"Skipping non-dictionary item during deduplication: {response}")
            continue

        new_file_path = response.get('new_file_path', '')
        new_line = response.get('new_line', -1)
        old_line = response.get('old_line', -1)
        comment_text = response.get('comment', '')

        # Validate types
        if not all([
            isinstance(new_file_path, str),
            isinstance(new_line, (int, type(None))),
            isinstance(old_line, (int, type(None))),
            isinstance(comment_text, str)
        ]):
             logger_obj.warning(f"Skipping item with invalid types during deduplication: {response}")
             continue

        location_key = (new_file_path, new_line, old_line)
        existing = best_comments.get(location_key)

        if not existing or len(comment_text) > len(existing.get('comment', '')):
            best_comments[location_key] = response
            if DEBUG_MODE:
                logger_obj.debug(f"Selected comment for {location_key}: {comment_text[:100]}...")

    deduplicated = list(best_comments.values())
    logger_obj.info(f"Deduplicated to {len(deduplicated)} responses")
    return deduplicated


def build_position(review_item, mr, logger_obj):
    """Builds a position object for a thread based on the review item."""
    new_line = review_item.get('new_line')
    old_line = review_item.get('old_line')
    new_file_path = review_item.get('new_file_path')
    old_file_path = review_item.get('old_file_path', new_file_path)

    if not new_file_path:
        return None

    new_line = int(new_line) if isinstance(new_line, (int, float, str)) and str(new_line).isdigit() else None
    old_line = int(old_line) if isinstance(old_line, (int, float, str)) and str(old_line).isdigit() else None

    if not hasattr(mr, 'diff_refs') or not mr.diff_refs:
        logger_obj.warning(f"Missing diff_refs on MR object !{mr.iid}. Cannot build precise position.")
        return None

    base_sha = mr.diff_refs.get('base_sha')
    head_sha = mr.diff_refs.get('head_sha')
    start_sha = mr.diff_refs.get('start_sha')

    if not base_sha or not head_sha or not start_sha:
        logger_obj.warning(f"Missing SHA values in diff_refs for MR !{mr.iid}. Cannot build precise position.")
        return None

    position = {
        'position_type': 'text',
        'new_path': new_file_path,
        'old_path': old_file_path,
        'base_sha': base_sha,
        'head_sha': head_sha,
        'start_sha': start_sha
    }

    line_range = None
    if new_line is not None:
        position['new_line'] = new_line
        line_range_str = f"new_{new_line}"
    elif old_line is not None:
        position['old_line'] = old_line
        line_range_str = f"old_{old_line}"
    else:
        orig_new_line = review_item.get('new_line')
        orig_old_line = review_item.get('old_line')
        logger_obj.warning(f"No valid line numbers (new_line={orig_new_line}, old_line={orig_old_line}) for position in {new_file_path}, MR !{mr.iid}.")
        return None

    return position


def post_diff_discussion(mr, line_comment, logger_obj):
    """
    Posts a code review comment as a discussion on a specific line.
    """
    try:
        comment_text = line_comment.get('comment', '').strip()
        file_path = line_comment.get('new_file_path', 'unknown file')
        new_line_num = line_comment.get('new_line', -1) # Keep as -1 if missing
        old_line_num = line_comment.get('old_line', -1) # Keep as -1 if missing

        # Determine display line more robustly (using 1-based numbers or None)
        display_line = 'N/A'
        if new_line_num is not None: # Check if it's not None (already 1-based)
            display_line = f"new:{new_line_num}"
        elif old_line_num is not None: # Check if it's not None (already 1-based)
            display_line = f"old:{old_line_num}"

        if not comment_text:
            logger_obj.warning(f"Skipping empty comment for {file_path} line ~{display_line} in MR !{mr.iid}")
            return

        target_position = build_position(line_comment, mr, logger_obj)

        if target_position:
            # --- Check for existing discussions at the same position ---
            try:
                # Fetch all discussions for the MR. Use get_all=True for pagination.
                existing_discussions = mr.discussions.list(get_all=True)
                found_existing = False
                for existing_disc in existing_discussions:
                    # Ensure the existing discussion has a position and it's 'text' type
                    # Also check if it's an active discussion (not resolved, though API might not filter easily)
                    if hasattr(existing_disc, 'position') and existing_disc.position and existing_disc.position.get('position_type') == 'text':
                        existing_pos = existing_disc.position
                        # Compare relevant position attributes (paths and lines)
                        # Note: Lines in target_position and existing_pos should both be 1-based
                        if (target_position.get('new_path') == existing_pos.get('new_path') and
                            target_position.get('old_path') == existing_pos.get('old_path') and
                            target_position.get('new_line') == existing_pos.get('new_line') and
                            target_position.get('old_line') == existing_pos.get('old_line')):
                            # Optional: Add SHA comparison here if needed for more precision,
                            # but be aware SHAs might change with rebases/updates.
                            # and target_position.get('base_sha') == existing_pos.get('base_sha')
                            # and target_position.get('head_sha') == existing_pos.get('head_sha')
                            # and target_position.get('start_sha') == existing_pos.get('start_sha')):

                            logger_obj.info(f"Discussion already exists at position {file_path}:{display_line} (Discussion ID: {existing_disc.id}). Skipping duplicate post for MR !{mr.iid}.")
                            found_existing = True
                            break # Stop checking once a match is found

                if found_existing:
                    return # Skip posting the new discussion if a duplicate was found
            except Exception as check_err:
                # Log the error but proceed with posting to avoid losing the comment due to a check failure
                logger_obj.error(f"Error checking for existing discussions for MR !{mr.iid} at {file_path}:{display_line}: {check_err}. Proceeding to post comment.", exc_info=True)
            # --- End check for existing discussions ---

            # If no existing discussion was found (or check failed), proceed to post
            # Truncate long comments if necessary (GitLab might have limits)
            max_comment_length = 10000 # Example limit, adjust if needed
            truncated_comment = (comment_text[:max_comment_length] + '...') if len(comment_text) > max_comment_length else comment_text

            # Post the new discussion
            result = mr.discussions.create({
                'body': truncated_comment,
                'position': target_position # Use the built position
            })
            logger_obj.info(f"Posted new discussion {result.id} for line {display_line} in {file_path} (MR !{mr.iid})")
        else:
            # Handle case where position couldn't be built (post as general note)
            logger_obj.warning(f"Could not build valid position for comment on {file_path} line ~{display_line}. Posting general note instead for MR !{mr.iid}")
            note_body = f"**Code Issue in `{file_path}` (Line ~{display_line})**\n\n{comment_text}"
            # Truncate note body as well
            max_note_length = 15000
            truncated_note = (note_body[:max_note_length] + '...') if len(note_body) > max_note_length else note_body
            mr.notes.create({'body': truncated_note})

    except Exception as e:
        # Log specific details if available
        file_info = line_comment.get('new_file_path', 'unknown_file')
        line_info = f"new:{line_comment.get('new_line', 'N/A')}/old:{line_comment.get('old_line', 'N/A')}"
        logger_obj.error(f"Error posting code review discussion for MR !{mr.iid} on {file_info} ({line_info}): {e}", exc_info=True)


def get_code_review_response_from_gemini(diffs, logger_obj, payload, project, mr):
    """
    Fetches a code review from the Gemini Pro model on Vertex AI.
    """
    if not vertex_ai_initialized:
        logger_obj.error("Vertex AI not initialized. Cannot get code review.")
        raise RuntimeError("Vertex AI not initialized") # Raise exception

    if not diffs:
        logger_obj.warning(f"No diffs provided to get_code_review_response_from_gemini for MR !{mr.iid}.")
        return {"responses": []}

    output_response_schema = {
        "type": "object",
        "properties": {
            "responses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "new_line": {"type": "integer", "description": "1-based line number in the new file. May be omitted or null."},
                        "old_line": {"type": "integer", "description": "1-based line number in the old file. May be omitted or null."},
                        "new_file_path": {"type": "string", "description": "Path of the file being changed."},
                        "old_file_path": {"type": "string", "description": "Original path of the file if renamed, otherwise same as new_file_path."},
                        "full_file_content": {"type": "string", "description": "The full content of the new file to provide context for the review."},
                        "comment": {"type": "string", "description": "The code review comment."},
                        "severity": {"type": "string", "description": "Severity suggestion (e.g., INFO, WARNING, ERROR)"}
                    },
                    "required": ["new_file_path", "comment", "severity"]
                }
            }
        },
         "required": ["responses"]
    }

    project_path = project.path_with_namespace
    review_prompt_text = get_review_prompt(project_path, logger_obj)

    # --- Data Preparation and Sanitization ---
    # Create a deep copy to avoid modifying the original list of diffs
    diffs_for_prompt = json.loads(json.dumps(diffs))

    # Remove the full_file_content from the diffs before sending to Gemini
    # and ensure all content is string, not bytes.
    for diff in diffs_for_prompt:
        if 'full_file_content' in diff:
            del diff['full_file_content']
        # Ensure 'diff' content is decoded if it's bytes
        if 'diff' in diff and isinstance(diff['diff'], bytes):
            try:
                diff['diff'] = diff['diff'].decode('utf-8')
            except UnicodeDecodeError:
                logger_obj.warning(f"Could not decode diff content for {diff.get('new_path')}. Skipping this part of the diff.")
                diff['diff'] = "[Content could not be decoded]"


    try:
        max_diff_chars = 50000
        diffs_json = json.dumps(diffs_for_prompt, indent=2)
        if len(diffs_json) > max_diff_chars:
            logger_obj.warning(f"Diff JSON size ({len(diffs_json)} chars) exceeds limit ({max_diff_chars}) for MR !{mr.iid}. Truncating.")
            diffs_json = diffs_json[:max_diff_chars] + "\n... (truncated)"
    except TypeError as e:
        logger_obj.error(f"TypeError during JSON serialization for prompt: {e}", exc_info=True)
        # This is where the bytes issue would likely be caught.
        raise ValueError(f"Data for MR !{mr.iid} is not JSON serializable. Check for bytes in diffs.") from e
    except Exception as e:
        logger_obj.error(f"Failed to serialize diffs to JSON for MR !{mr.iid}: {e}", exc_info=True)
        raise # Re-raise to be caught by the main handler

    final_prompt = f'''{review_prompt_text}

Review the following code changes presented as a JSON array of diff objects. Provide feedback according to the requested JSON schema.

```json
{diffs_json}
```
'''
    if DEBUG_MODE:
        logger_obj.debug(f"Full prompt for Gemini review (MR !{mr.iid}) - Size: {len(final_prompt)} chars")
    else:
        logger_obj.info(f"Prompt for Gemini review (MR !{mr.iid}) - First 500 chars: {final_prompt[:500]}...")
    logger_obj.info(f"Number of diffs sent to Gemini for MR !{mr.iid}: {len(diffs_for_prompt)}")

    try:
        model = GenerativeModel(
            model_name=MODEL_ID,
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                response_schema=output_response_schema,
                candidate_count=1,
            )
        )
        response = model.generate_content(final_prompt)

        if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
            finish_reason = getattr(response.candidates[0], 'finish_reason', 'N/A') if response.candidates else 'N/A'
            safety_ratings = getattr(response.candidates[0], 'safety_ratings', 'N/A') if response.candidates else 'N/A'
            error_message = f"Invalid response from Gemini for MR !{mr.iid}. Finish Reason: {finish_reason}, Safety Ratings: {safety_ratings}"
            logger_obj.error(error_message)
            raise RuntimeError(error_message)

        response_text = response.candidates[0].content.parts[0].text
        if DEBUG_MODE:
            logger_obj.debug(f"Full raw Gemini review response for MR !{mr.iid}: {response_text}")

        comments = json.loads(response_text)

        if 'responses' not in comments or not isinstance(comments['responses'], list):
            logger_obj.error(f"Gemini response missing 'responses' array for MR !{mr.iid}. Raw text: {response_text}")
            return {"responses": []}

        validated_responses = []
        for item in comments['responses']:
            if isinstance(item, dict):
                nl = item.get('new_line')
                ol = item.get('old_line')
                item['new_line'] = int(nl) if isinstance(nl, int) and nl > 0 else None
                item['old_line'] = int(ol) if isinstance(ol, int) and ol > 0 else None
                validated_responses.append(item)
            else:
                logger_obj.warning(f"Skipping non-dictionary item in Gemini 'responses' array: {item}")
        comments['responses'] = validated_responses

        logger_obj.info(f"Parsed Gemini response successfully for MR !{mr.iid}. Found {len(comments['responses'])} comments.")
        return comments
    except json.JSONDecodeError as json_err:
        logger_obj.error(f"Failed to decode JSON response from Gemini for MR !{mr.iid}: {json_err}", exc_info=True)
        logger_obj.error(f"Raw response text was: {response_text}")
        raise ValueError("Failed to decode JSON from Gemini.") from json_err
    except Exception as e:
        logger_obj.error(f"Error getting code review from Gemini: {e}", exc_info=True)
        raise # Re-raise the exception to be handled by the caller


def post_merge_request_summary(mr, feedback, logger_obj):
    """
    Posts the summary of a code review as a note on a GitLab merge request.
    """
    if not feedback or not isinstance(feedback, str) or not feedback.strip():
        logger_obj.warning(f"Attempted to post empty or invalid summary feedback for MR !{mr.iid}. Skipping.")
        return

    try:
        logger_obj.info(f"Posting summary feedback to MR !{mr.iid}")
        # Truncate long summaries
        max_summary_length = 15000 # Example limit
        truncated_feedback = (feedback[:max_summary_length] + '...') if len(feedback) > max_summary_length else feedback

        if DEBUG_MODE:
            logger_obj.debug(f"Summary feedback content (first 500 chars): {truncated_feedback[:500]}...")

        note = mr.notes.create({'body': truncated_feedback})
        logger_obj.info(f"Successfully posted summary note {note.id} for MR !{mr.iid}")
    except Exception as e:
        logger_obj.error(f"Error posting code review summary for MR !{mr.iid}: {e}", exc_info=True)


def get_latest_commit_diff(payload, project, logger_obj):
    """
    Fetches the diff for the latest commit in a GitLab merge request and enriches
    it with the full file content for each changed file.
    """
    commit_id = None
    try:
        commit_id = payload.get("object_attributes", {}).get("last_commit", {}).get("id")
        if not commit_id:
            logger_obj.error("Invalid payload: last_commit ID is missing or empty.")
            return []

        logger_obj.info(f"Fetching diffs for commit {commit_id[:8]} in project {project.path_with_namespace}")
        commit = project.commits.get(commit_id)
        # The commit.diff() call returns a list of dicts, where 'diff' can be bytes
        diff_list = commit.diff()
        logger_obj.info(f"Retrieved {len(diff_list)} diffs from commit {commit_id[:8]}")

        for diff in diff_list:
            # Decode the 'diff' content from bytes to string
            if 'diff' in diff and isinstance(diff['diff'], bytes):
                try:
                    diff['diff'] = diff['diff'].decode('utf-8')
                except UnicodeDecodeError:
                    logger_obj.warning(f"Could not decode diff content for {diff.get('new_path')}. Storing as placeholder.")
                    diff['diff'] = "[Content could not be decoded]"

            if diff.get('deleted_file'):
                diff['full_file_content'] = "" # Use empty string for deleted files
                continue

            file_path = diff.get('new_path')
            try:
                file_content = project.files.get(file_path=file_path, ref=commit_id).content
                if isinstance(file_content, bytes):
                    diff['full_file_content'] = file_content.decode('utf-8')
                else:
                    diff['full_file_content'] = file_content
            except Exception as file_err:
                logger_obj.error(f"Failed to fetch content for '{file_path}' at commit {commit_id[:8]}: {file_err}", exc_info=True)
                diff['full_file_content'] = f"Error: Could not retrieve content for {file_path}."

        return diff_list
    except Exception as e:
        commit_id_str = commit_id[:8] if commit_id else "unknown"
        logger_obj.error(f"Error fetching diffs for commit {commit_id_str}: {e}", exc_info=True)
        raise # Re-raise to be caught by the main handler


def get_code_review_summary_from_gemini(responses, logger_obj, payload, project, mr):
    """
    Generates a summary of code review comments from the Gemini Pro model.
    """
    if not vertex_ai_initialized:
        logger_obj.error("Vertex AI not initialized. Cannot generate summary.")
        return None
    if not responses:
        logger_obj.info(f"No responses provided to summarize for MR !{mr.iid}. Skipping summary generation.")
        return None

    # --- Prompt Loading Logic ---
    # Get the parsed summary system instructions and user-facing prompt
    summary_system_text, summary_user_prompt = get_summary_prompts(logger_obj)

    logger_obj.info(f"Number of responses being summarized for MR !{mr.iid}: {len(responses)}")

    try:
        model = GenerativeModel(
            model_name= MODEL_ID,
            system_instruction=summary_system_text
        )
    except Exception as e:
        logger_obj.error(f"Failed to initialize GenerativeModel for summary: {e}", exc_info=True)
        return None

    try:
        # Prepare responses for the prompt, maybe simplify them
        simplified_responses = [{"comment": r.get("comment", ""), "severity": r.get("severity", ""), "file": r.get("new_file_path", "")} for r in responses]
        responses_json = json.dumps(simplified_responses, indent=2)

        # Limit size of JSON sent for summary
        max_summary_input_chars = 10000
        if len(responses_json) > max_summary_input_chars:
             logger_obj.warning(f"Responses JSON size ({len(responses_json)} chars) exceeds summary limit ({max_summary_input_chars}). Truncating.")
             responses_json = responses_json[:max_summary_input_chars] + "\n... (truncated)"

        # Ensure the placeholder exists before formatting
        if '{json.dumps(responses, indent=2)}' in summary_user_prompt:
             # Replace the specific placeholder from the prompt file
             content_for_gemini = summary_user_prompt.replace('{json.dumps(responses, indent=2)}', responses_json)
        else:
             logger_obj.warning("Summary user prompt does not contain the expected '{json.dumps(responses, indent=2)}' placeholder. Appending raw responses JSON.")
             content_for_gemini = summary_user_prompt + f"\n\n**Review Comments:**\n```json\n{responses_json}\n```"

    except Exception as e:
        logger_obj.error(f"Error preparing summary content for Gemini: {e}", exc_info=True)
        return None

    if DEBUG_MODE:
        # Be cautious logging large prompts
        logger_obj.debug(f"Full prompt for Gemini summary (MR !{mr.iid}) - Size: {len(content_for_gemini)} chars")
        # logger_obj.debug(content_for_gemini) # Uncomment carefully if needed
    else:
        logger_obj.info(f"Prompt for Gemini summary (MR !{mr.iid}) - First 500 chars: {content_for_gemini[:500]}...")

    try:
        response = model.generate_content([content_for_gemini]) # Send as list for multi-turn history if needed later

        # Enhanced response validation
        if not response.candidates:
            logger_obj.error("Invalid summary response structure from Gemini: No candidates found.")
            return None
        if not response.candidates[0].content or not response.candidates[0].content.parts:
             logger_obj.error("Invalid summary response structure from Gemini: Missing content or parts in candidate.")
             finish_reason = getattr(response.candidates[0], 'finish_reason', 'N/A')
             safety_ratings = getattr(response.candidates[0], 'safety_ratings', 'N/A')
             logger_obj.error(f"Finish Reason: {finish_reason}, Safety Ratings: {safety_ratings}")
             return None

        summary_text = response.candidates[0].content.parts[0].text.strip()

        if not summary_text:
             logger_obj.warning(f"Gemini returned an empty summary for MR !{mr.iid}.")
             return None # Don't post an empty summary

        if DEBUG_MODE:
            logger_obj.debug(f"Full generated summary for MR !{mr.iid}: {summary_text}")
        else:
            logger_obj.info(f"Generated summary for MR !{mr.iid} (first 500 chars): {summary_text[:500]}...")
        return summary_text
    except Exception as e:
        logger_obj.error(f"Error generating summary for MR !{mr.iid}: {e}", exc_info=True)
        # Provide a fallback summary note
        return f"**Code Review Summary**\n\nAn error occurred while generating the summary ({e}). Please review the individual comments posted above."


def get_merge_diffs(mr, project, logger_obj):
    """
    Fetches all diff objects for a merge request and enriches them with the
    full file content from the source branch.
    """
    try:
        logger_obj.info(f"Fetching all diffs for merge request !{mr.iid} in project {mr.project_id}")
        source_branch = mr.source_branch
        changes = mr.changes()
        diffs = changes.get('changes', [])
        logger_obj.info(f"Retrieved {len(diffs)} total diffs for MR !{mr.iid}")

        for diff in diffs:
            # Decode the 'diff' content from bytes to string
            if 'diff' in diff and isinstance(diff['diff'], bytes):
                try:
                    diff['diff'] = diff['diff'].decode('utf-8')
                except UnicodeDecodeError:
                    logger_obj.warning(f"Could not decode diff content for {diff.get('new_path')}. Storing as placeholder.")
                    diff['diff'] = "[Content could not be decoded]"

            if diff.get('deleted_file'):
                diff['full_file_content'] = "" # Use empty string for deleted files
                continue

            file_path = diff.get('new_path')
            try:
                file_content = project.files.get(file_path=file_path, ref=source_branch).content
                if isinstance(file_content, bytes):
                    diff['full_file_content'] = file_content.decode('utf-8')
                else:
                    diff['full_file_content'] = file_content
            except Exception as file_err:
                logger_obj.error(f"Failed to fetch content for '{file_path}' from branch '{source_branch}': {file_err}", exc_info=True)
                diff['full_file_content'] = f"Error: Could not retrieve content for {file_path}."

        return diffs
    except Exception as e:
        logger_obj.error(f"Error fetching all diffs for MR !{mr.iid}: {e}", exc_info=True)
        raise # Re-raise to be caught by the main handler

# --- Main Execution ---
if __name__ == "__main__":
    # Gunicorn runs the app, this block is mainly for local development
    # Ensure PORT env var is set for local execution if needed
    port = int(os.environ.get("PORT", 8080))
    # Use debug=True cautiously in production via env var
    use_debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Starting Flask server locally on port {port} with debug={use_debug}")
    app.run(debug=use_debug, host="0.0.0.0", port=port)
