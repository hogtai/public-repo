# Migrate GitLab Secrets to Doppler

## Overview

`main.py` is a Python script that automates the backup, deletion, restoration, and migration of GitLab secrets to **Doppler**, with optional backup storage in **Google Cloud Storage (GCS)**.

## Features

- **Backup GitLab secrets** to a local JSON file and upload them to GCS.
- **Delete all GitLab secrets** after backing them up (optional).
- **Restore GitLab secrets** from a GCS-stored backup.
- **Migrate GitLab secrets to Doppler** while maintaining references and security policies.
- **Automatically create Doppler projects** if they do not exist.
- **Support for GitLab projects and groups**.

## Prerequisites

Before running the script, ensure you have:

- **Python 3.x** installed.
- Required Python dependencies: `gitlab`, `google-cloud-storage`, `requests`, `argparse`.
- A **GitLab Access Token** with permissions to manage secrets.
- A **Doppler API Token** with project management access.
- A **Google Cloud Storage (GCS) bucket** (if using backup storage).
- A configured Google Cloud authentication.

## Installation

1. **Clone the repository**:
   ```sh
   git clone <repo_url>
   cd <repo_directory>
   ```

2. **Install dependencies**:
   ```sh
   pip install -r requirements.txt
   ```
   *(If `requirements.txt` is not available, install manually:)*  
   ```sh
   pip install gitlab google-cloud-storage requests argparse
   ```

## Usage

### Command-Line Arguments

```
usage: main.py [-h] --gitlab-token GITLAB_TOKEN --doppler-token DOPPLER_TOKEN
                           --gitlab-id GITLAB_ID --gitlab-type {project,group}
                           [--gitlab-url GITLAB_URL] [--bucket-name BUCKET_NAME]
                           [--bucket-path BUCKET_PATH] [--delete-secrets]
                           [--restore-secrets]
```

### Example Commands

#### 1. **Backup GitLab Secrets and Upload to GCS**
```sh
python main.py --gitlab-token <your_gitlab_token> --doppler-token <your_doppler_token> \
--gitlab-id <project_or_group_id>
```

#### 2. **Delete GitLab Secrets After Backup**
```sh
python main.py --gitlab-token <your_gitlab_token> --doppler-token <your_doppler_token> \
--gitlab-id <project_or_group_id> --delete-secrets
```

#### 3. **Restore GitLab Secrets from GCS Backup**
```sh
python main.py --gitlab-token <your_gitlab_token> --doppler-token <your_doppler_token> \
--gitlab-id <project_or_group_id> --restore-secrets
```

### Parameters:

| Argument            | Required | Description |
|---------------------|----------|-------------|
| `--gitlab-token`   | ✅ Yes    | GitLab Access Token for authentication |
| `--doppler-token`  | ✅ Yes    | Doppler API Token for authentication |
| `--gitlab-id`      | ✅ Yes    | GitLab Project/Group ID |
| `--gitlab-type`    | No       | Specify whether the ID corresponds to a **project** or a **group** (`project` or `group`) Default: `project`|
| `--gitlab-url`     | No       | GitLab instance URL (default: `https://gitlab.com`) |
| `--bucket-name`    | No       | GCS bucket name for storing backups (default: `rms-sre-storage`) |
| `--bucket-path`    | No       | Path inside the GCS bucket (default: `secrets-backup`) |
| `--delete-secrets` | No       | Delete all GitLab secrets after backup |
| `--restore-secrets` | No      | Restore secrets from backup |

## How It Works

1. **Retrieves** all environment variables/secrets from a GitLab project or group.
2. **Backs up** the secrets to a JSON file.
3. **Uploads** the backup file to GCS.
4. **Deletes secrets** from GitLab (if the `--delete-secrets` flag is set).
5. **Restores secrets** from a backup file ( if the `--restore-secrets` flag is set.
6. **Creates a Doppler project** if it does not exist.
7. **Uploads secrets** to Doppler and ensures references to shared secrets.

## Notes

- **Caution when using `--delete-secrets`**: Once secrets are deleted, they cannot be recovered unless backed up first.
- The script automatically maps GitLab environment variables to Doppler configurations.
- Ensure that **GCP authentication is set up** properly before using backup functionalities.
