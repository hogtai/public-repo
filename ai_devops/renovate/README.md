# Renovate Bot GitLab CI Template

A reusable GitLab CI template for running [Renovate Bot](https://docs.renovatebot.com/) to automatically manage dependency updates across our gitlab projects for project maintainance patching.

## Overview

This template provides a standardized way to integrate Renovate Bot into any GitLab project. It handles:
- Automatic dependency updates for supported package managers
- Scheduled pipeline execution
- Integration with Doppler for secure token management
- Flexible runner configuration

## Prerequisites

1. **Renovate Configuration**: A `renovate.json` file in your project root to determine your particular configuration for how renovate manages dependencies in your project (doc: https://docs.renovatebot.com/configuration-options/)
2. **Doppler Secrets**: `RENOVATE_BOT` token configured in Doppler, needed for our gitlab runners to pull release update notes from Github via the SRE SVC Account (svc_sre_digital_product@life.chruch).

Credentials are saved in the Digital Product SRE 1Pass vault.

3. **GitLab Scheduled Pipeline**: Configured in your project's CI/CD settings - You need to set-up a scheudled pipeline job in your project to tell renovate when to automatically run. 

Renovate only runs on a schedule that you can set up in your project via a Scheduled Pipeline Job. Once set up, you can also manually trigger the job at any time to engage Renovate to scan for dependency upgrades for your project. 

## Usage

### Basic Setup

Add the following to your project's `.gitlab-ci.yml`:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/renovate'
    file: '/.gitlab-ci-template.yml'
    ref: 'main'

default:
  tags:
    - your-runner-tag  # e.g., int-staging, production, etc.
```

### Complete Example

Here's a complete example from a Terraform project:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/renovate'
    file: '/.gitlab-ci-template.yml'
    ref: 'main'

default:
  tags:
    - int-staging # which gitlab runners should take this job

stages:
  - renovate # needs to be added to your existing project stages

# Your other jobs here...
```

## Renovate Configuration

Create a `renovate.json` in your project root. Here's a basic example for a Terraform project:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": [
    "config:recommended"
  ],
  "enabledManagers": [
    "terraform",
    "terraform-version"
  ],
  "labels": [
    "renovate",
    "dependencies"
  ],
  "schedule": [
    "on the 28th day of the month"
  ],
  "timezone": "America/Chicago",
  "separateMajorMinor": true,
  "rangeStrategy": "pin"
}
```

For more configuration options, see the [Renovate documentation](https://docs.renovatebot.com/configuration-options/).

## Setting Up Scheduled Pipelines

1. Navigate to your project in GitLab
2. Go to **CI/CD > Schedules**
3. Click **New schedule**
4. Configure your schedule:
   - **Description**: e.g., "Renovate Bot - Monthly Check"
   - **Interval Pattern**: Choose your desired frequency
   - **Target Branch**: `main` (or your default branch)
   - **Variables**: None required
5. Click **Save pipeline schedule**

## How It Works

1. **Scheduled Trigger**: The pipeline runs only when triggered by a schedule (`CI_PIPELINE_SOURCE == "schedule"`)
2. **Secret Management**: The `secret` stage (from Doppler template) runs first to fetch the `RENOVATE_BOT`
3. **Renovate Execution**: The `renovate` stage:
   - Uses the official `renovate/renovate:latest` Docker image
   - Sources environment variables from `bash.env` (provided by Doppler for the target project)
   - Executes Renovate against your GitLab project
   - Creates a gitlab 'Issue' with an overview of all the available upgrades.
   - Visit the 'Issues' page in your gitlab project to see any available upgrades, you can check each upgrade of which you want a new MR for, run a fresh 'scheduled pipeline' for the renovate project, and then renovate will open seperate MRs with release notes for the upgrades as MRs for you to review in your project.

## Customization

### Changing Renovate Image Version

By default, this template uses `renovate/renovate:latest`. To pin to a specific version:

```yaml
renovate:
  image:
    name: renovate/renovate:37.0.0
    entrypoint: [""]
```

### Adding Additional Environment Variables

```yaml
renovate:
  variables:
    LOG_LEVEL: debug
    RENOVATE_AUTODISCOVER: false
```

### Modifying Execution Rules

By default, Renovate only runs on scheduled pipelines. To add manual execution:

```yaml
renovate:
  rules:
    - if: '$CI_PIPELINE_SOURCE == "schedule"'
      when: always
    - when: manual
      allow_failure: true
```

## Troubleshooting

### Pipeline Not Running

- Verify scheduled pipeline is configured and enabled
- Check that the schedule target branch is correct
- Ensure runner tags match available runners

### Authentication Errors

- Verify `RENOVATE_BOT` token is configured in Doppler
- Check token has appropriate permissions (API access, repository write)
- Ensure Doppler template is included and `secret` stage runs successfully

### No Updates Created

- Check `renovate.json` configuration
- Review Renovate logs in pipeline output
- Verify enabled managers match your project's dependency types

## Related Documentation

- [Renovate Bot Documentation](https://docs.renovatebot.com/)
- [GitLab CI/CD Pipelines](https://docs.gitlab.com/ee/ci/pipelines/)
- [GitLab Pipeline Schedules](https://docs.gitlab.com/ee/ci/pipelines/schedules.html)

## Support

For issues or questions, please contact the SRE team or open an issue in this repository.
