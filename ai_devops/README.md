# Gemini Code Reviewer & Wiki Updater - GitLab Cloud Function

This project contains a Google Cloud Function written in Python that integrates with GitLab to perform automated code reviews using Google's Gemini Pro model via Vertex AI and optionally update GitLab wikis based on merge request details.

## Project Structure

- `.gitignore`: Specifies intentionally untracked files that Git should ignore.
- `.gitlab-ci.yml`: Defines the GitLab CI/CD pipeline configuration (likely for deploying the Cloud Function).
- `README.md`: This file, providing documentation for the project.
- `app/`: Contains the main application code.
  - `main.py`: The Google Cloud Function entry point (`gitlab_webhook`).
  - `requirements.txt`: Lists the Python dependencies required for the function.

## How it Works

1.  **GitLab Webhook Trigger:** The function (`gitlab_webhook` in `app/main.py`) is designed to be triggered by GitLab webhook events, specifically "Merge Request Hook".
2.  **Authentication:** It verifies the authenticity of incoming requests using a secret token (`X-Gitlab-Token` header) configured in both GitLab and the function's environment.
3.  **Event Handling:**
    *   It identifies the type of merge request action (`open`, `reopen`, `update`, `merge`).
    *   **Code Review (on `open`, `reopen`, `update` with changes):**
        *   Fetches the relevant code diffs from the merge request using the GitLab API.
        *   Constructs a detailed prompt for the Gemini Pro model (`gemini-1.5-pro-001`) hosted on Vertex AI, instructing it to review the code changes focusing on correctness, formatting, maintainability, performance, security, and ROS2 best practices.
        *   Sends the diffs to Gemini Pro and receives line-by-line code review comments in JSON format, including severity levels (`minor`, `moderate`, `major`, `critical`).
        *   Generates a summary of the review comments using Gemini Pro.
        *   Posts the individual line comments as discussions on the merge request diff using the GitLab API.
        *   Posts the overall summary as a note on the merge request using the GitLab API.
    *   **Wiki Update (on `merge`):**
        *   If the merge request has labels starting with `docs::` (e.g., `docs::my-feature`), it identifies these as target wiki pages.
        *   Fetches the merge request details (title, description, commits, changes).
        *   Retrieves the existing content of the target wiki page (if it exists) or prepares to create a new one.
        *   Constructs a prompt for Gemini Pro to summarize the merge request details and update/generate the wiki page content in Markdown format.
        *   Updates or creates the wiki page using the GitLab API.
4.  **Logging:** Uses Google Cloud Logging to record information, debug messages, and errors.

## Setup

### 1. Deploy the Cloud Function

*   Deploy the function in `app/main.py` to Google Cloud Functions (Gen 2 recommended for potentially longer execution times).
*   Ensure the function's entry point is set to `gitlab_webhook`.
*   Set the necessary environment variables (see below).
*   Make the function publicly accessible but secured via the webhook token (or use Cloud IAP/API Gateway for stricter access control if needed). Note the Function URL after deployment.

### 2. Configure GitLab Webhook

*   In your GitLab project, navigate to **Settings -> Webhooks**.
*   **URL:** Enter the URL of your deployed Google Cloud Function.
*   **Secret token:** Generate a secure secret token and enter it here. This token **must** match the `GITLAB_WEBHOOK_SECRET_ID` environment variable configured for the Cloud Function.
*   **Trigger:** Select "Merge request events".
*   Click "Add webhook".

### 3. Environment Variables

The Cloud Function requires the following environment variables to be set:

*   `GITLAB_WEBHOOK_SECRET_ID`: The secret token configured in the GitLab webhook settings.
*   `PROJECT_ID`: Your Google Cloud Project ID where Vertex AI and other services are enabled.
*   `GITLAB_PAT_SECRET_ID`: A GitLab Personal Access Token (PAT) with `api` scope. Store this securely (e.g., in Google Secret Manager) and provide its value or secret ID here. The function uses this PAT to interact with the GitLab API (fetch diffs, post comments, update wikis).
*   `DEBUG_MODE` (Optional): Set to `true` or `1` to enable verbose debug logging in Cloud Logging. Defaults to off if not set.

**Security Note:** It's highly recommended to store sensitive values like the GitLab PAT and webhook secret in Google Secret Manager and grant the Cloud Function's service account access to read them, rather than setting them directly as environment variables. The current code reads directly from environment variables, which might require adaptation if using Secret Manager integration within the function code itself.

### 4. GCP APIs & Permissions

Ensure the following Google Cloud APIs are enabled in your project:

*   **Cloud Functions API:** To deploy and run the function.
*   **Vertex AI API:** To access the Gemini Pro model.
*   **Cloud Logging API:** For logging function execution and errors.
*   **Secret Manager API** (Recommended): If storing secrets securely.
*   **Cloud Build API:** Usually required for deploying Cloud Functions.

The service account used by the Cloud Function needs appropriate IAM roles:
*   `roles/cloudfunctions.invoker`: To allow invocation via HTTP.
*   `roles/aiplatform.user`: To interact with Vertex AI models.
*   `roles/logging.logWriter`: To write logs.
*   `roles/secretmanager.secretAccessor` (Recommended): If using Secret Manager.

## Usage

Once deployed and configured, the function runs automatically whenever a merge request event occurs in the configured GitLab project. Code review comments and summaries will appear directly on the merge requests. Wiki pages will be updated upon merging merge requests with appropriate `docs::` labels.

## Additional Notes

*   **Model:** The function currently uses `gemini-1.5-pro-001`. This can be changed via the `MODEL_ID` constant in `app/main.py`.
*   **ROS2 Focus:** The prompts for Gemini Pro specifically mention reviewing code for ROS2 best practices. This can be adjusted in the `system_instructions` within the `get_code_review_response_from_gemini` function if your project uses different standards.
*   **Wiki Trigger:** Wiki updates rely on GitLab labels following the `docs::slug-name` convention.
*   **Dependencies:** Install dependencies using `pip install -r app/requirements.txt`.

## CI/CD

The `.gitlab-ci.yml` file likely contains the configuration for deploying this Cloud Function using GitLab CI/CD, potentially using `gcloud` CLI commands. Review this file for specific deployment steps.
