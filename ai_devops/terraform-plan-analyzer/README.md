# Terraform Plan Analyzer

This project provides a tool for analyzing Terraform plan files. It includes a Python script for parsing and analyzing the plan, and a GitLab CI configuration for automating the analysis in a CI/CD pipeline.

## Overview

The `terraform_plan_analyzer.py` script is the core component of this project. It takes a Terraform plan file as input and performs analysis to identify potential issues, resource changes, and other relevant information.

The `terraform-plan-analysis.gitlab-ci.yml` file provides a GitLab CI configuration that automates the Terraform plan analysis process. It defines a pipeline that runs the `terraform_plan_analyzer.py` script on each commit or merge request, providing feedback on the changes introduced by the Terraform plan.

## Usage

To use the `terraform_plan_analyzer.py` script, you need to have Python installed on your system. You can then run the script from the command line, providing the path to the Terraform plan file as an argument:

```
python terraform_plan_analyzer.py <plan_file>
```

The script will output the analysis results to the console.

## GitLab CI Integration

To integrate the Terraform plan analysis into your GitLab CI/CD pipeline, you need to include the `terraform-plan-analysis.gitlab-ci.yml` file in your project's `.gitlab-ci.yml` file. This will define a pipeline that runs the `terraform_plan_analyzer.py` script on each commit or merge request.

## License

This project is licensed under the [MIT License](LICENSE).
