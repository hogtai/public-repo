import requests
import logging
import re
import sys
import os
import shutil
import zipfile
import time
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# GitLab project details
GITLAB_URL = "https://gitlab.com"
PROJECT_IDS = [
    "64459882",  # Mobile - LC-App
]
ACCESS_TOKEN = os.environ.get("GITLAB_ACCESS_TOKEN")  # Replace with your GitLab access token

# Performance tuning based on GitLab API limits:
# - Authenticated API: 7,200 req/hour = 2 req/sec average
# - Jobs API: 600 req/min = 10 req/sec
# - Safe concurrency: 8 workers (allows 8 req/sec with headroom)
MAX_WORKERS = 8  # Optimal concurrency for GitLab.com rate limits
RETRY_ATTEMPTS = 3  # Number of retries for failed requests
RETRY_BACKOFF = 2  # Exponential backoff multiplier

# Headers for the API requests
headers = {
    "Private-Token": ACCESS_TOKEN
}

# Rate limit tracking
rate_limit_remaining = None
rate_limit_reset = None

# Calculate date range (default 30 days)
DAYS_AGO = 30  # From April 1, 2025 to present (253 Days as of 12/10/25)
days_ago = datetime.now() - timedelta(days=DAYS_AGO)
days_ago_iso = days_ago.isoformat()

# Global variables for output
project_name = ""
sanitized_project_name = ""
output_filename = ""
log_filename = ""

def setup_logging():
    """
    Configure logging to output to both console and file
    """
    global log_filename
    log_filename = f"{sanitized_project_name}_flakiness_analysis_log.txt"

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
    """
    Fetch the project name using the GitLab API.
    """
    global project_name, sanitized_project_name, output_filename

    url = f"{GITLAB_URL}/api/v4/projects/{project_id}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    project_data = response.json()
    project_name = project_data['name']
    sanitized_project_name = sanitize_filename(project_name)
    output_filename = f"{sanitized_project_name}_flakiness_analysis_results.txt"

    return project_name

def sanitize_filename(name):
    """
    Sanitize the project name to create a valid filename.
    """
    # Remove any character that is not alphanumeric, a space, or one of -_.
    sanitized_name = re.sub(r'[^\w\s\-_]', '', name)
    # Replace spaces with underscores
    sanitized_name = sanitized_name.replace(' ', '_')
    return sanitized_name

def fetch_pipelines(project_id):
    """
    Fetch all pipelines updated in the specified date range.
    Uses Link header for pagination (GitLab best practice).
    """
    pipelines = []
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipelines"
    params = {
        "updated_after": days_ago_iso,
        "per_page": 100,  # Maximum allowed by GitLab API
    }

    while url:
        response = make_api_request_with_retry(url, params)
        data = response.json()

        if not data:
            break

        pipelines.extend(data)

        # Use Link header for next page
        link_header = response.headers.get('Link', '')
        next_url = None

        for link in link_header.split(','):
            if 'rel="next"' in link:
                next_url = link[link.find('<') + 1:link.find('>')]
                break

        url = next_url
        params = None  # URL from Link header already has params

    return pipelines

def update_rate_limit_info(response):
    """
    Update global rate limit tracking from response headers.
    """
    global rate_limit_remaining, rate_limit_reset

    if 'RateLimit-Remaining' in response.headers:
        rate_limit_remaining = int(response.headers['RateLimit-Remaining'])

        if rate_limit_remaining < 100:
            logging.warning(f"Rate limit warning: Only {rate_limit_remaining} requests remaining")

    if 'RateLimit-Reset' in response.headers:
        rate_limit_reset = int(response.headers['RateLimit-Reset'])

def make_api_request_with_retry(url, params=None):
    """
    Make an API request with exponential backoff retry logic.
    Monitors rate limits and handles 429 Too Many Requests.
    """
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)

            # Update rate limit info
            update_rate_limit_info(response)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logging.warning(f"Rate limit hit (429). Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            return response

        except requests.RequestException as e:
            if attempt < RETRY_ATTEMPTS - 1:
                wait_time = RETRY_BACKOFF ** attempt
                logging.warning(f"Request failed (attempt {attempt + 1}/{RETRY_ATTEMPTS}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"Request failed after {RETRY_ATTEMPTS} attempts: {e}")
                raise

    raise requests.RequestException("Max retries exceeded")

def fetch_pipeline_jobs(project_id, pipeline_id, include_retried=False):
    """
    Fetch all jobs for a specific pipeline with pagination.
    Uses Link header for efficient pagination (GitLab best practice).
    """
    jobs = []
    url = f"{GITLAB_URL}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    params = {
        "per_page": 100,  # Maximum allowed by GitLab API
    }

    if include_retried:
        params["include_retried"] = "true"

    while url:
        response = make_api_request_with_retry(url, params)
        data = response.json()

        if not data:
            break

        jobs.extend(data)

        # Use Link header for next page (GitLab best practice)
        link_header = response.headers.get('Link', '')
        next_url = None

        for link in link_header.split(','):
            if 'rel="next"' in link:
                next_url = link[link.find('<') + 1:link.find('>')]
                break

        url = next_url
        params = None  # URL from Link header already has params

    return jobs

def write_section_header(file, title, char="=", width=100):
    """
    Write a formatted section header to the output file
    """
    file.write("\n")
    file.write(char * width + "\n")
    file.write(f"{title}\n")
    file.write(char * width + "\n\n")

    # Also log to console
    logging.info("\n" + char * width)
    logging.info(title)
    logging.info(char * width + "\n")

def fetch_pipeline_jobs_with_metadata(project_id, pipeline):
    """
    Fetch jobs for a pipeline and return with pipeline metadata.
    This function is designed to be called concurrently.
    """
    pipeline_id = pipeline['id']
    try:
        jobs = fetch_pipeline_jobs(project_id, pipeline_id, include_retried=True)
        return {
            'pipeline_id': pipeline_id,
            'pipeline': pipeline,
            'jobs': jobs,
            'success': True,
            'error': None
        }
    except requests.RequestException as e:
        return {
            'pipeline_id': pipeline_id,
            'pipeline': pipeline,
            'jobs': [],
            'success': False,
            'error': str(e)
        }

def analyze_flakiness_vs_legitimate_failures(project_id, pipelines):
    """
    Analyze job failures to distinguish between:
    1. Flakey tests: Jobs that failed but eventually succeeded on retry
    2. Legitimate failures: Jobs that failed and all retries also failed (bad code)

    Returns detailed statistics for both categories.
    """
    logging.info("Starting flakiness vs legitimate failure analysis...")

    # Statistics tracking
    job_stats = defaultdict(lambda: {
        'total_job_groups': 0,           # Total number of times this job was executed (across all pipelines)
        'flakey_occurrences': 0,         # Times job failed but eventually succeeded (FLAKEY)
        'legitimate_failures': 0,        # Times job failed and all retries failed (BAD CODE)
        'clean_successes': 0,            # Times job succeeded on first try (no retries needed)
        'other_statuses': 0,             # Times job had other statuses (canceled, skipped, etc.)
        'total_retry_attempts': 0,       # Total number of retry attempts across all job groups
        'flakey_retry_attempts': 0,      # Retry attempts that were due to flakiness
        'legitimate_retry_attempts': 0,  # Retry attempts that were due to bad code
        'flakey_pipelines': [],          # List of pipeline IDs where flakiness occurred
    })

    # Track all flakey occurrences for detailed reporting
    flakey_details = []

    total_count = len(pipelines)
    processed_count = 0

    # Fetch jobs for all pipelines concurrently
    # Using MAX_WORKERS (8) optimized for GitLab API rate limits
    logging.info(f"Fetching jobs for {total_count} pipelines concurrently (max {MAX_WORKERS} workers)...")

    pipeline_results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all fetch jobs
        future_to_pipeline = {
            executor.submit(fetch_pipeline_jobs_with_metadata, project_id, pipeline): pipeline
            for pipeline in pipelines
        }

        # Process results as they complete
        for future in as_completed(future_to_pipeline):
            result = future.result()
            pipeline_results.append(result)

            processed_count += 1
            if processed_count % 10 == 0 or processed_count == total_count:
                logging.info(f"Fetched jobs from {processed_count}/{total_count} pipelines")

    logging.info(f"Successfully fetched jobs for {total_count} pipelines. Analyzing...")

    # Now analyze all the fetched data
    for result in pipeline_results:
        if not result['success']:
            logging.error(f"Error fetching jobs for pipeline {result['pipeline_id']}: {result['error']}")
            continue

        pipeline = result['pipeline']
        pipeline_id = result['pipeline_id']
        jobs = result['jobs']

        # Group jobs by their name within the same pipeline
        jobs_by_name = defaultdict(list)
        for job in jobs:
            jobs_by_name[job['name']].append(job)

        # Analyze each job group to determine if it's flakey or legitimate failure
        for job_name, job_list in jobs_by_name.items():
            # Sort by job ID to get chronological order (oldest first, newest last)
            job_list.sort(key=lambda x: x['id'])

            # Get statuses of all jobs in this group
            statuses = [job['status'] for job in job_list]

            # Count this job group
            job_stats[job_name]['total_job_groups'] += 1

            # Determine the number of attempts
            num_attempts = len(job_list)
            retry_count = num_attempts - 1
            job_stats[job_name]['total_retry_attempts'] += retry_count

            # Analyze the outcome pattern
            has_success = 'success' in statuses
            has_failure = 'failed' in statuses

            # Check for only other statuses (no success or failure)
            only_other_statuses = not has_success and not has_failure

            if num_attempts == 1 and job_list[0]['status'] == 'success':
                # Clean success: No retries needed, succeeded on first try
                job_stats[job_name]['clean_successes'] += 1
                logging.debug(f"Pipeline {pipeline_id}, Job '{job_name}': Clean success (no retries)")

            elif has_failure and has_success:
                # FLAKEY TEST: Failed at least once but eventually succeeded
                job_stats[job_name]['flakey_occurrences'] += 1
                job_stats[job_name]['flakey_retry_attempts'] += retry_count
                job_stats[job_name]['flakey_pipelines'].append(pipeline_id)
                flakey_details.append({
                    'pipeline_id': pipeline_id,
                    'pipeline_ref': pipeline.get('ref', 'unknown'),
                    'job_name': job_name,
                    'num_attempts': num_attempts,
                    'statuses': statuses
                })
                logging.info(f"Pipeline {pipeline_id}, Job '{job_name}': FLAKEY (failed then succeeded), attempts: {num_attempts}, statuses: {statuses}")

            elif has_failure and not has_success:
                # LEGITIMATE FAILURE: Failed and all retries also failed (bad code)
                job_stats[job_name]['legitimate_failures'] += 1
                job_stats[job_name]['legitimate_retry_attempts'] += retry_count
                logging.debug(f"Pipeline {pipeline_id}, Job '{job_name}': LEGITIMATE FAILURE (all attempts failed), attempts: {num_attempts}")

            elif only_other_statuses:
                # Other statuses: canceled, skipped, manual, running, etc.
                job_stats[job_name]['other_statuses'] += 1
                logging.debug(f"Pipeline {pipeline_id}, Job '{job_name}': Other statuses (no success/failure): {statuses}")

            elif has_success and not has_failure and num_attempts > 1:
                # Multiple attempts but all succeeded (shouldn't happen with retry: 2 logic, but handle it)
                job_stats[job_name]['clean_successes'] += 1
                logging.warning(f"Pipeline {pipeline_id}, Job '{job_name}': Unexpected - multiple attempts all succeeded: {statuses}")

            else:
                # Truly unexpected edge case
                job_stats[job_name]['other_statuses'] += 1
                logging.warning(f"Pipeline {pipeline_id}, Job '{job_name}': Unexpected status pattern: {statuses}")

    logging.info(f"Flakiness analysis completed for {len(job_stats)} job types.")
    return job_stats, flakey_details

def write_flakiness_analysis_stats(file, job_stats, flakey_details):
    """
    Write comprehensive flakiness analysis statistics to the output file.
    """
    file.write("=" * 150 + "\n")
    file.write("FLAKINESS ANALYSIS - Distinguishing Flakey Tests from Legitimate Failures\n")
    file.write("=" * 150 + "\n\n")

    file.write("DEFINITIONS:\n")
    file.write("  - Flakey Test: Job failed initially but succeeded on retry (reliability issue)\n")
    file.write("  - Legitimate Failure: Job failed and all retries also failed (bad code, not reliability issue)\n")
    file.write("  - Clean Success: Job succeeded on first attempt (no retries needed)\n")
    file.write("  - Other: Job had non-success/failure status (canceled, skipped, manual, running, etc.)\n")
    file.write("  - Flakiness Rate: Percentage of job executions that exhibited flakiness\n")
    file.write("  - Reliability Rate: Clean successes / (Clean successes + Flakey tests) - excludes bad code & other\n\n")

    # Calculate totals
    total_job_groups = sum(stats['total_job_groups'] for stats in job_stats.values())
    total_flakey = sum(stats['flakey_occurrences'] for stats in job_stats.values())
    total_legitimate = sum(stats['legitimate_failures'] for stats in job_stats.values())
    total_clean = sum(stats['clean_successes'] for stats in job_stats.values())
    total_other = sum(stats['other_statuses'] for stats in job_stats.values())

    # Write summary
    file.write("OVERALL SUMMARY:\n")
    file.write(f"  Total job executions analyzed: {total_job_groups}\n")
    file.write(f"  Clean successes (no retries): {total_clean} ({total_clean/total_job_groups*100:.2f}%)\n")
    file.write(f"  Flakey test occurrences: {total_flakey} ({total_flakey/total_job_groups*100:.2f}%)\n")
    file.write(f"  Legitimate failures: {total_legitimate} ({total_legitimate/total_job_groups*100:.2f}%)\n")
    file.write(f"  Other statuses (canceled/skipped): {total_other} ({total_other/total_job_groups*100:.2f}%)\n\n")

    if total_job_groups > 0:
        # Flakiness Rate: Only accounts for flakey tests, not legitimate failures
        flakiness_rate = (total_flakey / total_job_groups) * 100
        # Reliability Rate: Clean successes / (Clean successes + Flakey tests)
        # Note: Legitimate failures are excluded from this calculation
        non_legitimate_total = total_clean + total_flakey
        if non_legitimate_total > 0:
            reliability_rate = (total_clean / non_legitimate_total) * 100
        else:
            reliability_rate = 100.0

        file.write(f"  ** FLAKINESS RATE: {flakiness_rate:.2f}% **\n")
        file.write(f"  ** RELIABILITY RATE (excluding bad code): {reliability_rate:.2f}% **\n\n")

    # Detailed per-job statistics
    file.write("\n" + "=" * 150 + "\n")
    file.write("DETAILED JOB-BY-JOB ANALYSIS\n")
    file.write("=" * 150 + "\n\n")

    header = (
        f"{'Job Name':<40} "
        f"{'Total Runs':<12} "
        f"{'Clean Success':<14} "
        f"{'Flakey':<8} "
        f"{'Bad Code':<10} "
        f"{'Other':<8} "
        f"{'Flakiness %':<13} "
        f"{'Reliability %':<15}\n"
    )
    file.write(header)
    file.write("=" * 160 + "\n")

    for job_name, stats in sorted(job_stats.items()):
        total = stats['total_job_groups']
        clean = stats['clean_successes']
        flakey = stats['flakey_occurrences']
        legitimate = stats['legitimate_failures']
        other = stats['other_statuses']

        if total > 0:
            flakiness_pct = (flakey / total) * 100

            # Reliability rate excludes legitimate failures AND other statuses
            non_legitimate = clean + flakey
            if non_legitimate > 0:
                reliability_pct = (clean / non_legitimate) * 100
            else:
                reliability_pct = 0.0
        else:
            flakiness_pct = 0.0
            reliability_pct = 0.0

        line = (
            f"{job_name:<40} "
            f"{total:<12} "
            f"{clean:<14} "
            f"{flakey:<8} "
            f"{legitimate:<10} "
            f"{other:<8} "
            f"{flakiness_pct:<13.2f} "
            f"{reliability_pct:<15.2f}\n"
        )
        file.write(line)

    file.write("\n")

    # Retry attempts breakdown
    file.write("\n" + "=" * 150 + "\n")
    file.write("RETRY ATTEMPTS BREAKDOWN\n")
    file.write("=" * 150 + "\n\n")

    header_retry = (
        f"{'Job Name':<40} "
        f"{'Total Retries':<15} "
        f"{'Flakey Retries':<16} "
        f"{'Bad Code Retries':<18}\n"
    )
    file.write(header_retry)
    file.write("=" * 150 + "\n")

    total_all_retries = 0
    total_flakey_retries = 0
    total_legit_retries = 0

    for job_name, stats in sorted(job_stats.items()):
        total_retries = stats['total_retry_attempts']
        flakey_retries = stats['flakey_retry_attempts']
        legit_retries = stats['legitimate_retry_attempts']

        total_all_retries += total_retries
        total_flakey_retries += flakey_retries
        total_legit_retries += legit_retries

        if total_retries > 0:
            line = (
                f"{job_name:<40} "
                f"{total_retries:<15} "
                f"{flakey_retries:<16} "
                f"{legit_retries:<18}\n"
            )
            file.write(line)

    file.write("=" * 150 + "\n")
    totals_line = (
        f"{'TOTALS':<40} "
        f"{total_all_retries:<15} "
        f"{total_flakey_retries:<16} "
        f"{total_legit_retries:<18}\n"
    )
    file.write(totals_line)
    file.write("\n")

    # Flakey test details section
    if flakey_details:
        file.write("\n" + "=" * 150 + "\n")
        file.write("FLAKEY TEST DETAILS - Specific Pipelines Where Flakiness Occurred\n")
        file.write("=" * 150 + "\n\n")
        file.write("These are the specific pipeline executions where tests failed then succeeded on retry.\n")
        file.write("Investigate these pipelines to understand the root cause of test flakiness.\n\n")

        # Calculate dynamic column widths based on actual data
        pipeline_id_width = max(len("Pipeline ID"), max(len(str(d['pipeline_id'])) for d in flakey_details))
        branch_ref_width = max(len("Branch/Ref"), max(len(str(d['pipeline_ref'])) for d in flakey_details))
        job_name_width = max(len("Job Name"), max(len(str(d['job_name'])) for d in flakey_details))
        attempts_width = max(len("Attempts"), max(len(str(d['num_attempts'])) for d in flakey_details))
        # Calculate status pattern width
        status_widths = [len(' → '.join(d['statuses'])) for d in flakey_details]
        status_pattern_width = max(len("Status Pattern"), max(status_widths) if status_widths else 0)

        # Write header with dynamic widths
        header_details = (
            f"{'Pipeline ID':<{pipeline_id_width}} "
            f"{'Branch/Ref':<{branch_ref_width}} "
            f"{'Job Name':<{job_name_width}} "
            f"{'Attempts':<{attempts_width}} "
            f"{'Status Pattern':<{status_pattern_width}}\n"
        )
        file.write(header_details)

        # Calculate total width for separator line
        total_width = pipeline_id_width + branch_ref_width + job_name_width + attempts_width + status_pattern_width + 4
        file.write("=" * total_width + "\n")

        # Write data rows with same dynamic widths
        for detail in flakey_details:
            pipeline_url = f"https://gitlab.com/lifechurch/io/digital-product/interactions/lc-app/-/pipelines/{detail['pipeline_id']}"
            status_str = ' → '.join(detail['statuses'])
            line = (
                f"{detail['pipeline_id']:<{pipeline_id_width}} "
                f"{detail['pipeline_ref']:<{branch_ref_width}} "
                f"{detail['job_name']:<{job_name_width}} "
                f"{detail['num_attempts']:<{attempts_width}} "
                f"{status_str:<{status_pattern_width}}\n"
            )
            file.write(line)

        file.write("\n")
        file.write("TIP: View these pipelines in GitLab to investigate why the tests failed initially:\n")
        for detail in flakey_details:
            pipeline_url = f"https://gitlab.com/lifechurch/io/digital-product/interactions/lc-app/-/pipelines/{detail['pipeline_id']}"
            file.write(f"  - {pipeline_url}\n")
        file.write("\n")

def main():
    """
    Main function that runs the flakiness analysis
    """
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        all_generated_files = []

        for project_id in PROJECT_IDS:
            # Initialization
            global project_name, sanitized_project_name, output_filename
            project_name = fetch_project_name(project_id)
            setup_logging()

            logging.info(f"Starting GitLab Flakiness Analysis for project: {project_name} (ID: {project_id})")
            logging.info(f"Analyzing data from the last {DAYS_AGO} days (since {days_ago.strftime('%Y-%m-%d')})")
            logging.info(f"Results will be saved to {output_filename}")

            # Fetch pipelines
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
                output_file.write(f"# GitLab Flakiness Analysis Results for {project_name} (ID: {project_id})\n")
                output_file.write(f"# Generated on: {current_time}\n")
                output_file.write(f"# Analysis period: Last {DAYS_AGO} days (since {days_ago.strftime('%Y-%m-%d')})\n")
                output_file.write(f"# Total pipelines analyzed: {pipeline_count}\n\n")

                output_file.write("=" * 100 + "\n")
                output_file.write("PURPOSE: Distinguish Flakey Tests from Legitimate Code Failures\n")
                output_file.write("=" * 100 + "\n\n")

                output_file.write("This analysis accounts for the automatic retry logic (retry: 2) configured in\n")
                output_file.write("the LC-App GitLab CI templates. It distinguishes between:\n\n")
                output_file.write("1. FLAKEY TESTS: Jobs that fail initially but succeed on retry\n")
                output_file.write("   - These indicate test reliability issues\n")
                output_file.write("   - Count AGAINST the reliability rate\n\n")
                output_file.write("2. LEGITIMATE FAILURES: Jobs that fail and all retries also fail\n")
                output_file.write("   - These indicate bad code being pushed\n")
                output_file.write("   - Do NOT count against the reliability rate (not a test reliability issue)\n\n")
                output_file.write("3. CLEAN SUCCESSES: Jobs that succeed on the first attempt\n")
                output_file.write("   - No retries needed\n")
                output_file.write("   - Ideal scenario\n\n")

                # Run flakiness analysis
                job_stats, flakey_details = analyze_flakiness_vs_legitimate_failures(project_id, pipelines)
                write_flakiness_analysis_stats(output_file, job_stats, flakey_details)

            logging.info(f"Analysis complete! Results saved to {output_filename}")
            logging.info(f"Log file saved to {log_filename}")
            all_generated_files.append(output_filename)
            all_generated_files.append(log_filename)

        # Create a timestamped folder and zip the results
        if all_generated_files:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = f"flakiness_analysis_results_{timestamp}"

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
