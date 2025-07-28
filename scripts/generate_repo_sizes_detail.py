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

INPUT_JSONL_FILENAME = os.path.join(RESULTS_DIR, "aws_provider_repos.jsonl") # Replace with your input JSONL file path
OUTPUT_CSV_FILENAME = 'csvs/repo_sizes_detail.csv'    # Replace with your desired output CSV file path
LOG_FILENAME = os.path.join(LOGS_DIR, "repo_sizes_detail_extractor_log.log")

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
        csv_writer = csv.writer(outfile)
        header = ['project_id', 'size']
        csv_writer.writerow(header)
        logging.info(f"Written CSV header: {header}")

        # Process each line in the JSONL file
        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1
            project_id = None
            size_kb = None

            try:
                # Attempt to parse the JSON line
                data = json.loads(line.strip())

                # Extract project_id (repository)
                project_id = data.get('repository')
                if not project_id or '/' not in project_id:
                    logging.warning(f"Line {line_num}: Invalid or missing 'repository' field. Skipping record.")
                    errors_missing_data += 1
                    continue # Skip to next line if repository is invalid

                # Safely extract size_kb from nested structure
                github_metadata = data.get('github_metadata')
                if isinstance(github_metadata, dict):
                    size_kb = github_metadata.get('size_kb')
                else:
                    logging.warning(f"Line {line_num}: Missing or invalid 'github_metadata' for repo '{project_id}'. Skipping size.")
                    errors_missing_data += 1
                    continue # Skip if metadata is missing/wrong type

                # Check if size_kb was found and is a number
                if size_kb is None:
                    logging.warning(f"Line {line_num}: Missing 'size_kb' within 'github_metadata' for repo '{project_id}'. Skipping record.")
                    errors_missing_data += 1
                    continue # Skip if size_kb is None
                elif not isinstance(size_kb, (int, float)):
                     logging.warning(f"Line {line_num}: Invalid 'size_kb' value ({size_kb}) for repo '{project_id}'. Skipping record.")
                     errors_missing_data += 1
                     continue # Skip if size_kb is not a number

                # Write the extracted data to the CSV file
                csv_writer.writerow([project_id, size_kb])
                rows_written += 1
                logging.debug(f"Line {line_num}: Wrote row: [{project_id}, {size_kb}]")

            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors_parsing += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line. Error: {e}")
                errors_parsing += 1

            # Log progress periodically
            if lines_read % 1000 == 0:
                logging.info(f"Processed {lines_read} lines... Rows written: {rows_written}, Missing Data: {errors_missing_data}, Errors: {errors_parsing}")

except FileNotFoundError:
    # Should be caught by pre-checks, but handle defensively
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
    logging.info(f"Records skipped due to missing/invalid data: {errors_missing_data}")
    logging.info(f"Errors parsing JSON lines: {errors_parsing}")
    logging.info(f"CSV output saved to: {OUTPUT_FILE_PATH}")
    logging.info(f"Detailed logs saved to: {LOG_FILE}")

