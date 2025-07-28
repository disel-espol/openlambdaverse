import os
import json
import glob
import logging
import sys

# --- Configuration ---
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if not latest_dir:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

RESULTS_DIR = os.path.join(latest_dir, "results")
LOGS_DIR = os.path.join(latest_dir, "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

INPUT_FILENAME = os.path.join(RESULTS_DIR, "filtered_no_toy.jsonl")
OUTPUT_FILENAME = os.path.join(RESULTS_DIR, "aws_provider_repos.jsonl")
LOG_FILENAME = os.path.join(LOGS_DIR, "filter_by_provider_log.log")
TARGET_PROVIDER = "aws"

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

lines_read = 0
lines_written = 0
lines_filtered_provider = 0
errors = 0

logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Current Working Directory: {os.getcwd()}")
logging.info(f"Attempting to read from: {INPUT_FILENAME}")
logging.info(f"Attempting to write AWS-only repos to: {OUTPUT_FILENAME}")
logging.info(f"Attempting to write logs to: {LOG_FILENAME}")

try:
    if not os.path.isfile(INPUT_FILENAME):
        logging.error(f"Input file does not exist: {INPUT_FILENAME}")
        sys.exit(1)

    with open(INPUT_FILENAME, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(OUTPUT_FILENAME, 'w', encoding='utf-8') as outfile:

        logging.info(f"Successfully opened input file: {INPUT_FILENAME}")

        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1
            try:
                data = json.loads(line.strip())
                serverless_config = data.get('serverless_config')
                is_aws = False
                if isinstance(serverless_config, list):
                    for entry in serverless_config:
                        config = entry.get('config', {})
                        if config.get('provider_name') == TARGET_PROVIDER:
                            is_aws = True
                            break
                elif isinstance(serverless_config, dict):
                    # fallback for old format
                    if serverless_config.get('provider_name') == TARGET_PROVIDER:
                        is_aws = True

                if is_aws:
                    outfile.write(line)
                    lines_written += 1
                else:
                    lines_filtered_provider += 1
            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line. Error: {e}")
                errors += 1

            if lines_read % 1000 == 0:
                logging.info(f"Processed {lines_read} lines... Kept: {lines_written}, Filtered (Provider): {lines_filtered_provider}, Errors: {errors}")

except Exception as e:
    logging.exception(f"Critical error: {e}")
    sys.exit(1)
finally:
    logging.info("--- Filtering Summary ---")
    logging.info(f"Total lines read: {lines_read}")
    logging.info(f"Lines written (AWS provider): {lines_written}")
    logging.info(f"Lines filtered out (other/missing provider): {lines_filtered_provider}")
    logging.info(f"Lines skipped due to errors: {errors}")
    logging.info(f"Filtered data saved to: {OUTPUT_FILENAME}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")