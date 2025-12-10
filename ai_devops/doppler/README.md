# Doppler GitLab CI/CD Integration

## Overview
`Doppler` is a reusable GitLab CI/CD configuration designed to be included in other pipelines via GitLab's `include` function. It automates the retrieval and management of secrets from Doppler across different environments based on the Git branch in use.

## Features
- **Automatic Environment Selection**: Determines the appropriate Doppler configuration (`dev`, `stg`, or `prd`) based on the GitLab branch.
- **Hierarchical Secret Management**: Resolves and retrieves secrets from a hierarchical project structure in Doppler.
- **GitLab Include Compatibility**: Designed for easy inclusion in other GitLab CI/CD pipelines.

## Usage
To include this configuration in your GitLab CI/CD pipeline, reference it as follows:

```yaml
include:
  - project: 'lifechurch/io/digital-product/sre/cicd-tools/doppler'
    file: '.gitlab-ci.template.yml'
    ref: 'main'
```

## Configuration
### Variables
The pipeline dynamically determines the following variables:

- **`DOPPLER_PROJECT`**: Extracted from the GitLab project path.
- **`DOPPLER_CONFIG`**: Derived from the branch name (`dev`, `stg`, or `prd`).

### Project Mappings
`lifechurch/io/digital-product/sre/cicd-tools/doppler` will be re-written to `gitlab_sre_cicd-tools_doppler`.

You will see `gitlab_sre_cicd-tools_doppler` in Doppler Projects for Digital Product

### Supported Branch Mappings
| Branch Name | Doppler Config |
|------------|---------------|
| `dev`, `develop`, `development` | `dev` |
| `integration`, `staging` | `stg` |
| `main`, `master`, `production` | `prd` |
| Others | Defaults to `dev` |

## Job Definitions

By default, the include will attempt to set a before_script on all jobs. This will attempt to import secrets from doppler on every job. However if the GitLab Pipeline already has a `before_script` defined you will need to include the reference manually. An example is below:

```yaml
defaults:
  before_script:
    - !reference [.doppler_scripts, use_env_file]
```

## Secrets Retrieval Process
1. **Determine Project and Config**: Extracts the project from GitLab path and maps the branch to a corresponding Doppler config.
2. **Check Parent Projects**: Iterates through the parent hierarchy using the `DOPPLER_PARENT_CONFIG` variable.
3. **Fetch and Store Secrets**: Retrieves secrets for each project in the hierarchy and stores them in `bash.env`.
4. **Load Secrets in Pipelines**: The `bash.env` file is sourced in subsequent jobs.

## Dependencies
- `Secret` Stage in the Destination Pipeline to run this process.
- Doppler CLI (`dopplerhq/cli:3` Docker image)
- `jq` (installed in the pipeline to process JSON secrets)

## Notes
- Ensure that projects using this include have appropriate Doppler permissions.
- Secrets are stored in `bash.env` and should be handled securely.