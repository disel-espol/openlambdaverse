import os
import glob
import datetime
import logging
import sys

# --- Configuration ---
# Find the most recent code search directory
RAW_DATA_DIR = os.path.join(os.getcwd(), "data", "raw")
latest_dir_pattern = os.path.join(RAW_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if latest_dir:
    RESULTS_DIR = os.path.join(latest_dir, "results_by_filename")
    # Extract the timestamp from the latest directory name
    latest_timestamp = os.path.basename(latest_dir).replace("code_search_", "")
else:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found in the raw data directory.")

# Find the latest serverless.yml_results_YYYY-MM-DD.txt file in the results_by_filename directory
latest_file_pattern = os.path.join(RESULTS_DIR, "serverless.yml_results_*.txt")
INPUT_FILENAME = max(glob.glob(latest_file_pattern), key=os.path.getmtime, default=None)

if not INPUT_FILENAME:
    raise FileNotFoundError("No matching serverless.yml_results_YYYY-MM-DD.txt file found in the results_by_filename directory.")

# Define output and log directories using the latest directory's timestamp
OUTPUT_DIR = os.path.join(os.getcwd(), "data", "processed", f"code_search_{latest_timestamp}", "filtered_urls")
LOG_DIR = os.path.join(os.getcwd(), "data", "processed", f"code_search_{latest_timestamp}", "logs")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Define output and log file paths
OUTPUT_FILENAME = os.path.join(OUTPUT_DIR, "filtered_urls.txt")
LOG_FILENAME = os.path.join(LOG_DIR, "url_filter_log.log")

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

# --- Log Initial Information ---
logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Latest input file: {INPUT_FILENAME}")
logging.info(f"Filtered URLs will be saved to: {OUTPUT_FILENAME}")
logging.info(f"Logs will be saved to: {LOG_FILENAME}")

# Keywords/substrings to filter out (case-insensitive)
FILTERS = {
    "learn", "sample", "hello", "greeting", "template", "example",
    "test", "demo", "github.com/serverless", "starter", "basic",
    "course", "github.com/Azure", "github.com/aws"
}
# Ensure all filters are lowercase for case-insensitive comparison
FILTERS_LOWER = {f.lower() for f in FILTERS}

# --- Main Filtering Logic ---
lines_read = 0
lines_written = 0
lines_filtered = 0
errors = 0  # Count lines that couldn't be processed

try:
    # Check if input file exists before opening
    if not os.path.isfile(INPUT_FILENAME):
        logging.error(f"Input file check failed. File does not exist or is not a file at: {INPUT_FILENAME}")
        # Add a listing of the current directory contents for debugging
        try:
            dir_contents = os.listdir(RESULTS_DIR)
            logging.info(f"Contents of RESULTS_DIR ({RESULTS_DIR}): {dir_contents}")
        except Exception as list_e:
            logging.error(f"Could not list contents of RESULTS_DIR: {list_e}")
        exit(1)  # Exit if file doesn't exist

    # Open input and output files
    with open(INPUT_FILENAME, 'r', encoding='utf-8', errors='ignore') as infile, \
         open(OUTPUT_FILENAME, 'w', encoding='utf-8') as outfile:

        logging.info(f"Successfully opened input file: {INPUT_FILENAME}")  # Confirm opening

        # Process each line (URL) in the input file
        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1

            try:
                # Strip whitespace and check if the line is a URL or contains any filter keyword
                line = line.strip()
                if line.startswith("# Results for:"):
                    # Skip lines starting with "# Results for:"
                    continue
                if any(filter_word in line.lower() for filter_word in FILTERS_LOWER):
                    lines_filtered += 1
                    logging.debug(f"Filtered line {line_num}: {line}")
                elif line.startswith("http"):  # Only write valid URLs
                    outfile.write(line + '\n')
                    lines_written += 1
            except Exception as e:
                errors += 1
                logging.error(f"Error processing line {line_num}: {e}")

except FileNotFoundError:
    logging.error(f"File not found: {INPUT_FILENAME}")
except IOError as e:
    logging.error(f"I/O error occurred: {e}")
except Exception as e:
    logging.error(f"Unexpected error occurred: {e}")
finally:
    # Log summary of the filtering process
    logging.info(f"Lines read: {lines_read}")
    logging.info(f"Lines written: {lines_written}")
    logging.info(f"Lines filtered: {lines_filtered}")
    logging.info(f"Errors encountered: {errors}")
    logging.info("Script completed.")