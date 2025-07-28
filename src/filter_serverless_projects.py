import os
import glob
import logging
import sys

# --- Configuration ---
# Find the most recent code search directory in data/processed
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if latest_dir:
    UNIQUE_REPO_URLS_DIR = os.path.join(latest_dir, "unique_repo_urls")
    LOGS_DIR = os.path.join(latest_dir, "logs")
    FILTERED_REPO_URLS_DIR = os.path.join(latest_dir, "filtered_repo_urls")
    # Ensure the filtered_repo_urls directory exists
    os.makedirs(FILTERED_REPO_URLS_DIR, exist_ok=True)
else:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found in the processed data directory.")

# Define input, output, and log file paths
INPUT_FILENAME = os.path.join(UNIQUE_REPO_URLS_DIR, "unique_repo_urls.txt")
OUTPUT_FILENAME = os.path.join(FILTERED_REPO_URLS_DIR, "filtered_repo_urls.txt")
LOG_FILENAME = os.path.join(LOGS_DIR, "filter_serverless_repos_log.log")

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

# --- Main Filtering Logic ---
lines_read = 0
lines_written = 0
errors = 0

# Users to filter out
FILTER_USERS = {"serverless", "serverless-components"}

# --- Log Initial Information ---
logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Attempting to read unique repo URLs from: {INPUT_FILENAME}")
logging.info(f"Attempting to write filtered repo URLs to: {OUTPUT_FILENAME}")
logging.info(f"Attempting to write logs to: {LOG_FILENAME}")

try:
    # Check if input file exists before opening
    if not os.path.isfile(INPUT_FILENAME):
        logging.error(f"Input file check failed. File does not exist or is not a file at: {INPUT_FILENAME}")
        exit(1)  # Exit if file doesn't exist

    # Open input and output files
    with open(INPUT_FILENAME, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(OUTPUT_FILENAME, 'w', encoding='utf-8') as outfile:

        logging.info(f"Successfully opened input file: {INPUT_FILENAME}")

        # Process each line (URL) in the input file
        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1

            try:
                # Get the original URL, removing leading/trailing whitespace
                full_url = line.strip()

                # Skip empty lines
                if not full_url:
                    logging.debug(f"Line {line_num}: Skipping empty line.")
                    continue

                # Extract the owner from the URL
                owner = full_url.split("/")[3]  # Assuming URL format: https://github.com/owner/repo

                # Check if the owner is in the filter list
                if owner in FILTER_USERS:
                    logging.debug(f"Line {line_num}: Skipping repo owned by '{owner}': {full_url}")
                    continue

                # Write the URL to the output file
                outfile.write(full_url + '\n')
                lines_written += 1

            except Exception as e:
                # Catch potential errors during line processing
                logging.exception(f"Line {line_num}: Unexpected error processing line. URL: '{line.strip()}'. Error: {e}")
                errors += 1

    logging.info(f"Finished filtering. Total lines read: {lines_read}, lines written: {lines_written}, errors: {errors}")

except FileNotFoundError:
    logging.error(f"Error: Input file not found at the path calculated: '{INPUT_FILENAME}'")
    exit(1)
except IOError as e:
    logging.error(f"IOError reading input file {INPUT_FILENAME}: {e}")
    exit(1)
except Exception as e:
    logging.exception(f"An unexpected critical error occurred during processing: {e}")
    exit(1)
finally:
    # Final summary logging
    logging.info("--- Filtering Summary ---")
    logging.info(f"Total lines read from input: {lines_read}")
    logging.info(f"Total lines written to output: {lines_written}")
    logging.info(f"Total errors encountered: {errors}")
    logging.info(f"Filtered repo URLs saved to: {OUTPUT_FILENAME}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")