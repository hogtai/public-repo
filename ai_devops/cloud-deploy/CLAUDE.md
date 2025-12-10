# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a GCP Cloud Deploy CI/CD template system that automates continuous deployment of applications into GKE environments. It replaces the deprecated Kubernetes Deploy Helper (k8s-deploy-helper) which relied on certificate-based authentication that Google has deprecated.

**Key Purpose**: The project provides reusable GitLab CI/CD pipeline templates that other projects include to enable automated deployment via GCP Cloud Deploy.

## Architecture

### Pipeline Flow

The system operates as a **shared CI/CD template** that application projects include in their `.gitlab-ci.yml`:

1. **Application projects** include this template via GitLab's `include` directive
2. The template provides pre-built jobs for different deployment stages
3. Each job renders Kubernetes manifests with environment variables, then creates GCP Cloud Deploy releases
4. GCP Cloud Deploy handles the actual rollout to GKE clusters

### Key Integration Points

**Doppler Integration**: The pipeline depends on a separate Doppler template (`lifechurch/io/digital-product/sre/cicd-tools/doppler`) included at the top of `.gitlab-ci-template.yml`. This provides the `secret` job that populates environment variables from Doppler into a `bash.env` artifact.

**Variable Substitution Flow**:
- Doppler secrets → `bash.env` artifact (from the `secret` job dependency)
- Environment variables sourced from `bash.env` in `before_script`
- `envsubst` renders Kubernetes YAML templates using these variables
- Rendered manifests validated with `kubeconform` before deployment

**Namespace and Secret Management**:
- Namespace and ClusterSecretStore YAML files are processed first (lines 44-49 in template)
- Then remaining manifests are processed (lines 51-55)
- This ordering ensures secrets infrastructure exists before dependent resources deploy

### Deployment Environments

Three separate manifest directories under `kubernetes/`:
- **review/**: Feature branch review apps (auto-deployed, auto-expire after 30 days)
- **staging/**: Staging environment (develop/staging/integration branches)
- **production/**: Production environment (main branch, manual trigger)

Each uses the same template structure with different variable values.

## Cloud Deploy Release Naming Convention

Releases follow a strict naming pattern required by GCP:
- **Review Apps**: `r${CI_PROJECT_ID}-${TRUNCATED_SHA}-${TIMESTAMP}`
- **Staging**: `stg${CI_PROJECT_ID}-${TRUNCATED_SHA}-${TIMESTAMP}`
- **Production**: `prd${CI_PROJECT_ID}-${TRUNCATED_SHA}-${TIMESTAMP}`

Where:
- `TRUNCATED_SHA`: First 6 characters of commit SHA (lowercase)
- `TIMESTAMP`: `YYYYMMDD-HHMM` in America/Chicago timezone

## Common Commands

### Manifest Validation

The pipeline automatically validates rendered manifests using kubeconform:
```bash
cat rendered-manifests/rendered.yaml | kubeconform --summary --strict --verbose --output pretty \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
```

### Manual Environment Variable Rendering

To test manifest rendering locally:
```bash
# Source your environment variables first
export KUBE_NAMESPACE=test-namespace
export CI_COMMIT_REF_SLUG=my-branch
export CI_PROJECT_NAME=my-project
# ... etc

# Render a single manifest
envsubst "$(env | cut -d= -f1 | sed 's/^/$/' | tr '\n' ' ')" < kubernetes/review/deployment.yaml
```

### Checking Cloud Deploy Status

```bash
# List recent releases for a pipeline
gcloud deploy releases list \
  --delivery-pipeline=int-staging \
  --region=us-central1

# Describe a specific rollout
gcloud deploy rollouts describe ROLLOUT_ID \
  --region=us-central1 \
  --delivery-pipeline=int-staging \
  --release=RELEASE_NAME
```

## Important Implementation Details

### The `stop:review` Job Resource Cleanup

The destroy script (lines 145-264) has complex logic for safely deleting review app resources:

1. Reads the `rendered.yaml` artifact from the corresponding `deploy:review` job
2. Pre-processes YAML to ensure proper document separation (lines 154-164)
3. Splits manifest into individual documents using `csplit`
4. Parses each document to extract `kind` and `metadata.name`
5. Only deletes specific resource kinds defined in `TARGET_KINDS` variable
6. Uses `kubectl delete` with `--ignore-not-found` for idempotency
7. Special handling for ClusterSecretStore (no namespace flag)
8. Tracks deletion failures and reports issues
9. Finally, deletes the Doppler config for the review app

**Critical**: The destroy script relies on the artifact from the deploy job to know exactly what resources were created. This prevents accidentally deleting resources from other deployments in the same namespace.

### Separator Removal in envsubst

The `envsubst` commands use a specific `sed` pattern to clean YAML separators (lines 46, 49, 53):
```bash
sed '1{/^---$/d}; ${/^---$/d}; /^[[:space:]]*$/d' | sed '/^$/N;/^\n$/d'
```

This removes the first and last `---` separators plus blank lines, then the pipeline adds them back explicitly. This ensures consistent YAML document separation in the final rendered manifest.

### Rollout Monitoring Loop

The deployment script includes a monitoring loop (lines 76-144) that:
- Polls rollout status every 30 seconds
- Timeout after 15 minutes
- On failure, fetches detailed logs from Cloud Build using the job run and build IDs
- This nested ID lookup (rollout → job run → build ID) is necessary to get actual deployment logs

## How Application Projects Integrate

Application projects add this to their `.gitlab-ci.yml`:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/cloud-deploy'
    file: '/.gitlab-ci-template.yml'
    ref: 'main'

stages:
  - deploy:review
  - stop:review
  - deploy:develop
  - deploy:staging
  - deploy:production
```

Then create `kubernetes/{review,staging,production}/` directories with their manifest templates using environment variable placeholders like `$KUBE_NAMESPACE`, `$CI_PROJECT_NAME`, etc.

## Kubernetes Manifest Templates

Template manifests use environment variable substitution. Key variables:

**GitLab CI variables**:
- `$CI_PROJECT_NAME`: GitLab project name
- `$CI_COMMIT_REF_SLUG`: Branch name sanitized for DNS
- `$CI_COMMIT_SHA`: Full commit SHA
- `$CI_PIPELINE_ID`: Pipeline ID
- `$PROJECT_ID`: GCP project ID

**Doppler-sourced variables** (via `bash.env`):
- `$KUBE_NAMESPACE`: Target Kubernetes namespace
- `$DOPPLER_ENVIRONMENT`: Environment indicator (dev_, dev, stg, prd)
- `$CLOUD_DEPLOY_GCP_SERVICE_ACCOUNT`: GCP service account key JSON
- `$GKE_CLUSTER_NAME`: Target GKE cluster name
- Any `SECRET_*` prefixed variables: Application secrets

**Standard labels** (present in all manifests):
```yaml
labels:
  environment: $DOPPLER_ENVIRONMENT
  gitlab_project: $CI_PROJECT_NAME
  gitlab_pipeline_id: "$CI_PIPELINE_ID"
  project_owner: web  # Options: web, api, sre, data, rock
  tier: backend       # Options: frontend, backend, database, job
```

## Rollback Process

Rollbacks are performed via GCP Console:
1. Navigate to Cloud Deploy → Delivery pipelines
2. Select pipeline (int-staging or int-production)
3. Find a previous successful release
4. Click three-dot menu → "Promote"
5. Select target cluster and confirm

Note: There is no automated rollback in the GitLab pipeline.
