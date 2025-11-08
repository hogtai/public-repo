"""
This script automates the process of searching for a specific term within files
across all accessible GitLab projects. It logs the projects and file paths where
the term is found.

Configuration parameters such as GitLab URL, access token, and search term are
centralized in a Config class for easy modification.
"""
import requests
import time
import os
from datetime import datetime

class Config:
    GITLAB_URL = "YOUR_GITLAB_URL"                            # Base URL of the GitLab instance (e.g., "https://gitlab.com")
    ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"                        # Personal Access Token for GitLab API authentication (e.g., "glpat-xxxxxxxxxxxxxxxxx")
    REQUEST_TIMEOUT = 20                                      # Timeout for API requests in seconds
    RETRY_LIMIT = 3                                           # Number of times to retry a failed API request
    LOG_FILE = os.path.join(os.getcwd(), "find-results.txt")  # Path to the log file where results will be logged
    SEARCH_TERM = "YOUR_SEARCH_TERM"                          # The specific term to search for within GitLab project files (e.g., "terraform@lc-terraform-admin.iam.gserviceaccount.com")

# Helper function to write both to console and log file
def write_output(message):
    print(message)
    try:
        with open(Config.LOG_FILE, "a") as output_file_handle:
            output_file_handle.write(message + "\n")
    except IOError as e:
        print(f"Error writing to log file {Config.LOG_FILE}: {e}")

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

    def get_all_projects(self):
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

            projects.extend(response_data)
            write_output(f"Fetched page {page}, total projects so far: {len(projects)}")
            page += 1
        return projects

    def search_blobs(self, project_id, search_term):
        search_url = f"{self.gitlab_url}/api/v4/projects/{project_id}/search?scope=blobs&search={search_term}"
        response = self._make_request("GET", search_url)
        if response:
            return response.json()
        return []

# Search for the specified term in all projects
def search_for_term_in_projects(gitlab_api, projects, search_term):
    for project in projects:
        project_id = project['id']
        project_name = project['name']
        project_url = project['web_url']
        
        write_output(f"\nSearching in project: {project_name} ({project_url})")
        
        search_results = gitlab_api.search_blobs(project_id, search_term)
        
        if not search_results:
            write_output(f"No occurrences found in {project_name}")
            continue
        
        for result in search_results:
            file_path = result.get('path')
            write_output(f"Found in {project_name}: {file_path}")

def run_script():
    write_output("Starting the script...\n")
    
    gitlab_api = GitlabAPI(Config.GITLAB_URL, Config.ACCESS_TOKEN, Config.REQUEST_TIMEOUT, Config.RETRY_LIMIT)

    projects = gitlab_api.get_all_projects()
    write_output(f"Total projects found: {len(projects)}")
    
    search_for_term_in_projects(gitlab_api, projects, Config.SEARCH_TERM)
    write_output("\nScript execution completed.")

if __name__ == "__main__":
    if not os.path.exists(Config.LOG_FILE):
        try:
            open(Config.LOG_FILE, "w").close()
        except IOError as e:
            print(f"Error creating log file {Config.LOG_FILE}: {e}")
            exit(1)
    run_script()
