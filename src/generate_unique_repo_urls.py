import os
import glob
import logging
import sys
from urllib.parse import urlparse  # Use urlparse for more robust URL handling

# Find the most recent code search directory in data/processed
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if latest_dir:
    FILTERED_URLS_DIR = os.path.join(latest_dir, "filtered_urls")
    LOGS_DIR = os.path.join(latest_dir, "logs")
    UNIQUE_REPO_URLS_DIR = os.path.join(latest_dir, "unique_repo_urls")
    # Ensure the unique_repo_urls directory exists
    os.makedirs(UNIQUE_REPO_URLS_DIR, exist_ok=True)
else:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found in the processed data directory.")

# Define input, output, and log file paths
INPUT_FILENAME = os.path.join(FILTERED_URLS_DIR, "filtered_urls.txt")
OUTPUT_FILENAME = os.path.join(UNIQUE_REPO_URLS_DIR, "unique_repo_urls.txt")
LOG_FILENAME = os.path.join(LOGS_DIR, "base_url_extractor_log.log")

# Logging setup
# Remove existing handlers if any script runs this multiple times in one session
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

# Generate unique base repository URLs from filtered URLs
lines_read = 0
urls_extracted = 0
errors = 0
unique_repo_urls = set()  # Use a set to automatically store unique URLs

# Log initial information
logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Attempting to read filtered URLs from: {INPUT_FILENAME}")
logging.info(f"Attempting to write unique base repo URLs to: {OUTPUT_FILENAME}")
logging.info(f"Attempting to write logs to: {LOG_FILENAME}")

try:
    # Check if input file exists before opening
    if not os.path.isfile(INPUT_FILENAME):
        logging.error(f"Input file check failed. File does not exist or is not a file at: {INPUT_FILENAME}")
        exit(1)  # Exit if file doesn't exist

    # Open input file
    with open(INPUT_FILENAME, 'r', encoding='utf-8', errors='ignore') as infile:
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

                # Parse the URL
                parsed_url = urlparse(full_url)

                # Check if it's a github.com URL
                if parsed_url.netloc.lower() != 'github.com':
                    logging.warning(f"Line {line_num}: Skipping non-GitHub URL: {full_url}")
                    errors += 1
                    continue

                # Split the path part to get owner and repo
                # Path looks like: /owner/repo/blob/hash/path/to/file.yml
                path_parts = parsed_url.path.strip('/').split('/')

                # Ensure we have at least owner and repo in the path
                if len(path_parts) >= 2:
                    owner = path_parts[0]
                    repo = path_parts[1]
                    # Construct the base repository URL
                    base_repo_url = f"https://github.com/{owner}/{repo}"
                    # Add to set (duplicates are automatically handled)
                    if base_repo_url not in unique_repo_urls:
                        unique_repo_urls.add(base_repo_url)
                        urls_extracted += 1  # Count unique URLs added
                        logging.debug(f"Line {line_num}: Extracted base URL: {base_repo_url}")
                    else:
                        logging.debug(f"Line {line_num}: Duplicate base URL found: {base_repo_url}")
                else:
                    logging.warning(f"Line {line_num}: Could not extract owner/repo from path in URL: {full_url}")
                    errors += 1

            except Exception as e:
                # Catch potential errors during line processing or URL parsing
                logging.exception(f"Line {line_num}: Unexpected error processing line. URL: '{line.strip()}'. Error: {e}")
                errors += 1

            # Log progress periodically
            if lines_read % 1000 == 0:
                logging.info(f"Processed {lines_read} lines... Unique URLs extracted: {urls_extracted}, Errors/Skipped: {errors}")

    # After processing all lines, write the unique URLs to the output file
    logging.info(f"Finished reading input. Found {len(unique_repo_urls)} unique base repository URLs.")
    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as outfile:
            # Sort the URLs before writing for consistent output (optional)
            sorted_urls = sorted(list(unique_repo_urls))
            for url in sorted_urls:
                outfile.write(url + '\n')
            logging.info(f"Successfully wrote {len(sorted_urls)} unique URLs to {OUTPUT_FILENAME}")
    except IOError as e:
        logging.error(f"Error writing unique URLs to output file {OUTPUT_FILENAME}: {e}")
        exit(1)

# Handle FileNotFoundError specifically during the input open() call
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
    logging.info(f"Total lines read from input: {lines_read}")
    logging.info(f"Unique base repository URLs extracted: {len(unique_repo_urls)}")
    logging.info(f"Lines skipped due to errors or non-GitHub URLs: {errors}")
    logging.info(f"Unique base URLs saved to: {OUTPUT_FILENAME}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")