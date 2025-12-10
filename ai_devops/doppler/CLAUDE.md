# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository provides GitLab CI/CD integration with Doppler for automated secrets management across multiple environments. It consists of two main components:

1. **GitLab CI/CD Template** (`.gitlab-ci.template.yml`) - A reusable pipeline template that other GitLab projects include to automatically fetch secrets from Doppler
2. **Migration Tool** (`migrateToDoppler/`) - A Python utility for migrating secrets from GitLab to Doppler

## Core Architecture

### CI/CD Template Design

The template uses GitLab's `include` mechanism, allowing projects to import it like this:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/doppler'
    file: '.gitlab-ci.template.yml'
    ref: 'main'
```

**Key architectural concepts:**

1. **Hierarchical Secret Resolution**: Projects can reference parent projects via the `DOPPLER_PARENT` secret. The pipeline traverses this hierarchy from bottom-to-top, collecting secrets from each level. Secrets are applied in reverse order (top-down) so child project secrets override parent secrets.

2. **Project Path Mapping**: GitLab project paths are transformed to Doppler project names:
   - `lifechurch/io/digital-product/sre/cicd-tools/doppler` → `gitlab-sre-cicd-tools-doppler`
   - The prefix `lifechurch/io/digital-product/` is stripped, slashes become hyphens, and `gitlab-` is prepended

3. **Branch-to-Config Mapping**:
   - Development branches (`dev`, `develop`, `development-*`, `lifechurch/development`) → `dev` config
   - Staging branches (`integration`, `staging`, `staging-*`, `lifechurch/staging`) → `stg` config
   - Production branches (`main`, `master`, `lifechurch`, `production`, `production-*`) → `prd` config
   - Feature branches → `dev_<branch-slug>` config (created dynamically for review apps)

4. **Feature Branch Handling**: For non-standard branches:
   - A temporary Doppler config is created named `dev_<CI_COMMIT_REF_SLUG>`
   - If branch name exceeds 60 chars (Doppler limit), it's truncated to 47 chars and an 8-char MD5 hash is appended
   - For projects with `./kubernetes` directory, `INGRESS_HOSTNAME` and `SECRET_APP_BASE_URL` are automatically set
   - Feature configs inherit from the `dev` parent config
   - Use `.doppler_scripts.delete_feature_config` to clean up these configs when branches are deleted

5. **Protected Configs**: The delete script explicitly protects `dev`, `stg`, and `prd` configs from accidental deletion

### Secret Job Flow

1. Authenticates with Doppler using `DOPPLER_TOKEN` variable
2. Derives `DOPPLER_PROJECT` from GitLab project path
3. Determines `DOPPLER_CONFIG` based on current branch
4. For feature branches: creates new config, fetches `KUBE_DOMAIN` from parent, sets ingress variables
5. Traverses parent hierarchy by reading `DOPPLER_PARENT` secret at each level
6. Downloads secrets from each project (parent → child order)
7. Exports all secrets to `bash.env` artifact (1-day expiration)
8. Subsequent jobs source `bash.env` via the default `before_script`

### Migration Tool Architecture

**Purpose**: One-time migration of GitLab secrets to Doppler with backup/restore capabilities

**Key features**:
- Supports both GitLab projects and groups
- Backs up to local JSON and optionally to GCS
- Handles secret references (e.g., `${live_clusters.*}`)
- Converts lowercase secret names to UPPERCASE (Doppler convention)
- Preserves masked/protected/environment scope attributes
- Creates Doppler projects automatically if they don't exist

## Development Commands

### Testing the CI/CD Template

Since this is a template included by other projects, there's no local "run" command. To test changes:

1. **Commit changes** to a branch in this repository
2. **Update the `ref` parameter** in a test project's `.gitlab-ci.yml`:
   ```yaml
   include:
     - project: 'lifechurch/io/digital-product/sre/cicd-tools/doppler'
       file: '.gitlab-ci.template.yml'
       ref: 'your-test-branch'  # Change this
   ```
3. **Push to the test project** and observe the pipeline

### Using the Migration Tool

**Setup**:
```bash
cd migrateToDoppler
pip install -r requirements.txt
```

**Backup secrets**:
```bash
python main.py \
  --gitlab-token <token> \
  --doppler-token <token> \
  --gitlab-id <project_id> \
  --gitlab-type project
```

**Backup and delete** (migration):
```bash
python main.py \
  --gitlab-token <token> \
  --doppler-token <token> \
  --gitlab-id <project_id> \
  --gitlab-type project \
  --delete-secrets
```

**Restore secrets**:
```bash
python main.py \
  --gitlab-token <token> \
  --doppler-token <token> \
  --gitlab-id <project_id> \
  --gitlab-type project \
  --restore-secrets
```

**Optional parameters**:
- `--gitlab-url` (default: `https://gitlab.com`)
- `--bucket-name` (default: `rms-sre-storage`)
- `--bucket-path` (default: `secrets-backup`)

## Important Constraints

1. **Doppler Config Name Limit**: 60 characters maximum. The template handles this automatically by truncating and hashing long branch names.

2. **Feature Config Cleanup**: Feature branch configs are NOT automatically deleted. Projects should add a cleanup job to their pipeline:
   ```yaml
   cleanup_doppler_config:
     stage: .post
     when: manual
     script:
       - !reference [.doppler_scripts, delete_feature_config]
   ```

3. **Before Script Override**: If a project defines its own `before_script`, it must manually include the env file loader:
   ```yaml
   defaults:
     before_script:
       - !reference [.doppler_scripts, use_env_file]
   ```

4. **Secret Precedence**: In hierarchical setups, child secrets override parent secrets. This is by design in the traversal logic (line 208-224 of `.gitlab-ci.template.yml`).

5. **Merge Request Handling**: The pipeline detects merge request contexts and uses `CI_MERGE_REQUEST_SOURCE_BRANCH_NAME` instead of `CI_COMMIT_BRANCH` to determine the correct config.

6. **Tag Protection**: The secret job never runs on tag pushes (`rules: - if: $CI_COMMIT_TAG when: never`).

## Project Variables Required

Projects using this template must define:
- `DOPPLER_TOKEN` - Service token for Doppler API authentication

Optional secrets that can be defined in Doppler:
- `DOPPLER_PARENT` - Name of parent Doppler project for hierarchical resolution
- `KUBE_DOMAIN` - Base domain for Kubernetes ingress (required for feature branch deployments with `./kubernetes` directory)

## File Structure

```
doppler/
├── .gitlab-ci.template.yml       # Main CI/CD template (235 lines)
│   ├── .doppler_scripts          # Reusable script references
│   │   ├── use_env_file          # Sources bash.env in jobs
│   │   └── delete_feature_config # Cleans up feature branch configs
│   ├── default                   # Sets before_script for all jobs
│   └── secret                    # Main job that fetches secrets
├── migrateToDoppler/
│   ├── main.py                   # Python migration script (294 lines)
│   ├── requirements.txt          # python-gitlab, google-cloud-storage, requests
│   └── README.md                 # Migration tool documentation
└── README.md                     # Project overview and usage
```

## Common Pitfalls

1. **Protected Config Deletion**: The delete script protects core configs, but always verify before running deletion commands manually.

2. **Long Branch Names**: Branch names longer than 56 chars (accounting for `dev_` prefix) will be truncated. The original branch name is still printed in logs for reference.

3. **Parent Project Loops**: Don't create circular `DOPPLER_PARENT` references - the traversal doesn't detect loops and will hang.

4. **Case Sensitivity**: The migration tool converts secrets to UPPERCASE. GitLab projects expecting lowercase variable names will need code updates.

5. **Secret References**: The migration tool intelligently handles references like `${live_clusters.dev}`, but verify these work correctly after migration.

## Recent Changes

Based on recent commit history:
- Feature branch name truncation with consistent MD5 hashing (commit `78564f1`)
- Portable shell syntax improvements for cross-platform compatibility (commit `2d422b7`)
- Feature config deletion safety fixes (commits `e72d000`, `b7065b5`)
