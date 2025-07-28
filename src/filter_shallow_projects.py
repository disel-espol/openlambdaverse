import os
import json
import glob
import logging

MIN_SIZE_KB = 100

PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)
if not latest_dir:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

RESULTS_DIR = os.path.join(latest_dir, "results")
LOGS_DIR = os.path.join(latest_dir, "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

INPUT_FILE = os.path.join(RESULTS_DIR, "filtered_no_forks.jsonl")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "filtered_no_shallow.jsonl")
LOG_FILE = os.path.join(LOGS_DIR, "filter_shallow_projects_log.log")

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()]
)

total, filtered, written = 0, 0, 0
with open(INPUT_FILE, 'r', encoding='utf-8') as infile, open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
    for line in infile:
        total += 1
        try:
            data = json.loads(line)
            size_kb = data.get('github_metadata', {}).get('size_kb')
            if isinstance(size_kb, (int, float)) and size_kb < MIN_SIZE_KB:
                filtered += 1
            else:
                outfile.write(line)
                written += 1
        except Exception as e:
            logging.error(f"Error processing line {total}: {e}")

logging.info(f"Total: {total}, Filtered shallow (<{MIN_SIZE_KB}KB): {filtered}, Written: {written}")
logging.info(f"Output: {OUTPUT_FILE}")