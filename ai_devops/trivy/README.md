# Trivy Security Scanning GitLab CI Template

A reusable GitLab CI template for running [Trivy](https://trivy.dev/) security scans on container images to detect vulnerabilities and secrets.

## Overview

This template provides a standardized way to integrate Trivy security scanning into any GitLab project with containerized applications. It handles:
- Container vulnerability scanning (CVE detection)
- Secret detection in container images
- Automated scanning on main/integration branches
- GitLab security report integration
- Efficient caching of vulnerability databases

## Prerequisites

1. **Container Images**: Your project must build and push container images to Google Container Registry (GCR)
2. **GitLab Variables**: The following variables should be configured:
   - `CI_REGISTRY_USER` - Registry authentication username (usually auto-configured by GitLab)
   - `CI_REGISTRY_PASSWORD` - Registry authentication password (usually auto-configured by GitLab)
   - `PROJECT_ID` - Your GCP project ID where images are stored
3. **GitLab Runners**: Runners with appropriate tags (e.g., `int-prod`) and Docker support

## Usage

### Basic Setup

Add the following to your project's `.gitlab-ci.yml`:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/trivy'
    file: '/.gitlab-ci-template.yml'
    ref: 'main'

default:
  tags:
    - int-prod  # or your preferred runner tag

stages:
  - build      # your existing stages
  - test
  - secure     # add this stage for security scanning
```

### Complete Example

Here's a complete example from a containerized Node.js application:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/trivy'
    file: '/.gitlab-ci-template.yml'
    ref: 'main'

default:
  tags:
    - int-prod

stages:
  - build
  - secure

variables:
  PROJECT_ID: 'my-gcp-project-id'

build:
  stage: build
  image: gcr.io/kaniko-project/executor:latest
  script:
    - # build and push your container image
    - echo "Image built and pushed to gcr.io/${PROJECT_ID}/${CI_PROJECT_NAME}:${CI_COMMIT_SHA}-${CI_PIPELINE_ID}"

# Trivy jobs (container_scanning and secret_detection) are automatically included
```

## Jobs Provided

### container_scanning

Scans container images for known vulnerabilities (CVEs).

**Features**:
- Scans for CRITICAL and HIGH severity vulnerabilities
- Ignores unfixed vulnerabilities (those without available patches)
- Generates human-readable table output
- Creates JSON report for GitLab integration
- Only runs on `main` or `integration` branches

**Artifacts**:
- `trivy-report-vulns.json` - Detailed vulnerability report
- Integrated with GitLab's container scanning report format

### secret_detection

Scans container images for exposed secrets (API keys, passwords, tokens).

**Features**:
- Detects CRITICAL and HIGH severity secrets
- Fails pipeline if secrets are found (exit-code 1)
- Generates JSON report for GitLab integration
- Only runs on `main` or `integration` branches

**Artifacts**:
- `trivy-report-secrets.json` - Detailed secrets detection report
- Integrated with GitLab's secret detection report format

## Configuration

### Customizing Image Name

By default, images are scanned using the pattern:
```
gcr.io/${PROJECT_ID}/${CI_PROJECT_NAME}:${CI_COMMIT_SHA}-${CI_PIPELINE_ID}
```

To use a different image naming convention:

```yaml
variables:
  FULL_IMAGE_NAME: 'gcr.io/my-project/custom-name:${CI_COMMIT_TAG}'
```

### Changing Branch Rules

By default, scans only run on `main` and `integration` branches. To scan different branches:

```yaml
container_scanning:
  rules:
    - if: '$CI_COMMIT_BRANCH == "main" || $CI_COMMIT_BRANCH == "develop"'
      when: on_success
      allow_failure: true
```

### Adjusting Severity Levels

To scan for different severity levels:

```yaml
container_scanning:
  script:
    - time trivy image --format table --report summary --severity CRITICAL,HIGH,MEDIUM  "$FULL_IMAGE_NAME" --quiet --scanners vuln  --ignore-unfixed
    - time trivy image --exit-code 1 --severity CRITICAL,HIGH,MEDIUM --format json --list-all-pkgs --output trivy-report-vulns.json "$FULL_IMAGE_NAME" --scanners vuln  --ignore-unfixed
```

### Enabling on Merge Requests

By default, Trivy scans are disabled on merge requests. To enable:

```yaml
container_scanning:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: on_success
    - if: '$CI_COMMIT_BRANCH == "main" || $CI_COMMIT_BRANCH == "integration"'
      when: on_success
      allow_failure: true
```

### Allow Failures

To make security scans optional (not block pipeline):

```yaml
variables:
  SECURE_ALLOW_FAILURE: 'true'
```

Or override specific jobs:

```yaml
container_scanning:
  allow_failure: true
```

## How It Works

1. **Stage**: Security scans run in the `secure` stage (typically after build/test)
2. **Image Pull**: Trivy authenticates to GCR using `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD`
3. **Database Update**: Trivy downloads the latest vulnerability database
4. **Scanning**:
   - `container_scanning` checks for CVEs in packages
   - `secret_detection` checks for exposed secrets
5. **Reporting**:
   - Results are displayed in the pipeline logs
   - JSON reports are saved as artifacts
   - Reports integrate with GitLab Security Dashboard

## Viewing Results

### In GitLab UI

1. Navigate to your project's pipeline
2. Click on the security job (e.g., `container_scanning`)
3. View the security report in the **Security** tab
4. Or navigate to **Security & Compliance > Vulnerability Report**

### In Pipeline Logs

Security scans output a table format showing:
- Total vulnerabilities found
- Breakdown by severity (CRITICAL, HIGH, etc.)
- Affected packages

### Downloading Reports

JSON reports are available as pipeline artifacts:
- Download from the pipeline's artifacts section
- Or via GitLab API for integration with other tools

## Troubleshooting

### Authentication Errors

**Symptom**: `UNAUTHORIZED: authentication required`

**Solution**:
- Verify `PROJECT_ID` is set correctly
- Ensure GitLab has access to pull from GCR
- Check that `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD` are configured

### Image Not Found

**Symptom**: `unable to get image: GET https://gcr.io/...`

**Solution**:
- Verify the image was built and pushed in a previous stage
- Check that `FULL_IMAGE_NAME` matches your actual image name/tag
- Ensure the build stage runs before the secure stage

### Database Download Failures

**Symptom**: `failed to download vulnerability DB`

**Solution**:
- Check runner has internet access
- Verify no firewall blocking access to Trivy database servers
- Try manually clearing the cache and re-running

### Pipeline Fails on Vulnerabilities

**Symptom**: Pipeline fails with vulnerabilities found

**Solution**:
- Review the vulnerability report
- Update base images or dependencies to patched versions
- If accepting risk temporarily, set `allow_failure: true`
- Use `SECURE_ALLOW_FAILURE: 'true'` variable to make all security jobs non-blocking

## Performance Optimization

### Caching

Trivy caches vulnerability databases in `.trivycache/` to speed up subsequent scans. The cache is preserved between pipeline runs.

### Parallel Execution

Both `container_scanning` and `secret_detection` can run in parallel since they're independent jobs.

## Related Documentation

- [Trivy Official Documentation](https://trivy.dev/)
- [Trivy Container Scanning](https://aquasecurity.github.io/trivy/latest/docs/target/container_image/)
- [GitLab Container Scanning](https://docs.gitlab.com/ee/user/application_security/container_scanning/)
- [GitLab Secret Detection](https://docs.gitlab.com/ee/user/application_security/secret_detection/)

## Support

For issues or questions, please contact the SRE team or open an issue in this repository.

## Security Best Practices

1. **Always scan on main/integration**: These are your deployed branches
2. **Don't ignore CRITICAL vulnerabilities**: Address them promptly
3. **Update base images regularly**: Use recent, patched base images
4. **Monitor the Security Dashboard**: Regularly review vulnerability trends
5. **Fail fast on secrets**: Never deploy containers with exposed secrets
