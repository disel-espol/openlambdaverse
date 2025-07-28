import os
import glob
import json
import logging
import sys

# --- Configuration ---
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if latest_dir:
    LOGS_DIR = os.path.join(latest_dir, "logs")
    RESULTS_DIR = os.path.join(latest_dir, "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
else:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

INPUT_FILENAME = os.path.join(RESULTS_DIR, "repository_metadata.jsonl")
OUTPUT_FILENAME = os.path.join(RESULTS_DIR, "licensed_repos.jsonl")
LOG_FILENAME = os.path.join(LOGS_DIR, "filter_unlicensed_repos_log.log")

# --- Logging Setup ---
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILENAME, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def is_repo_licensed(repo_data):
    """Return True if the repo has a non-empty license_name field."""
    license_name = repo_data.get('license_name')
    if license_name and isinstance(license_name, str) and license_name.strip().lower() not in ('no license', 'none', 'unlicensed'):
        return True
    return False

def filter_licensed_repos(input_path, output_path):
    lines_read = 0
    lines_written = 0
    lines_filtered = 0
    errors = 0

    logging.info(f"Filtering licensed repos from: {input_path}")
    if not os.path.isfile(input_path):
        logging.error(f"Input file does not exist: {input_path}")
        sys.exit(1)

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:
        for i, line in enumerate(infile, 1):
            lines_read += 1
            try:
                data = json.loads(line)
                if is_repo_licensed(data):
                    outfile.write(line)
                    lines_written += 1
                else:
                    lines_filtered += 1
            except Exception as e:
                logging.error(f"Line {i}: Error processing line: {e} | Content: {line[:100]}")
                errors += 1

            if lines_read % 1000 == 0:
                logging.info(f"Processed {lines_read} lines... Kept: {lines_written}, Filtered: {lines_filtered}, Errors: {errors}")

    logging.info("--- Filtering Summary ---")
    logging.info(f"Total lines read: {lines_read}")
    logging.info(f"Lines written (licensed repos): {lines_written}")
    logging.info(f"Lines filtered out (no license): {lines_filtered}")
    logging.info(f"Lines skipped due to errors: {errors}")
    logging.info(f"Filtered data saved to: {output_path}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")

if __name__ == "__main__":
    filter_licensed_repos(INPUT_FILENAME, OUTPUT_FILENAME)