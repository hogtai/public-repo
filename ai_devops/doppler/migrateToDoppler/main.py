import gitlab
import json
import os
import argparse
import warnings
from google.cloud import storage
import sys
import time
import requests

# Suppress google-crc32c warnings
warnings.simplefilter("ignore", RuntimeWarning)

# Parse arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Backup, upload, delete, and restore GitLab secrets for both projects and groups.")
    parser.add_argument("--gitlab-token", required=True, help="GitLab Access Token")
    parser.add_argument("--doppler-token", required=True, help="Doppler API Token")
    parser.add_argument("--gitlab-id", required=True, help="GitLab project or group ID")
    parser.add_argument("--gitlab-type", choices=["project", "group"], default="project", required=True, help="Specify whether the ID corresponds to a project or a group")
    parser.add_argument("--gitlab-url", default="https://gitlab.com", help="GitLab instance URL")
    parser.add_argument("--bucket-name", default="rms-sre-storage", help="GCP bucket name")
    parser.add_argument("--bucket-path", default="secrets-backup", help="Path inside GCP bucket")
    parser.add_argument("--delete-secrets", action="store_true", help="Delete all GitLab secrets after backup")
    parser.add_argument("--restore-secrets", action="store_true", help="Restore secrets from the backup file")
    return parser.parse_args()

def generate_doppler_config_name(gitlab_path, getParent=False):
    if getParent:
        full_path = gitlab_path.split('/')[-2] if '/' in gitlab_path else gitlab_path
        if full_path == "digital-product":
            full_path = "base"
        
    else:
        """
        Generate the Doppler configuration name based on the GitLab path.
        Replace '/' with '-', but leave '-' unchanged.
        """
        full_path = gitlab_path.replace("/", "-")
        full_path = full_path.replace("lifechurch-io-digital-product-", "")

    return f"gitlab-{full_path}"

def check_or_create_doppler_project(project_name, doppler_token):
    """
    Check if a Doppler project exists, and create it if not.
    """
    url = "https://api.doppler.com/v3/projects"
    headers = {"Authorization": f"Bearer {doppler_token}"}

    # Check existing projects
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    projects = response.json()["projects"]

    if any(project["name"] == project_name for project in projects):
        print(f"Doppler project '{project_name}' already exists.")
    else:
        # Create the project if it doesn't exist
        payload = {"name": project_name}
        create_response = requests.post(url, json=payload, headers=headers)
        create_response.raise_for_status()
        print(f"Created Doppler project '{project_name}'.")

def get_gitlab_entity(gitlab_url, gitlab_token, gitlab_id, entity_type):
    try:
        gl = gitlab.Gitlab(gitlab_url, private_token=gitlab_token)
        if entity_type == "project":
            return gl.projects.get(gitlab_id)
        else:
            return gl.groups.get(gitlab_id)
    except gitlab.exceptions.GitlabAuthenticationError:
        print("Authentication Error. Please verify your token.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def get_secrets(entity):
    return entity.variables.list(get_all=True)

def backup_secrets(entity, entity_type):
    secrets = get_secrets(entity)
    data = []
    for secret in secrets:
        data.append(
            {
                "key": secret.key,
                "value": secret.value,
                "environment_scope": secret.environment_scope,
                "protected": secret.protected,
                "masked": secret.masked,
                "variable_type": secret.variable_type,
                "description": secret.description or "",
            }
        )
    file_name = f"{entity.name}_{entity.id}_secrets.json"
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Backup completed and saved to {file_name}")
    return file_name


def download_from_gcs(file_name, bucket_name, bucket_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{bucket_path}/{file_name}")
    blob.download_to_filename(file_name)
    print(f"Backup file downloaded from gs://{bucket_name}/{bucket_path}/{file_name}")


def delete_all_secrets(entity, bucket_name, bucket_path):
    file_name = f"{entity.name}_{entity.id}_secrets.json"
    download_from_gcs(file_name, bucket_name, bucket_path)
    
    # print("Backup file content before deletion:")
    # with open(file_name, "r") as f:
    #     print(f.read())
    
    # Prompt user for confirmation
    confirm = input("Are you sure you want to delete all secrets? This action is irreversible. (yes/no): ").strip().lower()
    if confirm not in ["yes", "y"]:
        print("Deletion aborted.")
        return

    secrets = get_secrets(entity)
    for secret in secrets:
        entity.variables.delete(secret.key)
    print("All secrets deleted.")


def restore_secrets(entity, file_name, bucket_name, bucket_path):
    try:
        download_from_gcs(file_name, bucket_name, bucket_path)
        with open(file_name, "r") as f:
            secrets = json.load(f)
        for secret in secrets:
            entity.variables.create(
                {
                    "key": secret["key"],
                    "value": secret["value"],
                    "protected": secret["protected"],
                    "masked": secret["masked"],
                    "variable_type": secret["variable_type"],
                    "environment_scope": secret["environment_scope"],
                    "description": secret["description"],
                }
            )
        print("Secrets restored successfully.")
    except Exception as e:
        print(f"Failed to restore secrets: {e}")


def upload_to_gcs(file_name, bucket_name, bucket_path):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"{bucket_path}/{file_name}")
    blob.upload_from_filename(file_name)
    print(f"Backup file uploaded to gs://{bucket_name}/{bucket_path}/{file_name}")


def get_doppler_project_secrets(doppler_token, project_name):
    url = f"https://api.doppler.com/v3/configs?project={project_name}"
    headers = {"Authorization": f"Bearer {doppler_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    configs = response.json().get("configs", [])
    all_secrets = {}
    for config in configs:
        config_name = config["name"]
        secrets_url = f"https://api.doppler.com/v3/configs/config/secrets?project={project_name}&config={config_name}"
        response = requests.get(secrets_url, headers=headers)
        response.raise_for_status()
        secrets = response.json().get("secrets", {})
        for key, secret_data in secrets.items():
            if isinstance(secret_data, dict) and "raw" in secret_data:
                secret_value = secret_data["raw"].strip()
                all_secrets[secret_value] = f"${{{project_name}.{config_name}.{key}}}"
    return all_secrets

def upload_secrets_to_doppler(doppler_project, doppler_parent, entity, gitlab_token, doppler_token):
    print(f"Uploading secrets to Doppler... https://dashboard.doppler.com/workplace/428509ea97ee92f547c1/projects/{doppler_project}")

    case_alert_needed = False
    case_alert_variables = []
    
    check_or_create_doppler_project(doppler_project, doppler_token)
    
    existing_secrets = get_doppler_project_secrets(doppler_token, "live_clusters")
    
    url = "https://api.doppler.com/v3/configs/config/secrets"
    headers = {"Authorization": f"Bearer {doppler_token}", "Content-Type": "application/json"}
    
    secrets = {}
    change_requests = []
    for var in entity.variables.list(get_all=True):
        if not var.key.isupper():
            case_alert_needed = True
            case_alert_variables.append(var.key)

        key = var.key.upper()
        value = var.value.strip()
        if value != "":  # Do not try to match empty variables to Cluster Secrets
            value = existing_secrets.get(value, var.value)

            secrets[key] = value

            # Create change request to unmask secrets that are references to live_cluster secrets
            if value.startswith("${live_clusters."):
                change_requests.append({
                    "name": key,
                    "originalName": key,
                    "value": value,
                    "originalValue": value,
                    "visibility": "unmasked"
                })
    
    secrets['DOPPLER_PARENT'] = doppler_parent
    change_requests.append({
        "name": "DOPPLER_PARENT",
        "originalName": "DOPPLER_PARENT",
        "value": doppler_parent,
        "originalValue": doppler_parent,
        "visibility": "unmasked"
    })
    
    for env in ["dev", "stg", "prd"]:
        payload = {"project": doppler_project, "config": env, "secrets": secrets}
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"Successfully uploaded secrets to Doppler {env}")
        else:
            print(f"Failed to upload secrets to Doppler {env}: {response.text}")
    
    # Apply change requests to unmask secrets
    if change_requests:
        for env in ["dev", "stg", "prd"]:
            change_payload = {"project": doppler_project, "config": env, "change_requests": change_requests}
            change_response = requests.post(url, json=change_payload, headers=headers)
            if change_response.status_code == 200:
                print(f"Successfully updated visibility of referenced secrets in Doppler {env}")
            else:
                print(f"Failed to update visibility of referenced secrets in Doppler {env}: {change_response.text}")

    return case_alert_needed, case_alert_variables

def main():
    args = parse_args()
    entity = get_gitlab_entity(args.gitlab_url, args.gitlab_token, args.gitlab_id, args.gitlab_type)
    
    # Generate Doppler project name
    doppler_project_name = generate_doppler_config_name(entity.full_path if hasattr(entity, 'full_path') else entity.path_with_namespace)
    doppler_parent_name = generate_doppler_config_name(entity.full_path if hasattr(entity, 'full_path') else entity.path_with_namespace, True)

    if args.delete_secrets:
        delete_all_secrets(entity, args.bucket_name, args.bucket_path)
        return
    
    if args.restore_secrets:
        file_name = f"{entity.name}_{entity.id}_secrets.json"
        restore_secrets(entity, file_name, args.bucket_name, args.bucket_path)
        return
    
    file_name = backup_secrets(entity, args.gitlab_type)
    # print(f"Backup file content:")
    # with open(file_name, "r") as f:
    #     print(f.read())
    upload_to_gcs(file_name, args.bucket_name, args.bucket_path)
    case_alert_needed, case_alert_variables = upload_secrets_to_doppler(doppler_project_name, doppler_parent_name, entity, args.gitlab_token, args.doppler_token)

    if case_alert_needed:
        print()
        print('#############################################################')
        print('#############################################################')
        print()
        print('The following variables are defined as lowercase in GitLab')
        print('CI Secrets. They will betransformed to UPPERCASE when sent')
        print('to doppler.')
        print()
        print('[ACTION] Verify with App Team if this will be a problem')
        print()
        print('#############################################################')
        print('#############################################################')
        print()
        print('Variables Affected: ')
        for v in case_alert_variables:
            print(' - ' + v + ' -> ' + v.upper() )

        print()
        print('#############################################################')
        print('#############################################################')

if __name__ == "__main__":
    main()
