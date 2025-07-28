import os
import json
import glob
import logging

TOY_KEYWORDS = [
    'example', 'tutorial', 'demo', 'sample', 'boilerplate', 'starter',
    'playground', 'hello-world', 'test', 'mock', 'poc', 'template',
    'learn', 'guide', 'workshop', 'exercise', 'skeleton'
]

def contains_toy_keyword(repo_data, keywords):
    repo_full_name = repo_data.get('repository', '').lower()
    metadata = repo_data.get('github_metadata', {})
    description = metadata.get('description', '').lower() if metadata.get('description') else ''
    topics = [topic.lower() for topic in metadata.get('topics', [])]
    if any(keyword in repo_full_name for keyword in keywords):
        return True
    if description and any(keyword in description for keyword in keywords):
        return True
    if topics and any(keyword in topic for topic in topics for keyword in keywords):
        return True
    if topics and any(topic in keywords for topic in topics):
        return True
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

INPUT_FILE = os.path.join(RESULTS_DIR, "filtered_no_inactive.jsonl")
OUTPUT_FILE = os.path.join(RESULTS_DIR, "filtered_no_toy.jsonl")
LOG_FILE = os.path.join(LOGS_DIR, "filter_toy_projects_log.log")

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
            if contains_toy_keyword(data, TOY_KEYWORDS):
                filtered += 1
            else:
                outfile.write(line)
                written += 1
        except Exception as e:
            logging.error(f"Error processing line {total}: {e}")

logging.info(f"Total: {total}, Filtered toy/example: {filtered}, Written: {written}")
logging.info(f"Output: {OUTPUT_FILE}")