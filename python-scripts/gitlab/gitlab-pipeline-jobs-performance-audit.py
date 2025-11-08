"""
This script automates the process of fetching GitLab pipeline and job data for a specified project,
analyzing job durations, and saving the statistics to a text file. It provides insights into
the performance of CI/CD pipelines and their jobs within a GitLab project.

Configuration parameters such as GitLab URL, project ID, access token, and data fetching
period are centralized in a Config class for easy modification.
"""
import requests
import logging
import re
from datetime import datetime, timedelta
from collections import defaultdict

class Config:
    GITLAB_URL = "YOUR_GITLAB_URL"                  # Base URL of the GitLab instance (e.g., "https://gitlab.com")
    PROJECT_ID = "YOUR_PROJECT_ID"                  # The ID of the GitLab project to analyze (e.g., "64437076")
    ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"              # Personal Access Token for GitLab API authentication (e.g., "glpat-xxxxxxxxxxxxxxxxx")
    PIPELINE_FETCH_DAYS_AGO = 90                    # Number of days ago to fetch pipelines from
    LOG_LEVEL = logging.INFO                        # Logging level (e.g., logging.INFO, logging.DEBUG)
    OUTPUT_FILENAME_PREFIX = "job_duration_stats"   # Prefix for the output text file

# Configure logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Log to console
    ]
)

def sanitize_filename(name):
    """
    Sanitize the project name to create a valid filename.
    """
    # Remove any character that is not alphanumeric, a space, or one of -_.
    sanitized_name = re.sub(r'[^\w\s\-_]', '', name)
    # Replace spaces with underscores
    sanitized_name = sanitized_name.replace(' ', '_')
    return sanitized_name

class GitlabAPI:
    def __init__(self, gitlab_url, project_id, access_token):
        self.gitlab_url = gitlab_url
        self.project_id = project_id
        self.headers = {"Private-Token": access_token}

    def _make_request(self, method, url, params=None):
        try:
            response = requests.request(method, url, headers=self.headers, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logging.error(f"Error with request to {url}: {e}")
            return None

    def fetch_project_name(self):
        """
        Fetch the project name using the GitLab API.
        """
        url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}"
        response = self._make_request("GET", url)
        if response:
            return response.json().get('name')
        return None

    def fetch_pipelines(self, updated_after_iso):
        """
        Fetch all pipelines updated after a specific date.
        """
        pipelines = []
        page = 1
        while True:
            url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines"
            params = {
                "updated_after": updated_after_iso,
                "per_page": 100,
                "page": page
            }
            response = self._make_request("GET", url, params=params)
            if not response:
                break
            data = response.json()
            if not data:
                break
            pipelines.extend(data)
            page += 1
        return pipelines

    def fetch_pipeline_jobs(self, pipeline_id):
        """
        Fetch all jobs for a specific pipeline.
        """
        jobs = []
        page = 1
        while True:
            url = f"{self.gitlab_url}/api/v4/projects/{self.project_id}/pipelines/{pipeline_id}/jobs"
            params = {
                "per_page": 100,
                "page": page
            }
            response = self._make_request("GET", url, params=params)
            if not response:
                break
            data = response.json()
            if not data:
                break
            jobs.extend(data)
            page += 1
        return jobs

def analyze_jobs(jobs):
    """
    Analyze job durations and calculate statistics.
    """
    job_durations = defaultdict(list)
    for job in jobs:
        duration = job.get('duration')  # Duration in seconds
        if duration is not None:
            job_durations[job['name']].append(duration / 60)  # Convert to minutes

    job_stats = {}
    for job_name, durations in job_durations.items():
        if durations:
            slowest = max(durations)
            fastest = min(durations)
            average = sum(durations) / len(durations)
            job_stats[job_name] = {
                "slowest": slowest,
                "fastest": fastest,
                "average": average
            }
    return job_stats

def save_to_text(job_stats, project_name):
    """
    Save job statistics to a text file.
    """
    sanitized_project_name = sanitize_filename(project_name)
    filename = f"{Config.OUTPUT_FILENAME_PREFIX}_{sanitized_project_name}.txt"
    try:
        with open(filename, "w") as txtfile:
            header = f"{'Job Name':<30} {'Slowest (min)':<15} {'Fastest (min)':<15} {'Average (min)':<15}\n"
            txtfile.write(header)
            txtfile.write("=" * 75 + "\n")
            for job_name, stats in job_stats.items():
                line = f"{job_name:<30} {stats['slowest']:<15.2f} {stats['fastest']:<15.2f} {stats['average']:<15.2f}\n"
                txtfile.write(line)
                logging.info(f"Job Name: {job_name}, Slowest: {stats['slowest']:.2f} min, "
                             f"Fastest: {stats['fastest']:.2f} min, Average: {stats['average']:.2f} min")
        logging.info(f"Job duration statistics saved to {filename}")
    except IOError as e:
        logging.error(f"Error writing to file {filename}: {e}")

def run_script():
    gitlab_api = GitlabAPI(Config.GITLAB_URL, Config.PROJECT_ID, Config.ACCESS_TOKEN)

    try:
        project_name = gitlab_api.fetch_project_name()
        if not project_name:
            logging.error("Failed to retrieve project name. Exiting.")
            return
        logging.info(f"Processing project: {project_name}")
    except requests.RequestException as e:
        logging.error(f"Failed to fetch project name: {e}")
        return

    days_ago = datetime.now() - timedelta(days=Config.PIPELINE_FETCH_DAYS_AGO)
    days_ago_iso = days_ago.isoformat()

    try:
        pipelines = gitlab_api.fetch_pipelines(days_ago_iso)
        logging.info(f"Found {len(pipelines)} pipelines ran in the last {Config.PIPELINE_FETCH_DAYS_AGO} days.\n")
    except requests.RequestException as e:
        logging.error(f"Failed to fetch pipelines: {e}")
        return

    all_jobs = []
    for pipeline in pipelines:
        pipeline_id = pipeline['id']
        try:
            jobs = gitlab_api.fetch_pipeline_jobs(pipeline_id)
            all_jobs.extend(jobs)
            logging.info(f"Fetched {len(jobs)} jobs from pipeline ID {pipeline_id}.")
        except requests.RequestException as e:
            logging.error(f"Failed to fetch jobs for pipeline ID {pipeline_id}: {e}")

    if all_jobs:
        job_stats = analyze_jobs(all_jobs)
        save_to_text(job_stats, project_name)
    else:
        logging.info("No jobs found to analyze.")

if __name__ == "__main__":
    run_script()
