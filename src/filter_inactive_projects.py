import os
import json
import glob
import logging
from datetime import datetime, timedelta, timezone

INACTIVITY_MONTHS = 24

def is_inactive(last_commit_str, months_threshold):
    if not last_commit_str:
        return False
    try:
        last_commit_dt = datetime.fromisoformat(last_commit_str.replace('Z', '+00:00'))
        if last_commit_dt.tzinfo is None:
            last_commit_dt = last_commit_dt.replace(tzinfo=timezone.utc)
        now_utc = datetime.now(timezone.utc)
        threshold_date = now_utc - timedelta(days=months_threshold * 30.44)
        return last_commit_dt < threshold_date
    except Exception:
        return False

PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)
if not latest_dir:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

RESULTS_DIR = os.path.join(latest_dir, "results")
LOGS_DIR = os.path.join(latest_dir, "logs")
os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

INPUT_FILE = os.path.join(RESULTS_DIR, "filtered_no_shallow.jsonl")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "filtered_no_inactive.jsonl")
LOG_FILE = os.path.join(LOGS_DIR, "filter_inactive_projects_log.log")

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
            last_commit_date = data.get('last_commit_date')
            if is_inactive(last_commit_date, INACTIVITY_MONTHS):
                filtered += 1
            else:
                outfile.write(line)
                written += 1
        except Exception as e:
            logging.error(f"Error processing line {total}: {e}")

logging.info(f"Total: {total}, Filtered inactive (> {INACTIVITY_MONTHS} months): {filtered}, Written: {written}")
logging.info(f"Output: {OUTPUT_FILE}")