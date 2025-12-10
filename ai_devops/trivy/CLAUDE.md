# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **reusable GitLab CI/CD template** for integrating Trivy security scanning into GitLab projects. It is designed to be included by other GitLab projects, not run standalone. The template provides container vulnerability scanning and secret detection for Docker images stored in Google Container Registry (GCR).

## Repository Architecture

**Template-based Design**: This repository provides infrastructure-as-code that other projects consume via GitLab's CI `include` directive.

**Key Files**:
- `.gitlab-ci-template.yml` - The reusable CI template that consuming projects include
- `README.md` - User-facing documentation for project maintainers who want to use this template

**Dependencies**:
- Uses official `docker.io/aquasec/trivy:latest` Docker image
- Requires access to Google Container Registry (GCR) for pulling images to scan
- Depends on GitLab CI variables: `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD`, `PROJECT_ID`

## How It Works

1. **Consumer projects include** this template in their `.gitlab-ci.yml`
2. **After container build stage**, the `secure` stage runs Trivy scans
3. **Two parallel jobs execute**:
   - `container_scanning` - Scans for CVEs in container packages
   - `secret_detection` - Scans for exposed secrets (API keys, tokens, etc.)
4. **Results are reported**:
   - Console output shows vulnerability summary
   - JSON artifacts are generated
   - GitLab Security Dashboard integration via reports

## Key Configuration Points

**GitLab Project Path**: Template is hosted at `lifechurch/io/digital-product/sre/cicd-tools/trivy`

**Stages**:
- `secure` - Main security scanning stage

**Jobs**:
- `.trivy` - Base job definition with common configuration
- `container_scanning` - Vulnerability scanning job (extends `.trivy`)
- `secret_detection` - Secret detection job (extends `.trivy`)

**Execution Rules**:
- Never runs on merge request events (`if: $CI_PIPELINE_SOURCE == "merge_request_event" when: never`)
- Only runs on `main` or `integration` branches
- Marked as `allow_failure: true` by default (unless `SECURE_ALLOW_FAILURE` is set)

**Image Naming Convention**:
- Default: `gcr.io/${PROJECT_ID}/${CI_PROJECT_NAME}:${CI_COMMIT_SHA}-${CI_PIPELINE_ID}`
- Consumer projects can override via `FULL_IMAGE_NAME` variable

**Runner Assignment**: Consumer projects must specify runner tags via `default.tags` or by overriding specific jobs

## Trivy Configuration

**Database Updates**: Each job run updates the Trivy vulnerability database (`trivy image --download-db-only`)

**Cache Strategy**:
- `.trivycache/` directory is cached between runs
- Cache is cleared at start of each scan (`trivy image --clear-cache`)

**Scan Configuration**:
- Severity levels: CRITICAL and HIGH (customizable)
- Container scanning: Ignores unfixed vulnerabilities
- Secret detection: Fails pipeline on detection (`--exit-code 1`)

**Authentication**:
- Uses `TRIVY_USERNAME` and `TRIVY_PASSWORD` (mapped from GitLab CI variables)
- Authenticates to `TRIVY_AUTH_URL` (CI registry)

## Testing Changes

Since this is a template consumed by other projects:

1. Make changes to `.gitlab-ci-template.yml`
2. Test by creating a test consumer project that includes this template
3. Build a container image in the test project
4. Run the pipeline on `main` or `integration` branch
5. Verify both `container_scanning` and `secret_detection` jobs execute
6. Check artifacts are generated correctly
7. Validate GitLab Security Dashboard shows results

## Modifying the Template

**Image Version**: Default is `aquasec/trivy:latest` - pin to specific version if stability is needed (e.g., `aquasec/trivy:0.48.0`)

**Severity Levels**: Modify `--severity CRITICAL,HIGH` to include MEDIUM or LOW if needed

**Scan Options**:
- `--ignore-unfixed`: Only shows vulnerabilities with available fixes (container scanning)
- `--scanners vuln`: Focuses on vulnerability scanning (vs license, config, etc.)
- `--scanners secret`: Focuses on secret detection
- `--quiet`: Reduces output verbosity
- `--report summary`: Shows summarized output format

**Branch Rules**: Adjust the `rules` section to change which branches trigger scans

**Failure Behavior**:
- `container_scanning` has `allow_failure: true` (warnings only)
- `secret_detection` uses `--exit-code 1` (fails on detection) but also has `allow_failure: true`

## Common Scenarios

**Adding new scan types**: Extend `.trivy` to create additional jobs (e.g., license scanning, config scanning)

**Customizing image name pattern**: Consumer projects set `FULL_IMAGE_NAME` variable

**Enabling on MRs**: Override the base rule that blocks merge request execution

**Adjusting failure behavior**: Consumer can set `SECURE_ALLOW_FAILURE: 'true'` or override job-level `allow_failure`

**Multiple images**: Consumer projects can create additional jobs that extend `.trivy` with different `FULL_IMAGE_NAME` values

## Security Considerations

**GIT_STRATEGY: none**: This template doesn't clone repository code (only scans pre-built images from registry)

**Secret Detection Exit Code**: Secret detection fails the pipeline (`--exit-code 1`) to prevent deploying containers with exposed secrets

**Vulnerability Scanning**: Container scanning shows warnings but doesn't fail by default, allowing teams to address vulnerabilities on their timeline

**Cache Isolation**: Each project has its own `.trivycache/` directory (not shared between projects)

## Performance Characteristics

**Database Download**: First run takes longer (~30s) to download vulnerability database

**Subsequent Runs**: Much faster due to caching (unless database has significant updates)

**Parallel Execution**: Both jobs run simultaneously for faster results

**Image Size Impact**: Larger container images take longer to scan

## Integration Points

**GitLab Security Dashboard**: Reports are formatted for GitLab's built-in security features

**Artifacts**: JSON reports can be consumed by external tools or custom integrations

**Pipeline Status**: Jobs can fail pipeline based on findings (if `allow_failure: false`)

**Notification**: Teams can configure GitLab notifications for security findings
