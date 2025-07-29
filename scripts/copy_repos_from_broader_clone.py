import json
import os
import logging
import sys
import glob
import shutil # For directory copying
from dotenv import load_dotenv

# --- Load .env file for external SSD or custom clone location ---
load_dotenv()

# --- Configuration ---
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
#latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_20250424_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if not latest_dir:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

RESULTS_DIR = os.path.join(latest_dir, "results")
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "logs"))
os.makedirs(LOGS_DIR, exist_ok=True)

INPUT_JSONL_FILENAME = os.path.join(RESULTS_DIR, "aws_provider_repos.jsonl")
LOG_FILENAME = os.path.join(LOGS_DIR, "copy_repos_from_broader_clone.log")

DEFAULT_SOURCE_DIR_FALLBACK = "source_aws_repos"
DEFAULT_CLONE_DIR_FALLBACK = "cloned_aws_repos"
SOURCE_DIR = os.getenv("REPOS_SOURCE_DIRECTORY", DEFAULT_SOURCE_DIR_FALLBACK)
CLONE_DIR = os.getenv("CLONED_REPOS_DIRECTORY", DEFAULT_CLONE_DIR_FALLBACK)

# --- Calculate Absolute Paths ---
CURRENT_WORKING_DIR = os.getcwd()
INPUT_FILE = os.path.abspath(os.path.join(CURRENT_WORKING_DIR, INPUT_JSONL_FILENAME))
# Use absolute paths for source and target directories directly from config
SOURCE_REPO_DIR_ABS = os.path.abspath(SOURCE_DIR)
TARGET_REPO_DIR_ABS = os.path.abspath(CLONE_DIR)
LOG_FILE = os.path.abspath(os.path.join(CURRENT_WORKING_DIR, LOG_FILENAME))

# --- Logging Setup ---
# Remove existing handlers if any script runs this multiple times in one session
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def get_dir_size(start_path='.'):
    """Calculates the total size of a directory recursively."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(start_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                # Skip if it is symbolic link (optional)
                if not os.path.islink(fp):
                    try:
                        total_size += os.path.getsize(fp)
                    except OSError as e:
                        logging.error(f"Could not get size of file {fp}: {e}")
            # Add size of directories themselves (usually negligible, but for completeness)
            # total_size += os.path.getsize(dirpath) # Uncomment if needed, often not desired
    except OSError as e:
        logging.error(f"Could not walk directory {start_path} to calculate size: {e}")
        return -1 # Indicate error
    return total_size

def format_size(size_bytes):
    """Converts bytes to a human-readable format (KB, MB, GB)."""
    if size_bytes < 0:
        return "Error Calculating Size"
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.2f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/1024**2:.2f} MB"
    else:
        return f"{size_bytes/1024**3:.2f} GB"

# --- Main Copying Logic ---
lines_read = 0
repos_copied = 0
repos_skipped_missing_src = 0
repos_skipped_already_exists = 0
errors_copying = 0
errors_parsing = 0

# --- Log Initial Information ---
logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Current Working Directory: {CURRENT_WORKING_DIR}")
logging.info(f"Attempting to read repo list from: {INPUT_FILE}")
logging.info(f"Source repository directory: {SOURCE_REPO_DIR_ABS}")
logging.info(f"Target directory for copies: {TARGET_REPO_DIR_ABS}")
logging.info(f"Attempting to write logs to: {LOG_FILE}")

try:
    # --- Preparations ---
    # Check if source directory exists
    if not os.path.isdir(SOURCE_REPO_DIR_ABS):
        logging.error(f"Source repository directory not found: {SOURCE_REPO_DIR_ABS}")
        exit(1)

    # Create target directory if it doesn't exist
    try:
        os.makedirs(TARGET_REPO_DIR_ABS, exist_ok=True)
        logging.info(f"Ensured target directory exists: {TARGET_REPO_DIR_ABS}")
    except OSError as e:
        logging.error(f"Could not create target directory {TARGET_REPO_DIR_ABS}: {e}")
        exit(1)

    # Check if input file exists
    if not os.path.isfile(INPUT_FILE):
        logging.error(f"Input file check failed. File does not exist or is not a file at: {INPUT_FILE}")
        exit(1)

    # --- Process Input File and Copy Repos ---
    with open(INPUT_FILE, 'r', encoding='utf-8', errors='ignore') as infile:
        logging.info(f"Successfully opened input file: {INPUT_FILE}")

        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1

            try:
                # Attempt to parse the JSON line
                data = json.loads(line.strip())
                repo_full_name = data.get('repository')

                if not repo_full_name or '/' not in repo_full_name:
                    logging.warning(f"Line {line_num}: Invalid or missing 'repository' field. Skipping.")
                    errors_parsing += 1
                    continue

                # Construct source and destination paths
                repo_dir_name = repo_full_name.replace('/', '_')
                source_path = os.path.join(SOURCE_REPO_DIR_ABS, repo_dir_name)
                dest_path = os.path.join(TARGET_REPO_DIR_ABS, repo_dir_name)

                # Check if source repo directory exists
                if not os.path.isdir(source_path):
                    logging.warning(f"Line {line_num}: Source directory not found for repo '{repo_full_name}' at {source_path}. Skipping copy.")
                    repos_skipped_missing_src += 1
                    continue

                # Check if destination directory already exists (optional: skip if exists)
                if os.path.exists(dest_path):
                    logging.info(f"Line {line_num}: Destination directory already exists for repo '{repo_full_name}' at {dest_path}. Skipping copy.")
                    repos_skipped_already_exists += 1
                    continue # Skip copying if it's already there

                # --- Perform the copy ---
                try:
                    logging.info(f"Line {line_num}: Copying '{repo_full_name}' from {source_path} to {dest_path}...")
                    shutil.copytree(source_path, dest_path, symlinks=False, ignore_dangling_symlinks=True) # Avoid issues with symlinks if possible
                    repos_copied += 1
                    logging.debug(f"Line {line_num}: Successfully copied '{repo_full_name}'.")
                except shutil.Error as e:
                    logging.error(f"Line {line_num}: Error copying directory for '{repo_full_name}': {e}")
                    errors_copying += 1
                except OSError as e:
                    logging.error(f"Line {line_num}: OS error copying directory for '{repo_full_name}': {e}")
                    errors_copying += 1

            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors_parsing += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line. Error: {e}")
                errors_parsing += 1

            # Log progress periodically
            if lines_read % 100 == 0:
                logging.info(f"Processed {lines_read} lines... Copied: {repos_copied}, Skipped (Missing Src): {repos_skipped_missing_src}, Skipped (Exists): {repos_skipped_already_exists}, Errors: {errors_copying + errors_parsing}")

    # --- Calculate Final Size ---
    logging.info("Finished processing input file. Calculating size of target directory...")
    total_size_bytes = get_dir_size(TARGET_REPO_DIR_ABS)
    human_readable_size = format_size(total_size_bytes)
    logging.info(f"Total size of target directory '{TARGET_REPO_DIR_ABS}': {human_readable_size} ({total_size_bytes} bytes)")


except FileNotFoundError:
    # Should be caught by pre-checks, but handle defensively
    logging.error(f"Error: A required file or directory was not found.")
    exit(1)
except IOError as e:
    logging.error(f"IOError reading input file or accessing directories: {e}")
    exit(1)
except Exception as e:
    logging.exception(f"An unexpected critical error occurred: {e}")
    exit(1)
finally:
    # Final summary logging
    logging.info("--- Copying Summary ---")
    logging.info(f"Total lines read from input: {lines_read}")
    logging.info(f"Repositories successfully copied: {repos_copied}")
    logging.info(f"Repositories skipped (source dir missing): {repos_skipped_missing_src}")
    logging.info(f"Repositories skipped (already in target): {repos_skipped_already_exists}")
    logging.info(f"Errors during copying: {errors_copying}")
    logging.info(f"Errors parsing input lines: {errors_parsing}")
    logging.info(f"Target directory: {TARGET_REPO_DIR_ABS}")
    # Re-log size in summary
    total_size_bytes_final = get_dir_size(TARGET_REPO_DIR_ABS) # Recalculate in case of errors during run
    human_readable_size_final = format_size(total_size_bytes_final)
    logging.info(f"Final calculated size of target directory: {human_readable_size_final} ({total_size_bytes_final} bytes)")
    logging.info(f"Detailed logs saved to: {LOG_FILE}")

