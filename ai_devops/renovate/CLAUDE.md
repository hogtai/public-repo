# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **reusable GitLab CI/CD template** for integrating Renovate Bot into GitLab projects. It is designed to be included by other GitLab projects, not run standalone. The template handles dependency updates across multiple package managers with integration to Doppler for secure token management.

## Repository Architecture

**Template-based Design**: This repository provides infrastructure-as-code that other projects consume via GitLab's CI `include` directive.

**Key Files**:
- `.gitlab-ci-template.yml` - The reusable CI template that consuming projects include
- `README.md` - User-facing documentation for project maintainers who want to use this template

**Dependencies**:
- Depends on `lifechurch/io/digital-product/sre/cicd-tools/doppler` CI template for secret management
- Uses official `renovate/renovate:latest` Docker image
- Requires `RENOVATE_BOT` token from Doppler secrets

## How It Works

1. **Consumer projects include** this template in their `.gitlab-ci.yml`
2. **Scheduled pipeline trigger** activates the renovate job (`CI_PIPELINE_SOURCE == "schedule"`)
3. **Secret stage** (from Doppler template) runs first to fetch `RENOVATE_BOT` token into `bash.env`
4. **Renovate stage** sources `bash.env` and runs renovate against the consumer's GitLab project
5. **Renovate creates**:
   - A GitLab Issue listing all available upgrades
   - Separate MRs for each selected upgrade (after re-running the scheduled pipeline)

## Key Configuration Points

**GitLab Project Path**: Template is hosted at `lifechurch/io/digital-product/sre/cicd-tools/renovate`

**Stages**:
- `secret` - Inherited from Doppler template
- `renovate` - Main Renovate execution stage

**Execution Rules**: Only runs on scheduled pipelines (`CI_PIPELINE_SOURCE == "schedule"`), marked as `allow_failure: true`

**Runner Assignment**: Consumer projects must specify runner tags via `default.tags` or by overriding the `renovate` job

## Testing Changes

Since this is a template consumed by other projects:

1. Make changes to `.gitlab-ci-template.yml`
2. Test by creating a test consumer project that includes this template
3. Set up a scheduled pipeline in the test project
4. Verify the pipeline runs successfully and Renovate behaves as expected
5. Check that secrets are properly sourced from `bash.env`

## Modifying the Template

**Image Version**: Default is `renovate/renovate:latest` - pin to specific version if stability is needed

**Authentication Flow**: The template assumes `bash.env` is created by the Doppler template's `secret` stage and contains `RENOVATE_BOT`

**Pipeline Dependency**: The `renovate` job has `dependencies: [secret]` to ensure secrets are available

**Platform Configuration**: Hardcoded to `--platform gitlab` since this is GitLab-specific

## Common Scenarios

**Adding environment variables**: Consumer projects can override the `renovate` job and add variables

**Changing schedule logic**: Modify the `rules` section in `.gitlab-ci-template.yml`

**Updating documentation**: Edit `README.md` with usage examples and troubleshooting

**Debugging**: Consumers can add `LOG_LEVEL: debug` as a Renovate environment variable
