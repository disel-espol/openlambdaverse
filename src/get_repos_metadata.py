import os
import glob
import json
import logging
import requests
import time
from urllib.parse import urlparse
from dotenv import load_dotenv  # Import dotenv to load environment variables

import yaml

# A generic constructor to handle all AWS CloudFormation tags
def generic_constructor(loader, tag_suffix, node):
    # This will handle scalar, sequence, and mapping nodes
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None

# Register the constructor for all AWS CloudFormation tags
yaml.SafeLoader.add_constructor('!Ref', generic_constructor)
yaml.SafeLoader.add_constructor('!GetAtt', generic_constructor)
yaml.SafeLoader.add_constructor('!Sub', generic_constructor)
yaml.SafeLoader.add_constructor('!Join', generic_constructor)
yaml.SafeLoader.add_constructor('!ImportValue', generic_constructor)
yaml.SafeLoader.add_constructor('!Select', generic_constructor)
yaml.SafeLoader.add_constructor('!Split', generic_constructor)
yaml.SafeLoader.add_constructor('!GetAZs', generic_constructor)
yaml.SafeLoader.add_constructor('!Base64', generic_constructor)
yaml.SafeLoader.add_constructor('!Cidr', generic_constructor)
yaml.SafeLoader.add_constructor('!FindInMap', generic_constructor)
yaml.SafeLoader.add_constructor('!Transform', generic_constructor)

# Conditional functions
yaml.SafeLoader.add_constructor('!And', generic_constructor)
yaml.SafeLoader.add_constructor('!Or', generic_constructor)
yaml.SafeLoader.add_constructor('!Not', generic_constructor)
yaml.SafeLoader.add_constructor('!Equals', generic_constructor)
yaml.SafeLoader.add_constructor('!If', generic_constructor)
yaml.SafeLoader.add_constructor('!Condition', generic_constructor)

# Load environment variables from a .env file if present
load_dotenv()

# Find the most recent code search directory in data/processed
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if latest_dir:
    FILTERED_REPO_URLS_DIR = os.path.join(latest_dir, "filtered_repo_urls")
    LOGS_DIR = os.path.join(latest_dir, "logs")
    RESULTS_DIR = os.path.join(latest_dir, "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
else:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

INPUT_FILENAME = os.path.join(FILTERED_REPO_URLS_DIR, "filtered_repo_urls.txt")
OUTPUT_FILENAME = os.path.join(RESULTS_DIR, "repository_metadata.jsonl")
LOG_FILENAME = os.path.join(LOGS_DIR, "extract_repo_metadata_log.log")

GITHUB_TOKEN = os.getenv("GITHUB_AUTH_TOKEN")
if not GITHUB_TOKEN:
    raise EnvironmentError("GITHUB_AUTH_TOKEN environment variable is not set.")

# Logging setup
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILENAME, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# GitHub REST API setup
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
RATE_LIMIT_REMAINING = 5000
RATE_LIMIT_RESET = None

def fetch_serverless_yaml(repo_owner_slash_repo):
    """Fetch the content of all serverless.yml/serverless.yaml files from a repository."""
    if '/' not in repo_owner_slash_repo:
        logging.warning(f"Invalid repository string: {repo_owner_slash_repo}. Expected 'owner/repo'.")
        return []
    owner, repo = repo_owner_slash_repo.split("/", 1)
    
    repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        repo_response = requests.get(repo_api_url, headers=HEADERS, timeout=15)
        check_rate_limit(repo_response.headers)
        repo_response.raise_for_status()
        repo_data = repo_response.json()
        default_branch = repo_data.get("default_branch", "main")
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch repository details for {owner}/{repo}: {e}")
        return []

    tree_api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    try:
        tree_response = requests.get(tree_api_url, headers=HEADERS, timeout=30) # Longer timeout for potentially large trees
        check_rate_limit(tree_response.headers)
        tree_response.raise_for_status()
        tree_data = tree_response.json()
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch repository tree for {owner}/{repo}: {e}")
        if isinstance(e, requests.HTTPError) and (e.response.status_code == 404 or \
            (e.response.status_code == 409 and "empty" in e.response.text.lower())):
            logging.info(f"Repository tree not found or empty for {owner}/{repo} (branch: {default_branch}).")
        return []

    if not tree_data.get("tree"):
        logging.info(f"Repository tree for {owner}/{repo} (branch: {default_branch}) is empty or missing key.")
        return []
            
    serverless_files_content = []
    for item in tree_data.get("tree", []):
        if (item["path"].endswith("serverless.yml") or item["path"].endswith("serverless.yaml")) \
           and item.get("type") == "blob":
            
            file_contents_url = item.get("url") 
            if not file_contents_url: 
                file_contents_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{item['path']}?ref={default_branch}"
            
            try:
                file_response = requests.get(file_contents_url, headers=HEADERS, timeout=15) # Headers for blob API might differ if raw needed
                check_rate_limit(file_response.headers)
                file_response.raise_for_status()
                file_data = file_response.json()
                
                if file_data.get("encoding") == "base64" and file_data.get("content"):
                    import base64
                    content_to_decode = file_data["content"].replace("\n", "") # GitHub API sometimes adds newlines
                    try:
                        yaml_content = base64.b64decode(content_to_decode).decode("utf-8")
                        serverless_files_content.append({"path": item["path"], "content": yaml_content})
                    except (UnicodeDecodeError, base64.binascii.Error) as decode_err:
                        logging.warning(f"Failed to decode base64 content for {item['path']} in {owner}/{repo}: {decode_err}")
                elif file_data.get("content"): # If content is not base64 but present
                     serverless_files_content.append({"path": item["path"], "content": file_data["content"]})
                else:
                    logging.warning(f"No content or unexpected encoding for {item['path']} in {owner}/{repo}. SHA: {file_data.get('sha', 'N/A')}")
            except requests.RequestException as file_req_err:
                logging.warning(f"Failed to fetch {item['path']} for {owner}/{repo} (URL: {file_contents_url}): {file_req_err}")
            except json.JSONDecodeError as json_err:
                 logging.warning(f"Failed to parse JSON response for file {item['path']} in {owner}/{repo}: {json_err}")

    return serverless_files_content

def parse_serverless_yaml(yaml_content):
    """Parse the serverless.yml content and extract relevant configuration."""
    try:
        logging.debug(f"Parsing YAML content (first 500 chars): {yaml_content[:500]}")
        if not isinstance(yaml_content, str):
            logging.error(f"Expected a string for yaml_content, but got {type(yaml_content)}")
            return None

        config = yaml.safe_load(yaml_content) # This is where YAMLError can occur
        logging.debug(f"Parsed YAML content: {config}")

        if not isinstance(config, dict):
            logging.warning(f"Parsed YAML content is not a dictionary (type: {type(config)}). Content: {str(config)[:200]}")
            if isinstance(config, str) and config.startswith("!"): # e.g. root is just "!ImportValue something"
                return {
                    "plugins": [], "runtimes": [None], "events": {}, "provider_name": "unknown",
                    "parse_error": "YAML root is a CloudFormation intrinsic function."
                }
            return None 

        provider_data = config.get("provider")
        runtime_from_provider = None
        provider_name_from_provider = "unknown" 
        known_provider_strings = ["aws", "azure", "google", "gcp", "aliyun", "tencent", "ibm", "openwhisk", "knative", "cloudflare", "fn", "kubeless", "spotinst", "other"]

        if isinstance(provider_data, dict):
            runtime_from_provider = provider_data.get("runtime")
            provider_name_from_provider = provider_data.get("name", "unknown")
        elif provider_data is not None: 
            logging.warning(
                f"Provider configuration is not a dictionary (type: {type(provider_data)}, value: '{str(provider_data)[:100]}'). "
                f"Attempting to infer provider name if it's a known string."
            )
            if isinstance(provider_data, str) and provider_data.lower() in known_provider_strings:
                provider_name_from_provider = provider_data.lower()
                logging.info(f"Inferred provider_name as '{provider_name_from_provider}' from string value.")
        
        plugins_value = config.get("plugins")
        actual_plugins = []
        if isinstance(plugins_value, list):
            actual_plugins = plugins_value
        elif plugins_value is not None: 
            logging.warning(f"Interpreting 'plugins' as empty list. Original type: {type(plugins_value)}, value: {str(plugins_value)[:100]}")
        
        events_data = config.get("functions", {}) # 'functions' block contains event definitions

        serverless_config_output = {
            "plugins": actual_plugins,
            "runtimes": [runtime_from_provider], 
            "events": events_data,
            "provider_name": provider_name_from_provider
        }
        return serverless_config_output
    except yaml.YAMLError as e: # Catches errors from yaml.safe_load()
        logging.error(f"Failed to parse serverless.yml content: {e} (Content snippet: {yaml_content[:200]})")
        return None
    except Exception as e: 
        logging.error(f"Unexpected error parsing serverless.yml: {e} (Content snippet: {yaml_content[:200]})")
        return None


def check_rate_limit(response_headers=None):
    """Check GitHub API rate limit and sleep if necessary."""
    global RATE_LIMIT_REMAINING, RATE_LIMIT_RESET
    
    if response_headers: 
        try:
            RATE_LIMIT_REMAINING = int(response_headers.get('X-RateLimit-Remaining', RATE_LIMIT_REMAINING))
            RATE_LIMIT_RESET = int(response_headers.get('X-RateLimit-Reset', RATE_LIMIT_RESET))
        except (ValueError, TypeError):
            logging.warning("Could not parse rate limit headers. Fetching explicitly.")
        else: 
            logging.debug(f"Rate limit remaining (from headers): {RATE_LIMIT_REMAINING}")
            if RATE_LIMIT_REMAINING <= 30: # Increased buffer
                sleep_duration = max(0, RATE_LIMIT_RESET - time.time()) + 15 # Increased buffer sleep
                if sleep_duration > 0:
                    logging.warning(f"Rate limit low ({RATE_LIMIT_REMAINING}). Sleeping for {sleep_duration:.2f} seconds.")
                    time.sleep(sleep_duration)
            return 

    try: # Explicit fetch if no headers or header parsing failed
        response = requests.get("https://api.github.com/rate_limit", headers=HEADERS, timeout=10)
        response.raise_for_status()
        rate_limit_data = response.json()
        RATE_LIMIT_REMAINING = rate_limit_data["rate"]["remaining"]
        RATE_LIMIT_RESET = rate_limit_data["rate"]["reset"]
        logging.debug(f"Rate limit remaining (explicit fetch): {RATE_LIMIT_REMAINING}")
        if RATE_LIMIT_REMAINING <= 30:
            sleep_duration = max(0, RATE_LIMIT_RESET - time.time()) + 15
            if sleep_duration > 0:
                logging.warning(f"Rate limit low ({RATE_LIMIT_REMAINING}). Sleeping for {sleep_duration:.2f} seconds.")
                time.sleep(sleep_duration)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch rate limit: {e}. Sleeping for 60s.")
        time.sleep(60)
    except (KeyError, json.JSONDecodeError) as e:
        logging.error(f"Error parsing rate limit response: {e}. Sleeping for 60s.")
        time.sleep(60)

def get_repo_metadata(repo_full_url_str): 
    """Fetch metadata for a given repository URL."""
    parsed_url = urlparse(repo_full_url_str)
    path_parts = parsed_url.path.strip("/").split("/")
    if len(path_parts) < 2:
        logging.warning(f"Invalid repository URL: {repo_full_url_str}")
        return None
    owner, repo_name = path_parts[0], path_parts[1] 
    
    metadata_result = { 
        "repository": f"{owner}/{repo_name}", "url": repo_full_url_str, 
        "serverless_config": [], "github_metadata": {}
    }

    repo_api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    try:
        response = requests.get(repo_api_url, headers=HEADERS, timeout=15)
        check_rate_limit(response.headers)
        response.raise_for_status()
        repo_data = response.json()
    except requests.Timeout:
        logging.error(f"Timeout fetching repo details for {owner}/{repo_name}.")
        return None
    except requests.HTTPError as e:
        logging.warning(f"HTTP error for {owner}/{repo_name}: {e.response.status_code} - {e.response.text}")
        return None 
    except requests.RequestException as e:
        logging.error(f"Request exception for {owner}/{repo_name}: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON for repo details of {owner}/{repo_name}: {e}")
        return None

    # Gather other metadata, calling API helper functions
    contributors = get_repo_contributors(owner, repo_name)
    tags = get_repo_tags(owner, repo_name)
    languages = get_repo_languages(owner, repo_name)
    last_commit = get_last_commit_date(owner, repo_name)

    metadata_result["github_metadata"] = {
        "size_kb": repo_data.get("size"), "forks": repo_data.get("forks_count"),
        "stars": repo_data.get("stargazers_count"), "topics": repo_data.get("topics", []),
        "primary_language": repo_data.get("language"), "archived": repo_data.get("archived"),
        "disabled": repo_data.get("disabled"), "visibility": repo_data.get("visibility"),
        "languages_bytes": languages, "contributor_logins": contributors,
        "contributor_count": len(contributors),
        "private_vulnerability_reporting_enabled": check_security_feature(owner, repo_name, "private-vulnerability-reporting"),
        "tags": tags, "tag_count": len(tags),
    }
    metadata_result.update({
        "is_fork": repo_data.get("fork"), "last_commit_date": last_commit,
        "stars_count": repo_data.get("stargazers_count"), "watchers_count": repo_data.get("watchers_count"),
        "open_issues_count": repo_data.get("open_issues_count"), "repo_created_at": repo_data.get("created_at"),
        "repo_updated_at": repo_data.get("updated_at"),
        "license_name": repo_data.get("license", {}).get("name") if repo_data.get("license") else None,
    })

    # Fetch and parse serverless configuration files
    serverless_yaml_files = fetch_serverless_yaml(f"{owner}/{repo_name}")
    for sls_file_info in serverless_yaml_files: 
        parsed_sls_config = parse_serverless_yaml(sls_file_info["content"])
        if parsed_sls_config:
            metadata_result["serverless_config"].append({
                "path": sls_file_info["path"], "config": parsed_sls_config
            })
        else:
            logging.warning(f"Failed to parse serverless config for {sls_file_info['path']} in {owner}/{repo_name}")
    return metadata_result

def _paginated_github_api_call(url_str, headers_dict, item_extractor_func):
    """Generic helper for paginated GitHub API GET requests."""
    all_items = []
    next_page_url = url_str
    while next_page_url:
        try:
            response = requests.get(next_page_url, headers=headers_dict, timeout=15)
            check_rate_limit(response.headers)
            response.raise_for_status()
            
            page_content = response.json()
            if not page_content: break # No more items or empty page
            
            all_items.extend(item_extractor_func(page_content))
            next_page_url = response.links.get("next", {}).get("url")
        except requests.Timeout:
            logging.error(f"Timeout during paginated request to {next_page_url}.")
            break 
        except requests.HTTPError as e:
            # Specific handling for 204 No Content (e.g. for contributors if none)
            if e.response.status_code == 204:
                 logging.info(f"No content (204) for paginated request {next_page_url.split('?')[0]}.")
            else:
                logging.warning(f"HTTP error for {next_page_url.split('?')[0]}: {e.response.status_code} - {e.response.text}")
            break 
        except requests.RequestException as e:
            logging.error(f"Request exception for {next_page_url.split('?')[0]}: {e}")
            break
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON from {next_page_url.split('?')[0]}: {e}")
            break
    return all_items

def get_repo_languages(owner_str, repo_str):
    """Fetch repository language breakdown."""
    url = f"https://api.github.com/repos/{owner_str}/{repo_str}/languages"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        check_rate_limit(response.headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch languages for {owner_str}/{repo_str}: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON for languages of {owner_str}/{repo_str}: {e}")
    return {}

def get_repo_contributors(owner_str, repo_str):
    """Fetch repository contributors (logins)."""
    url = f"https://api.github.com/repos/{owner_str}/{repo_str}/contributors?per_page=100"
    return _paginated_github_api_call(url, HEADERS, lambda page: [c["login"] for c in page if c and "login" in c])

def get_repo_tags(owner_str, repo_str):
    """Fetch repository tags (names)."""
    url = f"https://api.github.com/repos/{owner_str}/{repo_str}/tags?per_page=100"
    return _paginated_github_api_call(url, HEADERS, lambda page: [t["name"] for t in page if t and "name" in t])

def check_security_feature(owner_str, repo_str, feature_name):
    """Check if a specific security feature is enabled."""
    url = f"https://api.github.com/repos/{owner_str}/{repo_str}/{feature_name}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        check_rate_limit(response.headers)
        
        if response.status_code == 200: # e.g., for private-vulnerability-reporting
            return response.json().get("enabled", False)
        elif response.status_code == 204: # e.g., for vulnerability-alerts if enabled
            return True 
        elif response.status_code == 404: # Feature not found or not enabled
            logging.debug(f"Security feature '{feature_name}' not enabled for {owner_str}/{repo_str} (404).")
            return False
        else: # Other statuses
            logging.warning(f"Status {response.status_code} for '{feature_name}' on {owner_str}/{repo_str}: {response.text}")
            return None # Unknown state
    except requests.RequestException as e:
        logging.error(f"Request exception for '{feature_name}' on {owner_str}/{repo_str}: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON for '{feature_name}' of {owner_str}/{repo_str}: {e}")
    return None

def get_last_commit_date(owner_str, repo_str):
    """Fetch the date of the last commit."""
    url = f"https://api.github.com/repos/{owner_str}/{repo_str}/commits"
    try:
        response = requests.get(url, headers=HEADERS, params={"per_page": 1}, timeout=15)
        check_rate_limit(response.headers)
        response.raise_for_status()
        commits = response.json()
        if commits and isinstance(commits, list) and len(commits) > 0:
            commit_details = commits[0].get("commit", {}).get("committer", {})
            return commit_details.get("date")
        else:
            logging.info(f"No commits found for {owner_str}/{repo_str}.")
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch last commit date for {owner_str}/{repo_str}: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON for last commit of {owner_str}/{repo_str}: {e}")
    return None

# Main processing loop
def main():
    logging.info(f"Starting metadata extraction from: {INPUT_FILENAME}")
    if not os.path.isfile(INPUT_FILENAME):
        logging.error(f"Input file not found: {INPUT_FILENAME}")
        return

    urls_to_process = []
    with open(INPUT_FILENAME, "r", encoding="utf-8") as f_in:
        urls_to_process = [line.strip() for line in f_in if line.strip()]
    
    total_urls = len(urls_to_process)
    logging.info(f"Found {total_urls} URLs to process.")
    processed_count = 0

    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as outfile:
        for i, repo_url in enumerate(urls_to_process):
            logging.info(f"Processing repository {i+1}/{total_urls}: {repo_url}")
            check_rate_limit() # Check before starting work on a new repo
            
            repo_meta = get_repo_metadata(repo_url)
            if repo_meta:
                try:
                    outfile.write(json.dumps(repo_meta) + "\n")
                    processed_count +=1
                except TypeError as e:
                    logging.error(f"JSON serialization error for {repo_url}: {e}. Data: {str(repo_meta)[:500]}")
            else:
                logging.warning(f"No metadata retrieved or error for {repo_url}. Skipping.")
            
            # time.sleep(0.2) # Small optional delay

    logging.info(f"Metadata extraction complete. Processed {processed_count}/{total_urls} URLs. Results: {OUTPUT_FILENAME}")

if __name__ == "__main__":
    main()
