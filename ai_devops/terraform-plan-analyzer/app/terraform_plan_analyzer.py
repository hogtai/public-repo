#!/usr/bin/env python3

import json
import os
import sys
import argparse
import logging
import re
import glob
from typing import Dict, List, Any, Set
import google.generativeai as genai
import copy
import gitlab

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Common provider documentation base URLs
# Common provider documentation base URLs
PROVIDER_DOC_URLS = {
    "registry.terraform.io/hashicorp/aws": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/",
    "registry.terraform.io/hashicorp/google": "https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/",
    "registry.terraform.io/hashicorp/azurerm": "https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/",
    "registry.terraform.io/hashicorp/fastly": "https://registry.terraform.io/providers/fastly/fastly/latest/docs/resources/",
    "registry.terraform.io/newrelic/newrelic": "https://registry.terraform.io/providers/newrelic/newrelic/latest/docs/resources/",
    "registry.terraform.io/digitalocean/digitalocean": "https://registry.terraform.io/providers/digitalocean/digitalocean/latest/docs/resources/",
    "registry.terraform.io/cloudflare/cloudflare": "https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs/resources/",
    "registry.terraform.io/datadog/datadog": "https://registry.terraform.io/providers/datadog/datadog/latest/docs/resources/",
    "registry.terraform.io/hashicorp/kubernetes": "https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs/resources/",
    "registry.terraform.io/hashicorp/helm": "https://registry.terraform.io/providers/hashicorp/helm/latest/docs/resources/",
}

# Common sensitive field names - these will be automatically redacted
SENSITIVE_FIELD_PATTERNS = [
    "password",
    "secret",
    "token",
    "key",
    "cert",
    "private",
    "credential",
    "auth",
    "api_key",
    "api_secret",
    "access_key",
    "session_token",
    "ssh_key",
    "passphrase",
    "license",
    "signature"
]

# Maximum context window size (in tokens) for Gemini
# These are conservative estimates - actual limits may vary by model
GEMINI_CONTEXT_LIMITS = {
    "gemini-1.5-flash": 1000000,
    "gemini-1.5-pro": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-2.0-pro": 1000000,
    "gemini-2.0-flash-001": 1000000,
    "gemini-pro": 30000,  # older model
    "gemini-ultra": 32000  # older model
}

# Approximate tokens per character for estimation
TOKENS_PER_CHAR = 0.25

def get_resource_doc_url(provider_name: str, resource_type: str) -> str:
    """
    Construct the documentation URL for a given resource type and provider.
    
    Args:
        provider_name: The name of the Terraform provider
        resource_type: The type of the Terraform resource
        
    Returns:
        The documentation URL, or an empty string if not found
    """
    base_url = PROVIDER_DOC_URLS.get(provider_name)
    if not base_url:
        logger.warning(f"No documentation base URL found for provider: {provider_name}")
        return ""
    
    # Construct the resource-specific URL
    resource_name = resource_type.replace('_', '-')  # Format resource name to match URL
    doc_url = f"{base_url}{resource_name}"
    
    return doc_url

def format_value(value: Any) -> str:
    """Format a value for display in Terraform-like output"""
    if isinstance(value, str):
        # Escape any quotation marks in the string
        escaped_value = value.replace('"', '\\"')
        return f'"{escaped_value}"'
    elif value is None:
        return "null"
    elif isinstance(value, bool):
        return str(value).lower()
    elif isinstance(value, list):
        # Format list contents
        if not value:
            return "[]"
        if all(isinstance(item, dict) for item in value):
            # Format complex objects in lists more carefully
            formatted_items = []
            for item in value:
                item_str = "{"
                for k, v in sorted(item.items()):
                    item_str += f" {k} = {format_value(v)},"
                item_str += " }"
                formatted_items.append(item_str)
            return f"[\n    {',\n    '.join(formatted_items)}\n  ]"
        else:
            # Format simple values in lists
            formatted_items = [format_value(item) for item in value]
            if len(', '.join(formatted_items)) > 60:  # Line break for long lists
                return f"[\n    {',\n    '.join(formatted_items)}\n  ]"
            else:
                return f"[{', '.join(formatted_items)}]"
    elif isinstance(value, dict):
        try:
            # Format dictionary contents
            if not value:
                return "{}"
            formatted_items = []
            for k, v in sorted(value.items()):
                formatted_items.append(f"{k} = {format_value(v)}")
            if len(', '.join(formatted_items)) > 60:  # Line break for long dicts
                return f"{{\n    {',\n    '.join(formatted_items)}\n  }}"
            else:
                return f"{{ {', '.join(formatted_items)} }}"
        except:
            return str(value)
    else:
        return str(value)

def create_detailed_change_output(resource: Dict) -> str:
    """Create detailed textual representation of the changes for a resource"""
    # Get the necessary information
    address = resource.get('address', 'Unknown')
    resource_type = resource.get('type', 'Unknown')
    actions = resource.get('actions', [])
    before = resource.get('before', {}) or {}  # Ensure before is a dict, not None
    after = resource.get('after', {}) or {}    # Ensure after is a dict, not None
    
    if 'update' in actions:
        action_description = "will be updated in-place"
        symbol = "~"
    elif 'create' in actions:
        action_description = "will be created"
        symbol = "+"
    elif 'delete' in actions:
        action_description = "will be destroyed"
        symbol = "-"
    else:
        # For other actions like 'read', 'no-op', etc.
        return ""  # Skip detailed output for non-standard actions
    
    # Split address into type and name parts
    address_parts = address.split('.')
    if len(address_parts) >= 2:
        # For module resources or resources with longer addresses
        resource_display_type = address_parts[0]
        resource_display_name = '.'.join(address_parts[1:])
    else:
        # Fallback if we can't properly split
        resource_display_type = resource_type
        resource_display_name = address
    
    # Start building the output
    output = f"# {address} {action_description}\n"
    output += f"{symbol} resource \"{resource_display_type}\" \"{resource_display_name}\" {{\n"
    
    # For simple scalar attributes, add them directly to the output
    all_keys = set(before.keys()) | set(after.keys())
    
    # Always include id and name if available
    for key in ['id', 'name']:
        if key in all_keys:
            if key in after:
                val = after[key]
                formatted_val = format_value(val)
                output += f" {key} = {formatted_val}\n"
    
    # Process the rest of the attributes
    processed_keys = set(['id', 'name'])  # Keep track of already processed keys
    
    # Process nested objects and changes first
    for key in sorted(all_keys):
        if key in processed_keys:
            continue  # Skip already processed keys
            
        before_val = before.get(key)
        after_val = after.get(key)
        
        # Skip if both values are None
        if before_val is None and after_val is None:
            continue
            
        # Process nested objects and changes
        if key in before and key in after and before_val != after_val:
            # For update: show both values
            action_symbol = "~"
            
            # Handle different types of data structures
            if isinstance(before_val, dict) and isinstance(after_val, dict):
                # For nested dictionary objects
                output += f" {action_symbol} {key} {{\n"
                
                # Process nested attributes
                nested_keys = set(before_val.keys()) | set(after_val.keys())
                processed_nested_keys = []
                
                for nested_key in sorted(nested_keys):
                    nested_before = before_val.get(nested_key)
                    nested_after = after_val.get(nested_key)
                    
                    if nested_before != nested_after:
                        processed_nested_keys.append(nested_key)
                        
                        # Format the values
                        formatted_before = format_value(nested_before)
                        formatted_after = format_value(nested_after)
                        
                        output += f"  {action_symbol} {nested_key} = {formatted_before} -> {formatted_after}\n"
                
                # Add comment about hidden attributes
                hidden_count = len(nested_keys) - len(processed_nested_keys)
                if hidden_count > 0:
                    output += f"  # ({hidden_count} unchanged attributes hidden)\n"
                
                output += " }\n"
                
            elif isinstance(before_val, list) and isinstance(after_val, list):
                # For list changes, we need to show the actual content differences
                
                # Enhanced list comparison to identify changes
                if len(before_val) == len(after_val):
                    # Check if the lists contain dictionaries
                    if all(isinstance(x, dict) for x in before_val + after_val):
                        # For lists of dictionaries (common in Terraform resources)
                        
                        # Try to identify the changed items by comparing the list entries
                        changed_items = False
                        
                        # If lists of dicts, we need to identify the changes in detail
                        output += f" {action_symbol} {key} = [\n"
                        
                        # Try to match items by position or by common identifier fields
                        for i in range(len(before_val)):
                            before_item = before_val[i]
                            after_item = after_val[i]
                            
                            # Check if the items are different
                            if before_item != after_item:
                                changed_items = True
                                output += f"   {action_symbol} {{ # item {i}\n"
                                
                                # Find the keys that differ
                                all_item_keys = set(before_item.keys()) | set(after_item.keys())
                                for item_key in sorted(all_item_keys):
                                    before_field = before_item.get(item_key)
                                    after_field = after_item.get(item_key)
                                    
                                    if before_field != after_field:
                                        formatted_before = format_value(before_field)
                                        formatted_after = format_value(after_field)
                                        output += f"     {action_symbol} {item_key} = {formatted_before} -> {formatted_after}\n"
                                    else:
                                        # Show unchanged fields
                                        formatted_val = format_value(before_field)
                                        output += f"       {item_key} = {formatted_val}\n"
                                
                                output += "   },\n"
                            else:
                                # Item is unchanged, show it in abbreviated form
                                first_field = next(iter(before_item.items()), ('unnamed', None))
                                output += f"     {{ # unchanged item {i} ({first_field[0]} = {format_value(first_field[1])}) }},\n"
                        
                        output += " ]\n"
                        
                        if not changed_items:
                            # If we couldn't identify specific changes, just show summary
                            output = output.replace(f" {action_symbol} {key} = [\n", f" {action_symbol} {key} = {format_value(before_val)} -> {format_value(after_val)}\n")
                    else:
                        # For lists of simple values
                        formatted_before = format_value(before_val)
                        formatted_after = format_value(after_val)
                        output += f" {action_symbol} {key} = {formatted_before} -> {formatted_after}\n"
                else:
                    # Different length lists
                    formatted_before = format_value(before_val)
                    formatted_after = format_value(after_val)
                    output += f" {action_symbol} {key} = {formatted_before} -> {formatted_after}\n"
            else:
                # For scalar values
                formatted_before = format_value(before_val)
                formatted_after = format_value(after_val)
                
                output += f" {action_symbol} {key} = {formatted_before} -> {formatted_after}\n"
            
            processed_keys.add(key)
    
    # Add other attributes for create/delete actions
    for key in sorted(all_keys):
        if key in processed_keys:
            continue  # Skip already processed keys
            
        before_val = before.get(key)
        after_val = after.get(key)
        
        # Skip if both values are None
        if before_val is None and after_val is None:
            continue
            
        if key in after and key not in before and 'create' in actions:
            # For create: show only new value
            action_symbol = "+"
            formatted_val = format_value(after_val)
            output += f" {action_symbol} {key} = {formatted_val}\n"
            
        elif key in before and key not in after and 'delete' in actions:
            # For delete: show only old value
            action_symbol = "-"
            formatted_val = format_value(before_val)
            output += f" {action_symbol} {key} = {formatted_val}\n"
            
        processed_keys.add(key)
    
    # Add comment about hidden attributes for the resource
    visible_attrs = len(processed_keys)
    total_attrs = len(all_keys)
    hidden_count = total_attrs - visible_attrs
    if hidden_count > 0:
        output += f" # ({hidden_count} unchanged attributes hidden)\n"
    
    output += "}"
    
    return output

def setup_gemini_api():
    """Setup the Gemini API with credentials from environment variables"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable is not set")
        sys.exit(1)
    
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-001")
    logger.info(f"Using Gemini model: {model_name}")
    
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)

def parse_terraform_plan(plan_file: str) -> Dict:
    """Parse the Terraform plan.json file"""
    try:
        with open(plan_file, 'r') as f:
            plan_data = json.load(f)
        return plan_data
    except Exception as e:
        logger.error(f"Failed to parse Terraform plan file: {e}")
        sys.exit(1)

def sanitize_sensitive_values(data: Any, sensitive_paths: Set[str] = None, current_path: str = "", sensitive_fields: Set[str] = None) -> Any:
    """
    Recursively sanitize sensitive values in the data.
    
    Args:
        data: The data to sanitize
        sensitive_paths: Set of paths to sensitive values from the terraform plan
        current_path: Current path in the data structure
        sensitive_fields: Set of field names that should be considered sensitive
        
    Returns:
        Sanitized data
    """
    if sensitive_paths is None:
        sensitive_paths = set()
    
    if sensitive_fields is None:
        sensitive_fields = set()
        # Generate regex patterns for sensitive field names
        for pattern in SENSITIVE_FIELD_PATTERNS:
            sensitive_fields.add(pattern)
    
    # Make a deep copy to avoid modifying the original data
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            # Build the current path for this key
            new_path = f"{current_path}.{key}" if current_path else key
            
            # Check if this key is sensitive based on name patterns
            key_is_sensitive = any(pattern in key.lower() for pattern in sensitive_fields)
            
            # Check if this path is marked as sensitive in the plan
            path_is_sensitive = new_path in sensitive_paths
            
            if key_is_sensitive or path_is_sensitive:
                if isinstance(value, (str, int, float, bool)) and value:
                    # Redact sensitive scalar values
                    result[key] = "[REDACTED]"
                elif isinstance(value, (dict, list)) and value:
                    # For complex types, indicate they were redacted but keep structure
                    result[key] = "[REDACTED_COMPLEX_VALUE]"
                else:
                    # Null, empty dicts, empty lists - keep as is
                    result[key] = value
            else:
                # Recursively sanitize non-sensitive fields
                result[key] = sanitize_sensitive_values(
                    value, sensitive_paths, new_path, sensitive_fields
                )
        return result
    elif isinstance(data, list):
        return [
            sanitize_sensitive_values(item, sensitive_paths, f"{current_path}[{i}]", sensitive_fields)
            for i, item in enumerate(data)
        ]
    else:
        return data

def extract_sensitive_paths(plan_data: Dict) -> Set[str]:
    """
    Extract paths to all sensitive values from the Terraform plan.
    
    Args:
        plan_data: The parsed Terraform plan
        
    Returns:
        Set of paths to sensitive values
    """
    sensitive_paths = set()
    
    # Process resource changes
    if 'resource_changes' in plan_data:
        for resource in plan_data['resource_changes']:
            resource_address = resource.get('address', '')
            
            # Check before_sensitive
            if 'change' in resource and 'before_sensitive' in resource['change']:
                before_sensitive = resource['change']['before_sensitive']
                extract_sensitive_keys(before_sensitive, resource_address, sensitive_paths)
            
            # Check after_sensitive
            if 'change' in resource and 'after_sensitive' in resource['change']:
                after_sensitive = resource['change']['after_sensitive']
                extract_sensitive_keys(after_sensitive, resource_address, sensitive_paths)
    
    return sensitive_paths

def extract_sensitive_keys(sensitive_data: Any, current_path: str, sensitive_paths: Set[str], is_sensitive: bool = False) -> None:
    """
    Recursively extract sensitive keys from sensitive data structure.
    
    Args:
        sensitive_data: The sensitive data structure from the plan
        current_path: Current path in the data structure
        sensitive_paths: Set to store sensitive paths
        is_sensitive: Whether the parent was marked as sensitive
    """
    if isinstance(sensitive_data, dict):
        for key, value in sensitive_data.items():
            new_path = f"{current_path}.{key}" if current_path else key
            if value is True or is_sensitive:
                sensitive_paths.add(new_path)
            extract_sensitive_keys(value, new_path, sensitive_paths, value is True or is_sensitive)
    elif isinstance(sensitive_data, list):
        for i, item in enumerate(sensitive_data):
            new_path = f"{current_path}[{i}]"
            extract_sensitive_keys(item, new_path, sensitive_paths, is_sensitive)

def extract_resource_changes(plan_data: Dict) -> List[Dict]:
    """Extract resource changes from the plan data"""
    resource_changes = []
    
    # Check if resource_changes exists in the plan
    if 'resource_changes' not in plan_data:
        logger.warning("No resource changes found in plan")
        return resource_changes
    
    # Extract sensitive paths from the plan
    sensitive_paths = extract_sensitive_paths(plan_data)
    logger.info(f"Found {len(sensitive_paths)} sensitive paths in the plan")
    
    for resource in plan_data['resource_changes']:
        # Skip resources with no actions
        if not resource.get('change', {}).get('actions'):
            continue
            
        actions = resource['change']['actions']
        
        # Skip resources with no-op actions
        if actions == ['no-op']:
            continue
        
        # Extract resource type and provider
        resource_type = resource.get('type', 'Unknown')
        provider_name = resource.get('provider_name', '')
        
        # Determine documentation URL
        doc_url = get_resource_doc_url(provider_name, resource_type)
        
        # Get the before and after values
        before = resource.get('change', {}).get('before', {})
        after = resource.get('change', {}).get('after', {})
        
        # Sanitize sensitive values
        sanitized_before = sanitize_sensitive_values(before, sensitive_paths)
        sanitized_after = sanitize_sensitive_values(after, sensitive_paths)
        
        # Fix for the problem - check if after_sensitive is a dictionary before calling items()
        sensitive_fields = []
        after_sensitive = resource.get('change', {}).get('after_sensitive', {})
        if isinstance(after_sensitive, dict):
            sensitive_fields = [
                key for key, is_sensitive in after_sensitive.items()
                if is_sensitive
            ]
            
        resource_info = {
            'address': resource.get('address', 'Unknown'),
            'type': resource_type,
            'name': resource.get('name', 'Unknown'),
            'provider_name': provider_name,
            'actions': actions,
            'doc_url': doc_url,
            'before': sanitized_before,
            'after': sanitized_after,
            'sensitive_fields': sensitive_fields
        }
        
        resource_changes.append(resource_info)
    
    return resource_changes

def analyze_resource_change(resource: Dict) -> Dict:
    """Analyze a single resource change and provide insights"""
    
    # Extract relevant information from the resource
    address = resource.get('address', 'Unknown')
    resource_type = resource.get('type', 'Unknown')
    provider_name = resource.get('provider_name', '')
    actions = resource.get('actions', [])
    before = resource.get('before', {})
    after = resource.get('after', {})
    doc_url = resource.get('doc_url', '')
    
    # 1. Change Summary
    change_summary = f"Changes detected for resource {address} ({resource_type}) - Actions: {', '.join(actions)}"
    
    analysis = {
        'change_summary': change_summary,
    }
    
    return analysis

def format_resource_changes(resource_changes: List[Dict]) -> str:
    """Format resource changes for Gemini API input"""
    if not resource_changes:
        return "No changes detected in the Terraform plan."

    formatted_changes = []

    for resource in resource_changes:
        # Analyze the resource change
        analysis = analyze_resource_change(resource)

        # Create detailed change text
        detailed_change = create_detailed_change_output(resource)

        change_description = f"""
Resource: {resource['address']}
Type: {resource['type']}
Documentation: {resource['doc_url']}

Change Summary:
{analysis['change_summary']}
{detailed_change}
"""
        formatted_changes.append(change_description)

    return "\n\n===\n\n".join(formatted_changes)

def read_terraform_files(tf_directory: str, max_files: int = None) -> str:
    """Read all Terraform files in the specified directory and subdirectories"""
    terraform_code = []
    
    # Find all .tf files in the specified directory and subdirectories
    tf_files = glob.glob(f"{tf_directory}/**/*.tf", recursive=True)
    
    if not tf_files:
        # Try again without recursive if no files found (for older Python versions)
        tf_files = glob.glob(f"{tf_directory}/*.tf")
    
    if not tf_files:
        logger.warning(f"No Terraform files found in {tf_directory}")
        return ""
    
    # Sort files for consistent output
    tf_files.sort()
    
    # Limit number of files if specified
    if max_files and len(tf_files) > max_files:
        logger.warning(f"Limiting analysis to {max_files} Terraform files (out of {len(tf_files)} found)")
        tf_files = tf_files[:max_files]
    
    logger.info(f"Reading {len(tf_files)} Terraform files")
    
    # Read each file
    for file_path in tf_files:
        try:
            with open(file_path, 'r') as f:
                relative_path = os.path.relpath(file_path, tf_directory)
                file_content = f.read()
                
                # Remove sensitive values from the code
                for pattern in SENSITIVE_FIELD_PATTERNS:
                    # Find patterns like key = "value" or key = value
                    file_content = re.sub(
                        rf'({pattern}\w*)\s*=\s*"[^"]*"', 
                        r'\1 = "[REDACTED]"', 
                        file_content, 
                        flags=re.IGNORECASE
                    )
                    file_content = re.sub(
                        rf'({pattern}\w*)\s*=\s*[^\s,"{{}}]+', 
                        r'\1 = [REDACTED]', 
                        file_content, 
                        flags=re.IGNORECASE
                    )
                
                terraform_code.append(f"# File: {relative_path}\n\n{file_content}")
        except Exception as e:
            logger.warning(f"Error reading Terraform file {file_path}: {e}")
    
    return "\n\n" + "\n\n".join(terraform_code)

def estimate_token_count(text: str) -> int:
    """Estimate the number of tokens in a text string"""
    # This is a simple estimation - actual token count may vary
    return int(len(text) * TOKENS_PER_CHAR)

def create_prompt(changes_text: str, terraform_code: str = "") -> str:
    """Create the prompt for Gemini analysis"""
    
    # Read the prompt from the prompt.txt file
    try:
        with open("prompt.txt", "r") as f:
            prompt = f.read()
    except Exception as e:
        logger.error(f"Error reading prompt file: {e}")
        return ""
    
    # Add Terraform code context if available
    terraform_context = ""
    if terraform_code:
        terraform_context = f"""
I've also included the Terraform code that defines these resources. Use this to understand the relationships between resources and how they're configured:

```hcl
{terraform_code}
```

"""
    
    # Replace placeholders in the prompt
    prompt = prompt.replace("{terraform_context}", terraform_context)
    prompt = prompt.replace("{changes_text}", changes_text)
    
    return prompt

def analyze_with_gemini(model, prompt: str, dry_run: bool = False) -> str:
    """Use Gemini API to analyze the changes with context from Terraform code"""
    
    if dry_run:
        logger.info("Dry run mode - not sending prompt to Gemini API")
        return "DRY RUN MODE - Analysis not performed. Enable with --send-to-gemini flag."
    
    try:
        response = model.generate_content(prompt)
        response = response.text.replace('+!+!+!+!+!+!', "")
        response = response.strip()
        # Remove ``` from the beginning and end of the response
        response = re.sub(r"^```\n?", "", response)
        response = re.sub(r"\n?```$", "", response)

        return response

    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return f"Error analyzing plan: {str(e)}"

def send_gemini_response_to_gitlab(response_text: str):
    """Send the Gemini response to a comment in the GitLab Merge Request"""
    import gitlab
    
    # Get the GitLab token from the environment variable
    gitlab_token = os.environ.get("GITLAB_TOKEN")
    if not gitlab_token:
        logger.error("GITLAB_TOKEN environment variable is not set")
        return

    # Get the GitLab project ID from the environment variable
    project_id = os.environ.get("CI_PROJECT_ID")
    if not project_id:
        logger.error("CI_PROJECT_ID environment variable is not set")
        return

    # Get the Merge Request IID from the environment variable
    mr_iid = os.environ.get("CI_MERGE_REQUEST_IID")
    if not mr_iid:
        logger.error("CI_MERGE_REQUEST_IID environment variable is not set")
        return
    
    # Get commit ID and related information
    commit_id = os.environ.get("CI_COMMIT_SHA", "unknown")
    commit_short_id = commit_id[:8] if len(commit_id) >= 8 else commit_id
    commit_ref = os.environ.get("CI_COMMIT_REF_NAME", "unknown branch")
    commit_url = os.environ.get("CI_PROJECT_URL", "") 
    if commit_url and commit_id != "unknown":
        commit_url = f"{commit_url}/-/commit/{commit_id}"
    else:
        commit_url = "#"
    
    # Comment identifier to ensure we can find our comment later
    comment_identifier = f"<!-- terraform-plan-analyzer-{mr_iid} -->"
    comment_header = f"Terraform Plan Analysis by Gemini"

    try:
        # Connect to the GitLab API
        gl = gitlab.Gitlab('https://gitlab.com', private_token=gitlab_token)

        # Get the project
        project = gl.projects.get(project_id)

        # Get the Merge Request
        mr = project.mergerequests.get(mr_iid)

        # Search for existing comments from this script
        comments = mr.notes.list(all=True)  # Get all comments
        existing_comment = None
        
        logger.info(f"Searching for existing comment among {len(comments)} comments...")
        
        # First try to find by our hidden identifier (most reliable)
        for comment in comments:
            if comment_identifier in comment.body:
                existing_comment = comment
                logger.info(f"Found existing comment with identifier: {comment.id}")
                break
                
        # If not found, try to find by the standard header (for backward compatibility)
        if not existing_comment:
            for comment in comments:
                if comment.body.strip().startswith(comment_header):
                    existing_comment = comment
                    logger.info(f"Found existing comment by header: {comment.id}")
                    break

        # Prepare the comment body with our identifier and commit information
        commit_info = f"Analysis for commit: [{commit_short_id}]({commit_url}) ({commit_ref})"
        
        comment_body = f"""
{comment_identifier}
## {comment_header}

**{commit_info}**

{response_text}

"""

        # Create or update the comment
        if existing_comment:
            existing_comment.body = comment_body
            existing_comment.save()
            logger.info(f"Updated existing comment (ID: {existing_comment.id}) in Merge Request !{mr_iid}")
        else:
            new_comment = mr.notes.create({'body': comment_body})
            logger.info(f"Created new comment (ID: {new_comment.id}) in Merge Request !{mr_iid}")
            
    except Exception as e:
        logger.error(f"Error while interacting with GitLab API: {e}")

def main():
    parser = argparse.ArgumentParser(description='Analyze Terraform plan using Gemini API')
    parser.add_argument('--plan', required=True, help='Path to the Terraform plan.json file')
    parser.add_argument('--output', default='terraform_analysis.md', help='Output file for the analysis')
    parser.add_argument('--save-sanitized', default=None, help='Save the sanitized plan to this file')
    parser.add_argument('--tf-dir', default='.', help='Directory containing Terraform files to analyze')
    parser.add_argument('--skip-code', action='store_true', help='Skip analyzing Terraform code files')
    parser.add_argument('--max-files', type=int, default=None, help='Maximum number of Terraform files to include')
    parser.add_argument('--save-prompt', default=None, help='Save the prompt to a file without sending to Gemini')
    parser.add_argument('--send-to-gemini', action='store_true', help='Actually send the prompt to Gemini (otherwise dry run)')
    parser.add_argument('--gitlab-comment', action='store_true', help='Send the Gemini response to a comment in the GitLab Merge Request')

    args = parser.parse_args()

    # Parse the Terraform plan
    plan_data = parse_terraform_plan(args.plan)
    
    # Extract resource changes
    resource_changes = extract_resource_changes(plan_data)
    
    # Optionally save the sanitized plan
    if args.save_sanitized:
        # Create a sanitized copy of the plan
        sensitive_paths = extract_sensitive_paths(plan_data)
        sanitized_plan = sanitize_sensitive_values(copy.deepcopy(plan_data), sensitive_paths)
        
        with open(args.save_sanitized, 'w') as f:
            json.dump(sanitized_plan, f, indent=2)
        logger.info(f"Sanitized plan saved to {args.save_sanitized}")
    
    terraform_code = ""
    if not args.skip_code:
        # Read and sanitize Terraform files
        terraform_code = read_terraform_files(args.tf_dir, args.max_files)
    
    if not resource_changes:
        analysis = "No changes detected in the Terraform plan."
    else:
        # Format changes for Gemini
        formatted_changes = format_resource_changes(resource_changes)
        
        # Create the prompt
        prompt = create_prompt(formatted_changes, terraform_code)
        
        # Check if the prompt is likely to exceed model's context window
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-001")
        token_estimate = estimate_token_count(prompt)
        model_limit = GEMINI_CONTEXT_LIMITS.get(model_name, 30000)  # Default to 30K if unknown
        
        logger.info(f"Estimated prompt size: {token_estimate} tokens (model limit: {model_limit})")
        
        if token_estimate > model_limit:
            logger.warning(f"Prompt likely exceeds model context window ({token_estimate} > {model_limit})")
            
            # If we have code, try reducing it first
            if terraform_code and not args.skip_code:
                # Try with just half the code files
                if args.max_files is None:
                    tf_files = glob.glob(f"{args.tf_dir}/**/*.tf", recursive=True)
                    suggested_max = max(1, len(tf_files) // 2)
                    logger.warning(f"Try using --max-files={suggested_max} to reduce context size")
            
            # Other suggestions
            logger.warning("Other options to reduce context size:")
            logger.warning("1. Use --skip-code to exclude Terraform code")
            logger.warning("2. Focus on a smaller subset of Terraform files")
            logger.warning("3. Split your Terraform plan into smaller chunks")
            
            if not args.send_to_gemini:
                logger.error("Aborting due to context size - use --send-to-gemini to override")
                sys.exit(1)
        
        # Save the prompt if requested
        if args.save_prompt:
            with open(args.save_prompt, 'w') as f:
                f.write(prompt)
            logger.info(f"Prompt saved to {args.save_prompt}")
        
        # Initialize the Gemini model if we're going to use it
        model = None
        if args.send_to_gemini:
            model = setup_gemini_api()
        
        # Analyze with Gemini (or dry run)
        analysis = analyze_with_gemini(model, prompt, not args.send_to_gemini)

        # Send the analysis to GitLab if requested
        if args.gitlab_comment:
            send_gemini_response_to_gitlab(analysis)

    # Write the analysis to a file
    with open(args.output, 'w') as f:
        f.write(analysis)

    logger.info(f"Analysis written to {args.output}")

    # If this was a dry run, show next steps
    if not args.send_to_gemini:
        print("\n" + "="*50)
        print("DRY RUN COMPLETED")
        print("To send this analysis to Gemini, add the --send-to-gemini flag")
        if args.save_prompt:
            print(f"You can review the prompt that would be sent in: {args.save_prompt}")
        print("="*50 + "\n")

if __name__ == "__main__":
    main()
