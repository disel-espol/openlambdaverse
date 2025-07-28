import json
import csv
import os
import logging
import glob
import sys

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
OUTPUT_CSV_FILENAME = 'csvs/repo_metadata.csv' # Replace with your desired output CSV file path
LOG_FILENAME = os.path.join(LOGS_DIR, "repo_metadata_extractor_log.log")

# --- Calculate Absolute Paths ---
CURRENT_WORKING_DIR = os.getcwd()
INPUT_FILE = os.path.abspath(os.path.join(CURRENT_WORKING_DIR, INPUT_JSONL_FILENAME))
OUTPUT_FILE_PATH = os.path.abspath(os.path.join(CURRENT_WORKING_DIR, OUTPUT_CSV_FILENAME))
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

# --- Main Logic ---
lines_read = 0
rows_written = 0
errors_parsing = 0
errors_missing_data = 0

# --- Log Initial Information ---
logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Current Working Directory: {CURRENT_WORKING_DIR}")
logging.info(f"Reading JSONL data from: {INPUT_FILE}")
logging.info(f"Writing CSV output to: {OUTPUT_FILE_PATH}")
logging.info(f"Log file: {LOG_FILE}")

try:
    # --- Preparations ---
    # Check if input file exists
    if not os.path.isfile(INPUT_FILE):
        logging.error(f"Input JSONL file not found: {INPUT_FILE}")
        exit(1)

    # --- Process JSONL File and Write CSV ---
    with open(INPUT_FILE, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(OUTPUT_FILE_PATH, 'w', newline='', encoding='utf-8') as outfile:

        logging.info(f"Successfully opened input file: {INPUT_FILE}")
        logging.info(f"Successfully opened output file: {OUTPUT_FILE_PATH}")

        # Create CSV writer and write header
        # project_id,watchers_count,forks_count,stargazers_count,open_issues_count,contributor_count
        header = [
            'project_id',
            'watchers_count',
            'forks_count',
            'stargazers_count', # Output column name
            'open_issues_count',
            'contributor_count'
        ]
        csv_writer = csv.writer(outfile)
        csv_writer.writerow(header)
        logging.info(f"Written CSV header: {header}")

        # Process each line in the JSONL file
        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1
            project_id = None
            watchers_count = None
            forks_count = None # From github_metadata.forks
            stars_count = None   # From top-level stars_count, output as stargazers_count
            open_issues_count = None
            contributor_count = None # From github_metadata.contributor_count

            try:
                # Attempt to parse the JSON line
                data = json.loads(line.strip())

                # Extract project_id (repository)
                project_id = data.get('repository')
                if not project_id or '/' not in project_id:
                    logging.warning(f"Line {line_num}: Invalid or missing 'repository' field. Skipping record.")
                    errors_missing_data += 1
                    continue

                # Extract top-level counts
                watchers_count = data.get('watchers_count')
                stars_count = data.get('stars_count') # This will be stargazers_count in output
                open_issues_count = data.get('open_issues_count')

                # Safely extract from nested 'github_metadata'
                github_metadata = data.get('github_metadata')
                if isinstance(github_metadata, dict):
                    forks_count = github_metadata.get('forks') # User wants this as forks_count
                    contributor_count = github_metadata.get('contributor_count')
                else:
                    logging.warning(f"Line {line_num}: Missing or invalid 'github_metadata' for repo '{project_id}'. Some fields might be empty.")
                    # Allow to proceed, missing fields will be None

                # Validate that essential counts are numbers or can be treated as 0 if None
                # For CSV output, None will become an empty string, which is fine.
                # If a specific default (like 0) is needed for missing numeric values,
                # it can be added here. e.g., watchers_count = watchers_count if watchers_count is not None else 0

                # Write the extracted data to the CSV file
                csv_writer.writerow([
                    project_id,
                    watchers_count,
                    forks_count,
                    stars_count, # Using stars_count from JSON for stargazers_count column
                    open_issues_count,
                    contributor_count
                ])
                rows_written += 1
                logging.debug(f"Line {line_num}: Wrote row for '{project_id}'")

            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors_parsing += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line for '{project_id if project_id else 'UnknownRepo'}'. Error: {e}")
                errors_parsing += 1 # Count as parsing error for simplicity

            # Log progress periodically
            if lines_read % 1000 == 0:
                logging.info(f"Processed {lines_read} lines... Rows written: {rows_written}, Missing Data/Key Errors: {errors_missing_data}, Parsing/Other Errors: {errors_parsing}")

except FileNotFoundError:
    logging.error(f"Error: Input file not found.")
    exit(1)
except IOError as e:
    logging.error(f"IOError reading input or writing output file: {e}")
    exit(1)
except Exception as e:
    logging.exception(f"An unexpected critical error occurred: {e}")
    exit(1)
finally:
    # Final summary logging
    logging.info("--- CSV Generation Summary ---")
    logging.info(f"Total lines read from JSONL: {lines_read}")
    logging.info(f"Rows successfully written to CSV: {rows_written}")
    logging.info(f"Records skipped due to missing/invalid repository ID or critical data: {errors_missing_data}")
    logging.info(f"Errors parsing JSON lines or other processing errors: {errors_parsing}")
    logging.info(f"CSV output saved to: {OUTPUT_FILE_PATH}")
    logging.info(f"Detailed logs saved to: {LOG_FILE}")

