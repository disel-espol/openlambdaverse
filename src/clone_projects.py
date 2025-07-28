import os
import json
import logging
import subprocess
import glob
import sys
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# --- Load .env file for external SSD or custom clone location ---
load_dotenv()
DEFAULT_CLONE_DIR_FALLBACK = "cloned_aws_repos"
CLONE_DIR = os.getenv("CLONED_REPOS_DIRECTORY", DEFAULT_CLONE_DIR_FALLBACK)

# --- Configuration for input/output ---
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if not latest_dir:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

RESULTS_DIR = os.path.join(latest_dir, "results")
LOGS_DIR = os.path.join(latest_dir, "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
INPUT_FILENAME = os.path.join(RESULTS_DIR, "aws_provider_repos.jsonl")
LOG_FILENAME = os.path.join(LOGS_DIR, "clone_aws_repos.log")

os.makedirs(CLONE_DIR, exist_ok=True)

# --- Logging Setup ---
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
logger = logging.getLogger("CloneProjects")

def get_repo_path_from_url(repo_url, base_dir):
    """Generates a safe local path for a repository URL."""
    parsed_url = urlparse(repo_url)
    path_part = parsed_url.path.strip("/")
    parts = path_part.split("/")
    if len(parts) >= 2:
        owner, repo = parts[-2], parts[-1]
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        safe_owner = "".join(c if c.isalnum() or c in "-_" else "_" for c in owner)
        safe_repo = "".join(c if c.isalnum() or c in "-_" else "_" for c in repo)
        return os.path.join(base_dir, f"{safe_owner}_{safe_repo}")
    else:
        # fallback for malformed URLs
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in path_part)
        return os.path.join(base_dir, f"unknown_{safe_name}")

def clone_repo(repo_url, target_dir):
    dest_path = get_repo_path_from_url(repo_url, target_dir)
    if os.path.exists(dest_path):
        logger.info(f"Repo already exists, skipping: {dest_path}")
        return "skipped", dest_path
    try:
        logger.info(f"Cloning {repo_url} into {dest_path}")
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, dest_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.debug(result.stdout.decode().strip())
        return "cloned", dest_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone {repo_url}: {e.stderr.decode().strip()}")
        return "failed", dest_path

def main():
    repos_cloned = 0
    repos_skipped = 0
    repos_failed = 0
    processed = 0

    if not os.path.isfile(INPUT_FILENAME):
        logger.error(f"Input file does not exist: {INPUT_FILENAME}")
        sys.exit(1)

    with open(INPUT_FILENAME, "r", encoding="utf-8") as infile:
        for line in infile:
            processed += 1
            try:
                data = json.loads(line)
                repo_url = data.get("url")
                if repo_url:
                    status, path = clone_repo(repo_url, CLONE_DIR)
                    if status == "cloned":
                        repos_cloned += 1
                    elif status == "skipped":
                        repos_skipped += 1
                    else:
                        repos_failed += 1
                else:
                    repos_skipped += 1
                    logger.warning(f"No URL found in line: {line.strip()[:100]}")
            except Exception as e:
                repos_failed += 1
                logger.error(f"Error processing line: {e}")

    logger.info(f"Cloning complete. Processed: {processed}, Cloned: {repos_cloned}, Skipped: {repos_skipped}, Failed: {repos_failed}")

if __name__ == "__main__":
    main()