# DevOps Toolkit & Infrastructure Portfolio

A comprehensive collection of DevOps tools, infrastructure-as-code templates, and automation scripts for multi-cloud environments. This repository serves as both a production-ready toolkit and a portfolio demonstrating modern DevOps practices.

## 📋 Table of Contents

- [Overview](#overview)
- [AI DevOps Suite](#ai-devops-suite)
- [Infrastructure as Code](#infrastructure-as-code)
- [Automation Scripts](#automation-scripts)
- [CI/CD Workflows](#cicd-workflows)
- [Getting Started](#getting-started)
- [License](#license)

## 🎯 Overview

This repository contains production-ready tools and templates for:
- **Multi-cloud infrastructure** (AWS, GCP)
- **GitLab CI/CD pipeline templates**
- **AI-powered DevOps automation**
- **Container orchestration** (Docker, Kubernetes)
- **Infrastructure provisioning** (Terraform, CloudFormation)
- **Security scanning and secrets management**

## 🤖 AI DevOps Suite

Reusable GitLab CI/CD templates located in [`/ai_devops/`](./ai_devops/):

### Cloud Deploy
Modern continuous deployment for GCP Cloud Deploy integration with Kubernetes.
- Automated review app deployment for feature branches
- Multi-environment support (review/staging/production)
- Doppler secrets management integration
- Automatic cleanup of stale review apps
- **Template**: `ai_devops/cloud-deploy/.gitlab-ci-template.yml`

### Terraform Plan Analyzer
AI-powered Terraform infrastructure change analysis using Google Gemini.
- Automatic sensitive data redaction (16+ patterns)
- Context-aware AI analysis of infrastructure changes
- GitLab MR comment integration
- Support for 10+ Terraform providers
- **Script**: `ai_devops/terraform-plan-analyzer/terraform_plan_analyzer.py`

### Code Analyzer (Gemini Code Reviewer)
Automated code review using Google Gemini Pro via Vertex AI.
- Line-by-line code review with severity ratings
- GitLab webhook integration
- Cloud Tasks for asynchronous processing
- Customizable review prompts per project
- **Deployment**: Google Cloud Run

### Doppler Integration
Centralized secrets management from Doppler to GitLab CI/CD.
- Hierarchical secret resolution
- Branch-to-environment mapping
- Automatic feature branch config creation
- Migration tool for GitLab → Doppler secrets
- **Template**: `ai_devops/doppler/.gitlab-ci.template.yml`

### Renovate Bot
Automated dependency management and update tracking.
- Multi-package-manager support (Terraform, npm, Python, Docker)
- Automated MR creation with release notes
- Issue tracking for available upgrades
- **Template**: `ai_devops/renovate/.gitlab-ci-template.yml`

### Trivy Security Scanning
Container vulnerability and secret detection.
- CVE scanning for CRITICAL/HIGH vulnerabilities
- Secret detection in container images
- GitLab Security Dashboard integration
- **Template**: `ai_devops/trivy/.gitlab-ci-template.yml`

## 🏗️ Infrastructure as Code

### Terraform ([`/Terraform/`](./Terraform/))
- **GCP Infrastructure**: GKE clusters, Cloud Storage, networking
- **AWS Infrastructure**: EC2, VPC, RDS, security groups
- **Reusable Modules**: 11+ modules for common infrastructure patterns
- **Reference Architectures**: Three-tier applications, complete infrastructure examples
- **GitLab Agent**: Kubernetes agent deployment for GKE

### CloudFormation ([`/cloudformation/`](./cloudformation/))
- VPC and networking configurations
- DynamoDB, EC2, and IAM setups
- Instance scheduling automation
- Multi-version template evolution

### Kubernetes ([`/kubernetes/`](./kubernetes/))
- Multi-tier application stacks (Apache, PostgreSQL, Redis)
- Production-ready manifests

### Docker ([`/docker/`](./docker/))
- Development and production Dockerfiles
- Docker Compose configurations for multi-environment setups
- Docker Swarm stack definitions

## 🔧 Automation Scripts

### Python Scripts ([`/python-scripts/`](./python-scripts/))

**AWS Automation:**
- EC2 management (backup, idle detection, cleanup)
- EBS volume management
- AMI lifecycle management
- VPC flow log analysis
- SNS/SQS/DynamoDB integration

**GitLab Monitoring:**
- `pipeline-performance-multiple-projects-test.py`: Multi-project performance analysis
- `gitlab_pipeline_performance_with_retry.py`: Flakiness analysis and retry tracking

**Infrastructure Deployment:**
- Three-tier high-availability deployment orchestration
- VPC creation automation

### Bash Scripts ([`/bash-scripts/`](./bash-scripts/))
- Server provisioning and setup
- Database backup automation (MySQL)
- User management
- File organization and batch operations
- Log cleanup and rotation
- Git automation

### Lambda Functions ([`/lambda-functions/`](./lambda-functions/))
Serverless functions for AWS automation:
- EC2 cost optimization
- Storage lifecycle management
- Event-driven data pipelines
- Network monitoring

### AWS CLI ([`/aws-cli/`](./aws-cli/))
Ready-to-use AWS CLI commands for:
- DynamoDB table operations
- EC2 instance management
- IAM policy configuration

## 🔄 CI/CD Workflows

### GitHub Actions ([`.github/workflows/`](./.github/workflows/))

**Pipeline Performance Audit** (`pipeline-audit.yml`):
- **Schedule**: First Friday of each month at 6:00 UTC
- **Purpose**: GitLab pipeline performance monitoring and flakiness analysis
- **Features**:
  - Multi-project performance testing
  - Retry logic analysis
  - Email notifications (success/failure)
  - Artifact collection and archiving
  - Timezone-aware execution (America/Chicago)

## 🚀 Getting Started

### Using GitLab CI/CD Templates

Include templates in your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/hogtai/public-repo/main/ai_devops/cloud-deploy/.gitlab-ci-template.yml'
  - remote: 'https://raw.githubusercontent.com/hogtai/public-repo/main/ai_devops/trivy/.gitlab-ci-template.yml'
```

### Using Terraform Modules

Reference modules in your Terraform configuration:

```hcl
module "vpc" {
  source = "git::https://github.com/hogtai/public-repo.git//Terraform/modules/vpc"
  # ... configuration
}
```

### Running Python Scripts

```bash
# Example: GitLab pipeline performance analysis
export GITLAB_PROJECT_IDS="123456,789012"
export GITLAB_ACCESS_TOKEN="your-token"
python python-scripts/gitlab/pipeline-performance-multiple-projects-test.py
```

## 🔐 Security

This repository includes multiple security features:
- Automatic secret redaction in Terraform plans
- Container vulnerability scanning (Trivy)
- Secret detection in CI/CD pipelines
- Centralized secrets management (Doppler)
- Token-based authentication for webhooks

## 🛠️ Technology Stack

**Cloud Platforms**: AWS, Google Cloud Platform
**Infrastructure**: Terraform, CloudFormation, Kubernetes, Docker
**CI/CD**: GitLab CI/CD, GitHub Actions
**Languages**: Python, Bash, HCL, YAML
**AI/ML**: Google Gemini Pro, Vertex AI
**Security**: Trivy, Doppler
**Automation**: Renovate Bot, Cloud Deploy

## 📊 Repository Statistics

- **72+** production-ready scripts and templates
- **6** AI-powered DevOps tools
- **Multi-cloud** support (AWS + GCP)
- **11+** reusable Terraform modules
- **Automated** security scanning and dependency management

## 📝 License

This repository is licensed under the [MIT License](https://opensource.org/licenses/MIT). Feel free to use, modify, and distribute the contents as needed.

---

<p align="center">Made with ❤️ by Tait Hoglund</p>
<p align="center">Cloud Engineer | DevOps Specialist | Infrastructure Automation</p>
