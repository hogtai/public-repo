"""
This script automates the process of searching for a specific string in GitLab project files
within a defined namespace, replacing it with a new string, and then creating a new branch
and a merge request for the changes. It handles API interactions, retries, and logs its
progress to a file. Includes logging, error handling, and retry logic.

Configuration parameters such as GitLab URL, access token, search/replacement terms,
and project namespace are centralized in a Config class for easy modification.
"""
import requests
import time
import os
from datetime import datetime

class Config:
    GITLAB_URL = "YOUR_GITLAB_URL"                   # Base URL of the GitLab instance (e.g., "https://gitlab.com") (string value)
    ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"               # Personal Access Token for GitLab API authentication (e.g., "glpat-xxxxxxxxxxxxxxxxx") (string value)
    REQUEST_TIMEOUT = 20                             # Timeout for API requests in seconds (integer value)
    RETRY_LIMIT = 3                                  # Number of times to retry a failed API request (integer value)
    LOG_FILE = os.path.join(os.getcwd(), "log.txt")  # Path to the log file and final log file output name (string value)
    SEARCH_TERM = "SEARCH_TERM_VALUE"                # The string to search for in project files
    REPLACEMENT_TERM = "REPLACEMENT_TERM_VALUE"      # The string to replace the search term with
    TARGET_NAMESPACE = "TARGET_NAMESPACE_VALUE"      # The GitLab namespace to target for project searches (e.g., "/your_group/your_subgroup")
    BRANCH_PREFIX = "BRANCH_NAME"                    # Prefix for the new branch name created for changes
    COMMIT_MESSAGE = "COMMIT_MESSAGE"                # Commit message for the changes
    MERGE_REQUEST_TITLE = "MERGE_REQUEST_TITLE"      # Title for the created merge request

# Helper function to write both to console and log file
def write_output(message):
    print(message)
    try:
        with open(Config.LOG_FILE, "a") as output_file_handle:
            output_file_handle.write(message + "\n")
    except IOError as e:
        print(f"Error writing to log file {Config.LOG_FILE}: {e}")

# Check if a project has already been processed
def is_project_processed(project_name):
    try:
        with open(Config.LOG_FILE, "r") as log:
            for line in log:
                if line.startswith(f"PROCESSED: {project_name}"):
                    return True
    except FileNotFoundError:
        return False
    return False

# Mark a project as processed
def mark_project_processed(project_name):
    write_output(f"PROCESSED: {project_name}")

class GitlabAPI:
    def __init__(self, gitlab_url, access_token, request_timeout, retry_limit):
        self.gitlab_url = gitlab_url
        self.headers = {"Private-Token": access_token}
        self.request_timeout = request_timeout
        self.retry_limit = retry_limit

    def _make_request(self, method, url, **kwargs):
        retries = 0
        while retries < self.retry_limit:
            try:
                response = requests.request(method, url, timeout=self.request_timeout, headers=self.headers, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                write_output(f"Request to {url} timed out. Retrying... ({retries + 1}/{self.retry_limit})")
                retries += 1
                time.sleep(5)
            except requests.exceptions.RequestException as e:
                write_output(f"Error with request to {url}: {e}")
                break
        return None

    def get_all_projects(self, target_namespace):
        projects = []
        page = 1
        while True:
            url = f"{self.gitlab_url}/api/v4/projects?membership=true&per_page=100&page={page}"
            response = self._make_request("GET", url)
            if not response:
                break
            response_data = response.json()
            if not response_data:
                break

            filtered_projects = [project for project in response_data if project['web_url'].startswith(f"{self.gitlab_url}{target_namespace}")]
            projects.extend(filtered_projects)
            write_output(f"Fetched page {page}, total '{target_namespace}' projects so far: {len(projects)}")
            page += 1
        return projects

    def get_default_branch(self, project_id):
        url = f"{self.gitlab_url}/api/v4/projects/{project_id}"
        response = self._make_request("GET", url)
        if response:
            return response.json().get("default_branch", "main")
        return "main"

    def create_branch(self, project_id, branch_name, ref):
        url = f"{self.gitlab_url}/api/v4/projects/{project_id}/repository/branches"
        data = {
            "branch": branch_name,
            "ref": ref
        }
        response = self._make_request("POST", url, json=data)
        return response is not None

    def commit_changes(self, project_id, branch_name, file_path, content, commit_message):
        url = f"{self.gitlab_url}/api/v4/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}"
        data = {
            "branch": branch_name,
            "content": content,
            "commit_message": f"{commit_message} in {file_path}"
        }
        response = self._make_request("PUT", url, json=data)
        return response is not None

    def open_merge_request(self, project_id, source_branch, target_branch, title):
        url = f"{self.gitlab_url}/api/v4/projects/{project_id}/merge_requests"
        data = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": f"{title} from {source_branch} to {target_branch}",
            "remove_source_branch": True
        }
        response = self._make_request("POST", url, json=data)
        return response is not None

    def search_blobs(self, project_id, search_term, ref):
        search_url = f"{self.gitlab_url}/api/v4/projects/{project_id}/search?scope=blobs&search={search_term}&ref={ref}"
        response = self._make_request("GET", search_url)
        if response:
            return response.json()
        return []

    def get_raw_file_content(self, project_id, file_path, ref):
        raw_url = f"{self.gitlab_url}/api/v4/projects/{project_id}/repository/files/{file_path.replace('/', '%2F')}/raw?ref={ref}"
        response = self._make_request("GET", raw_url)
        if response:
            return response.text
        return None

# Process a single project for search and replace
def process_project(gitlab_api, project, search_term, replacement_term):
    project_id = project['id']
    project_name = project['name']
    
    if is_project_processed(project_name):
        write_output(f"Skipping already processed project: {project_name}")
        return

    default_branch = gitlab_api.get_default_branch(project_id)
    new_branch_name = f"{Config.BRANCH_PREFIX}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    search_results = gitlab_api.search_blobs(project_id, search_term, default_branch)
    
    if not search_results:
        write_output(f"No instances found in {project_name} ({default_branch})")
        mark_project_processed(project_name) # Mark as processed even if no changes, to avoid re-checking
        return
    
    write_output(f"Processing project: {project_name} on branch {default_branch}")
    
    if not gitlab_api.create_branch(project_id, new_branch_name, default_branch):
        write_output(f"Failed to create branch '{new_branch_name}' for project {project_name}")
        return
    
    changes_made = False
    for result in search_results:
        file_path = result.get('path')
        file_content = gitlab_api.get_raw_file_content(project_id, file_path, default_branch)
        
        if not file_content:
            continue

        updated_content = file_content.replace(search_term, replacement_term)
        
        if updated_content != file_content:
            if gitlab_api.commit_changes(project_id, new_branch_name, file_path, updated_content, Config.COMMIT_MESSAGE):
                write_output(f"Committed changes to {file_path} on branch {new_branch_name}")
                changes_made = True
    
    if changes_made:
        if gitlab_api.open_merge_request(project_id, new_branch_name, default_branch, Config.MERGE_REQUEST_TITLE):
            write_output(f"Merge request created for project: {project_name}")
    else:
        write_output(f"No changes were committed for project: {project_name}")

    mark_project_processed(project_name)

# Search for and replace hardcoded URL in the default branch
def search_and_replace_in_projects(gitlab_api, projects, search_term, replacement_term):
    for project in projects:
        process_project(gitlab_api, project, search_term, replacement_term)

def run_script():
    write_output("Starting the script...\n")
    
    gitlab_api = GitlabAPI(Config.GITLAB_URL, Config.ACCESS_TOKEN, Config.REQUEST_TIMEOUT, Config.RETRY_LIMIT)

    projects = gitlab_api.get_all_projects(Config.TARGET_NAMESPACE)
    write_output(f"Total '{Config.TARGET_NAMESPACE}' namespace projects found: {len(projects)}")

    search_and_replace_in_projects(gitlab_api, projects, Config.SEARCH_TERM, Config.REPLACEMENT_TERM)
    write_output("\nScript execution completed.")

if __name__ == "__main__":
    if not os.path.exists(Config.LOG_FILE):
        try:
            open(Config.LOG_FILE, "w").close()
        except IOError as e:
            print(f"Error creating log file {Config.LOG_FILE}: {e}")
            exit(1)
    run_script()
