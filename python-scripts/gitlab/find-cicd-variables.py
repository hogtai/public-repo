"""
This script automates the process of searching for a specific GCP service account
within CI/CD variables across all projects and their subgroups within a specified
GitLab group. It logs the projects and variables where the service account is found.

Configuration parameters such as GitLab URL, access token, search term, and
the target GitLab group ID are centralized in a Config class for easy modification.
"""
import requests
import time
import os
from datetime import datetime

class Config:
    GITLAB_URL = "YOUR_GITLAB_URL"                       # Base URL of the GitLab instance (e.g., "https://gitlab.com")
    ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"                   # Personal Access Token for GitLab API authentication (e.g., "glpat-xxxxxxxxxxxxxxxxx")
    SEARCH_TERM = "YOUR_GCP_SERVICE_ACCOUNT_EMAIL"       # The GCP service account email to search for (e.g., "terraform@lc-terraform-admin.iam.gserviceaccount.com")
    GROUP_ID = YOUR_GROUP_ID                             # The ID of the GitLab group to search within (e.g., 95194212)
    LOG_FILE = os.path.join(os.getcwd(), "results.txt")  # Path to the log file where results will be logged
    REQUEST_TIMEOUT = 20                                 # Timeout for API requests in seconds
    RETRY_LIMIT = 3                                      # Number of times to retry a failed API request

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

    def get_all_projects_in_group(self, group_id, all_projects=None):
        if all_projects is None:
            all_projects = []

        # Get all projects for the group
        url = f"{self.gitlab_url}/api/v4/groups/{group_id}/projects?include_subgroups=false"
        response = self._make_request("GET", url)
        if not response:
            write_output(f"Error: Could not fetch projects for group {group_id}")
            return all_projects

        projects = response.json()
        write_output(f"Fetched {len(projects)} projects from group {group_id}")
        for project in projects:
            all_projects.append(project)

        # Get all subgroups for the group
        url = f"{self.gitlab_url}/api/v4/groups/{group_id}/subgroups"
        response = self._make_request("GET", url)
        if not response:
            write_output(f"Error: Could not fetch subgroups for group {group_id}")
            return all_projects

        subgroups = response.json()
        write_output(f"Found {len(subgroups)} subgroups in group {group_id}")
        for subgroup in subgroups:
            # Recursively call get_all_projects for each subgroup
            self.get_all_projects_in_group(subgroup['id'], all_projects)

        return all_projects

    def search_cicd_variables(self, project_id, search_term):
        variables_url = f"{self.gitlab_url}/api/v4/projects/{project_id}/variables"
        response = self._make_request("GET", variables_url)
        if response:
            return response.json()
        return []

def find_gcp_account_in_projects(gitlab_api, projects, search_term):
    for project in projects:
        project_id = project['id']
        project_name = project['name']
        project_url = project['web_url']

        write_output(f"\nSearching CI/CD variables in project: {project_name} ({project_url})")

        variables = gitlab_api.search_cicd_variables(project_id, search_term)

        found = False
        for variable in variables:
            if search_term in variable['value']:
                write_output(f"Found in project {project_name}, variable {variable['key']}: {variable['value']}")
                found = True

        if not found:
            write_output(f"No occurrences found in CI/CD variables of {project_name}")

def run_script():
    write_output("Starting the script...\n")

    gitlab_api = GitlabAPI(Config.GITLAB_URL, Config.ACCESS_TOKEN, Config.REQUEST_TIMEOUT, Config.RETRY_LIMIT)

    all_projects = gitlab_api.get_all_projects_in_group(Config.GROUP_ID)

    write_output(f"Total projects found: {len(all_projects)}")

    find_gcp_account_in_projects(gitlab_api, all_projects, Config.SEARCH_TERM)

    write_output("\nScript execution completed.")

if __name__ == "__main__":
    if not os.path.exists(Config.LOG_FILE):
        try:
            open(Config.LOG_FILE, "w").close()
        except IOError as e:
            print(f"Error creating log file {Config.LOG_FILE}: {e}")
            exit(1)
    run_script()
