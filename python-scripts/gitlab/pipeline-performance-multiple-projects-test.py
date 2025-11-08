import requests
import logging
import re
import sys
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from collections import defaultdict
# Init test
# GitLab project details
# For each Gitlab Project you want to analyze, add its project ID to the PROJECT_IDS list
GITLAB_URL = "https://gitlab.com"
PROJECT_IDS = [pid.strip() for pid in os.environ.get("GITLAB_PROJECT_IDS", "").split(',') if pid.strip()]
if not PROJECT_IDS:
    logging.error("No GitLab project IDs found. Please set the GITLAB_PROJECT_IDS environment variable.")
    sys.exit(1)
ACCESS_TOKEN = os.environ.get("GITLAB_ACCESS_TOKEN")
if not ACCESS_TOKEN:
    logging.error("GitLab access token not found. Please set the GITLAB_ACCESS_TOKEN environment variable.")
    sys.exit(1)

# Pass the GL PAT as a Headers for the API requests
headers = {
    "Private-Token": ACCESS_TOKEN
}

# Calculate date range (default 90 days)
DAYS_AGO = 30
days_ago = datetime.now() - timedelta(days=DAYS_AGO)
days_ago_iso = days_ago.isoformat()

# Global variables for output
project_name = ""
sanitized_project_name = ""
output_filename = ""
log_filename = ""

def setup_logging():
    # Configure logging to output to both console and file
    global log_filename
    log_filename = f"{sanitized_project_name}_pipeline_stats_log.txt"
    
    # Clear previous handlers to avoid duplicates
    if logging.root.handlers:
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, mode='w'),  # Log to file
            logging.StreamHandler()  # Log to console
        ]
    )

def fetch_project_name(project_id):
    # Fetch the project name using the GitLab API.
    global project_name, sanitized_project_name, output_filename
    
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    project_data = response.json()
    project_name = project_data['name']
    sanitized_project_name = sanitize_filename(project_name)
    output_filename = f"{sanitized_project_name}_pipeline_stats_results.txt"
    
    return project_name

def sanitize_filename(name):
    # Sanitize the project name to create a valid filename for logging.
    # Remove any character that is not alphanumeric, a space, or one of -_.
    sanitized_name = re.sub(r'[^\w\s\-_]', '', name)
    # Replace spaces with underscores
    sanitized_name = sanitized_name.replace(' ', '_')
    return sanitized_name

def fetch_pipelines(project_id):
    # Fetch all pipelines updated in the specified date range.
    pipelines = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipelines"
        params = {
            "updated_after": days_ago_iso,
            "per_page": 100,
            "page": page
        }
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        pipelines.extend(data)
        page += 1
    return pipelines

def fetch_pipeline_details(project_id, pipeline_id):
    # Fetch detailed information for a specific pipeline.
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_pipeline_jobs(project_id, pipeline_id, include_retried=False):
    # Fetch all jobs for a specific pipeline.
    jobs = []
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
        params = {
            "per_page": 100,
            "page": page
        }
        
        if include_retried:
            params["include_retried"] = "true"
            
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        jobs.extend(data)
        page += 1
    return jobs

def write_section_header(file, title, char="=", width=100):
    # Write a formatted section header to the output file
    file.write("\n")
    file.write(char * width + "\n")
    file.write(f"{title}\n")
    file.write(char * width + "\n\n")
    
    # Also log to console
    logging.info("\n" + char * width)
    logging.info(title)
    logging.info(char * width + "\n")

#
# ANALYSIS FUNCTIONS
#

def analyze_pipeline_runtimes(project_id, pipelines):
    # Analyze pipeline runtimes grouped by branch.
    logging.info("Starting pipeline runtime analysis...")
    
    # Dictionary to store durations for each branch
    branch_durations = defaultdict(list)
    processed_count = 0
    total_count = len(pipelines)

    for pipeline in pipelines:
        pipeline_id = pipeline['id']
        ref = pipeline['ref']
        
        # Fetch detailed pipeline information
        try:
            details = fetch_pipeline_details(project_id, pipeline_id)
            duration = details.get('duration')  # Duration in seconds

            if duration is not None:
                duration_minutes = duration / 60
                branch_durations[ref].append(duration_minutes)
                logging.debug(f"Pipeline ID: {pipeline_id}, Branch: {ref}, Duration: {duration_minutes:.2f} minutes")
            else:
                logging.debug(f"Pipeline ID: {pipeline_id}, Branch: {ref}, Duration: Not Available")
                
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == total_count:
                logging.info(f"Processed {processed_count}/{total_count} pipelines")
                
        except requests.RequestException as e:
            logging.error(f"Error fetching details for pipeline {pipeline_id}: {e}")

    # Calculate statistics for each branch
    branch_stats = {}
    for branch, durations in branch_durations.items():
        if durations:
            slowest = max(durations)
            fastest = min(durations)
            average = sum(durations) / len(durations)
            branch_stats[branch] = {
                "slowest": slowest,
                "fastest": fastest,
                "average": average
            }

    logging.info(f"Pipeline runtime analysis completed for {len(branch_stats)} branches.")
    return branch_stats

def analyze_job_durations(project_id, all_jobs):
    # Analyze job durations and calculate statistics.
    logging.info("Starting job duration analysis...")
    
    job_durations = defaultdict(list)
    for job in all_jobs:
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
            
    logging.info(f"Job duration analysis completed for {len(job_stats)} job types.")
    return job_stats

def analyze_job_retries(project_id, pipelines):
    # Analyze job retries and calculate Pipeline Reliability Rate.
    logging.info("Starting job retry analysis...")
    
    job_stats = defaultdict(lambda: {'total_runs': 0, 'successes': 0, 'failures': 0, 'retries': 0})
    processed_count = 0
    total_count = len(pipelines)

    for pipeline in pipelines:
        pipeline_id = pipeline['id']
        try:
            jobs = fetch_pipeline_jobs(project_id, pipeline_id, include_retried=True)

            # Group jobs by their name within the same pipeline
            jobs_by_name = defaultdict(list)
            for job in jobs:
                jobs_by_name[job['name']].append(job)

            # Analyze each group to determine retries and calculate statistics
            for job_name, job_list in jobs_by_name.items():
                job_list.sort(key=lambda x: x['id'], reverse=True)
                latest_job = job_list[0]
                retried_jobs = job_list[1:]

                job_stats[job_name]['total_runs'] += len(job_list)
                job_stats[job_name]['retries'] += len(retried_jobs)
                for job in job_list:
                    if job['status'] == 'success':
                        job_stats[job_name]['successes'] += 1
                    elif job['status'] == 'failed':
                        job_stats[job_name]['failures'] += 1
                        
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == total_count:
                logging.info(f"Processed {processed_count}/{total_count} pipelines for retry analysis")
                
        except requests.RequestException as e:
            logging.error(f"Error fetching jobs for pipeline {pipeline_id}: {e}")

    logging.info(f"Job retry analysis completed for {len(job_stats)} job types.")
    return job_stats

def analyze_retry_durations(project_id, pipelines):
    # Analyze durations of retried jobs.
    logging.info("Starting retry duration analysis...")
    
    retried_jobs_duration = defaultdict(float)
    retried_jobs_count = defaultdict(int)
    total_retried_jobs = 0
    processed_count = 0
    total_count = len(pipelines)

    for pipeline in pipelines:
        pipeline_id = pipeline['id']
        try:
            jobs = fetch_pipeline_jobs(project_id, pipeline_id, include_retried=True)

            # Group jobs by their name within the same pipeline
            jobs_by_name = defaultdict(list)
            for job in jobs:
                jobs_by_name[job['name']].append(job)

            # Analyze each group to determine retries and calculate statistics
            for job_name, job_list in jobs_by_name.items():
                # Sort by job ID to get the latest job first
                job_list.sort(key=lambda x: x['id'], reverse=True)
                
                # If we have more than one job with the same name in a pipeline, we have retries
                if len(job_list) > 1:
                    retried_jobs = job_list[1:]  # All except the latest one are retries
                    for job in retried_jobs:
                        duration = job.get('duration')
                        if duration is not None:
                            retried_jobs_duration[job_name] += duration / 60  # Convert to minutes
                            retried_jobs_count[job_name] += 1
                            total_retried_jobs += 1
                            logging.debug(f"Found retried job: {job_name} in pipeline {pipeline_id}, duration: {duration / 60:.2f} min")
            
            processed_count += 1
            if processed_count % 10 == 0 or processed_count == total_count:
                logging.info(f"Processed {processed_count}/{total_count} pipelines for retry duration analysis")
                
        except requests.RequestException as e:
            logging.error(f"Error fetching jobs for pipeline {pipeline_id}: {e}")

    # Calculate average durations
    retry_stats = {}
    for job_name in retried_jobs_duration:
        total_duration = retried_jobs_duration[job_name]
        count = retried_jobs_count[job_name]
        avg_duration = total_duration / count if count > 0 else 0
        retry_stats[job_name] = {
            "total_duration": total_duration,
            "count": count,
            "avg_duration": avg_duration
        }

    logging.info(f"Retry duration analysis completed with {total_retried_jobs} total retried jobs.")
    return retry_stats, total_retried_jobs

#
# OUTPUT FUNCTIONS
#

def write_branch_stats(file, branch_stats):
    # Write branch statistics to the output file.
    header = f"{'Branch':<50} {'Slowest (min)':<15} {'Fastest (min)':<15} {'Average (min)':<15}\n"
    file.write(header)
    file.write("=" * 95 + "\n")
    
    for branch, data in sorted(branch_stats.items()):
        line = f"{branch:<50} {data['slowest']:<15.2f} {data['fastest']:<15.2f} {data['average']:<15.2f}\n"
        file.write(line)
        
    file.write("\n")

def write_job_duration_stats(file, job_stats):
    # Write job duration statistics to the output file.
    header = f"{'Job Name':<30} {'Slowest (min)':<15} {'Fastest (min)':<15} {'Average (min)':<15}\n"
    file.write(header)
    file.write("=" * 75 + "\n")
    
    for job_name, stats in sorted(job_stats.items()):
        line = f"{job_name:<30} {stats['slowest']:<15.2f} {stats['fastest']:<15.2f} {stats['average']:<15.2f}\n"
        file.write(line)
        
    file.write("\n")

def write_job_retry_stats(file, job_stats):
    # Write job retry statistics to the output file.
    header = f"{'Job Name':<30} {'Total Runs':<12} {'Successes':<10} {'Failures':<10} {'Retries':<8} {'Pipeline Reliability Rate (%)':<16}\n"
    file.write(header)
    file.write("=" * 85 + "\n")
    
    for job_name, stats in sorted(job_stats.items()):
        if stats['total_runs'] > 0:
            reliability_rate = ((stats['total_runs'] - stats['retries']) / stats['total_runs']) * 100
        else:
            reliability_rate = 0.0
        line = f"{job_name:<30} {stats['total_runs']:<12} {stats['successes']:<10} {stats['failures']:<10} {stats['retries']:<8} {reliability_rate:<16.2f}\n"
        file.write(line)
        
    file.write("\n")

def write_retry_duration_stats(file, retry_stats, total_retried_jobs):
    # Write retry duration statistics to the output file.
    header = f"{'Job Name':<30} {'Total Retried Duration (min)':<25} {'Retry Count':<15} {'Avg Duration (min)':<20}\n"
    file.write(header)
    file.write("=" * 90 + "\n")
    
    total_duration = 0
    
    if retry_stats:
        for job_name, stats in sorted(retry_stats.items()):
            total_duration += stats['total_duration']
            line = f"{job_name:<30} {stats['total_duration']:<25.2f} {stats['count']:<15} {stats['avg_duration']:<20.2f}\n"
            file.write(line)
        
        # Add a total line
        total_line = f"{'TOTAL':<30} {total_duration:<25.2f} {total_retried_jobs:<15} {'-':<20}\n"
        file.write(total_line)
    else:
        file.write("No retried jobs found in the specified time frame.\n")
        
    file.write("\n")

def main():
    # Main function that runs all analyses in sequence
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_generated_files = []
        
        for project_id in PROJECT_IDS:
            # Initialization
            global project_name, sanitized_project_name, output_filename
            project_name = fetch_project_name(project_id)
            setup_logging()
            
            logging.info(f"Starting unified GitLab Pipeline analysis for project: {project_name} (ID: {project_id})")
            logging.info(f"Analyzing data from the last {DAYS_AGO} days (since {days_ago.strftime('%Y-%m-%d')})")
            logging.info(f"Results will be saved to {output_filename}")
            
            # Fetch pipelines (we'll reuse this for all analyses)
            logging.info("Fetching pipelines data...")
            pipelines = fetch_pipelines(project_id)
            pipeline_count = len(pipelines)
            logging.info(f"Found {pipeline_count} pipelines in the last {DAYS_AGO} days.")
            
            if pipeline_count == 0:
                logging.error("No pipelines found. Skipping project.")
                continue
            
            # Open output file
            with open(output_filename, "w") as output_file:
                # Write file header
                output_file.write(f"# GitLab Pipeline Analysis Results for {project_name} (ID: {project_id})\n")
                output_file.write(f"# Generated on: {current_time}\n")
                output_file.write(f"# Analysis period: Last {DAYS_AGO} days (since {days_ago.strftime('%Y-%m-%d')})\n")
                output_file.write(f"# Total pipelines analyzed: {pipeline_count}\n\n")
                
                # ANALYSIS 1: Pipeline Runtimes by Branch
                write_section_header(output_file, "1. PIPELINE RUNTIMES BY BRANCH")
                branch_stats = analyze_pipeline_runtimes(project_id, pipelines)
                write_branch_stats(output_file, branch_stats)
                
                # ANALYSIS 2: Job Durations
                write_section_header(output_file, "2. JOB DURATIONS")
                
                # Fetch all jobs for regular duration analysis
                logging.info("Fetching jobs data for duration analysis...")
                all_jobs = []
                for i, pipeline in enumerate(pipelines):
                    pipeline_id = pipeline['id']
                    try:
                        jobs = fetch_pipeline_jobs(project_id, pipeline_id, include_retried=False)
                        all_jobs.extend(jobs)
                        if (i + 1) % 10 == 0 or (i + 1) == pipeline_count:
                            logging.info(f"Fetched jobs from {i+1}/{pipeline_count} pipelines")
                    except requests.RequestException as e:
                        logging.error(f"Failed to fetch jobs for pipeline ID {pipeline_id}: {e}")
                
                job_stats = analyze_job_durations(project_id, all_jobs)
                write_job_duration_stats(output_file, job_stats)
                
                # ANALYSIS 3: Job Retries and Reliability
                write_section_header(output_file, "3. JOB RETRIES AND RELIABILITY")
                job_retry_stats = analyze_job_retries(project_id, pipelines)
                write_job_retry_stats(output_file, job_retry_stats)
                
                # ANALYSIS 4: Retry Durations
                write_section_header(output_file, "4. RETRY DURATIONS")
                retry_stats, total_retried_jobs = analyze_retry_durations(project_id, pipelines)
                write_retry_duration_stats(output_file, retry_stats, total_retried_jobs)
                
                # Final summary
                write_section_header(output_file, "SUMMARY", char="-")
                output_file.write(f"Total pipelines analyzed: {pipeline_count}\n")
                output_file.write(f"Total unique branches: {len(branch_stats)}\n")
                output_file.write(f"Total unique job types: {len(job_stats)}\n")
                output_file.write(f"Total retried jobs: {total_retried_jobs}\n")
                
                # Calculate overall reliability rate
                total_runs = sum(stats['total_runs'] for stats in job_retry_stats.values())
                total_retries = sum(stats['retries'] for stats in job_retry_stats.values())
                if total_runs > 0:
                    overall_reliability = ((total_runs - total_retries) / total_runs) * 100
                    output_file.write(f"Overall pipeline reliability rate: {overall_reliability:.2f}%\n")
                    
            logging.info(f"Analysis complete! Results saved to {output_filename}")
            logging.info(f"Log file saved to {log_filename}")
            all_generated_files.append(output_filename)
            all_generated_files.append(log_filename)

        # Create a timestamped folder and zip the results
        if all_generated_files:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = f"pipeline_audit_results_{timestamp}"
            
            os.makedirs(folder_name, exist_ok=True)
            logging.info(f"Created directory: {folder_name}")

            for file_path in all_generated_files:
                if os.path.exists(file_path):
                    shutil.move(file_path, os.path.join(folder_name, os.path.basename(file_path)))
            
            logging.info(f"Moved all result files to {folder_name}")

            # Create a zip file of the folder
            shutil.make_archive(folder_name, 'zip', folder_name)
            logging.info(f"Successfully created zip file: {folder_name}.zip")
            
    except requests.RequestException as e:
        logging.error(f"API Error: {e}")
        return
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return

if __name__ == "__main__":
    main()
