import json
import os
import logging
import glob
import sys
import re
from collections import Counter
from math import isnan

# --- Configuration ---
PROCESSED_DATA_DIR = os.path.join(os.getcwd(), "data", "processed")
#latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_*")
latest_dir_pattern = os.path.join(PROCESSED_DATA_DIR, "code_search_20250424_*")
latest_dir = max(glob.glob(latest_dir_pattern), key=os.path.getmtime, default=None)

if not latest_dir:
    raise FileNotFoundError("No matching code_search_YYYYMMDD_hhmmss directory found.")

RESULTS_DIR = os.path.join(latest_dir, "results")
PAPER_TABLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../paper/tables"))
LOGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "logs"))
os.makedirs(PAPER_TABLES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

INPUT_FILENAME = os.path.join(RESULTS_DIR, "aws_provider_repos.jsonl")
OUTPUT_LATEX_FILE = os.path.join(PAPER_TABLES_DIR, "runtime_counts.tex")
LOG_FILENAME = os.path.join(LOGS_DIR, "runtime_counter_log.log")
RUNTIME_GROUP_REGEX = re.compile(r"^[a-zA-Z]+")
RUNTIME_IGNORE_MAP = {"Not Specified": None, "other": None}
TABLE_CAPTION = 'Runtimes used in the projects of the dataset'
TABLE_LABEL = 'tab:merged-runtime-stats'

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

def get_base_runtime(runtime_str):
    """Extracts a base runtime name (e.g., 'nodejs', 'python')."""
    if not isinstance(runtime_str, str):
        return None
    runtime_str = runtime_str.strip()
    if runtime_str in RUNTIME_IGNORE_MAP:
        return RUNTIME_IGNORE_MAP[runtime_str]
    match = RUNTIME_GROUP_REGEX.match(runtime_str)
    if match:
        return match.group(0).lower()
    return runtime_str.lower() if runtime_str else None

def format_latex_number(n):
    try:
        return f"{n:,}"
    except (ValueError, TypeError):
        return str(n)

def format_latex_percent(p):
    if p is None or isnan(p):
        return "N/A"
    try:
        return f"{p * 100:.3f}\\%"
    except (ValueError, TypeError):
        return "N/A"

def generate_runtime_latex_table(runtime_counts, total_count, caption="Runtime Counts", label="tab:runtimes"):
    latex_string = []
    latex_string.append(r'\begin{table}[htbp]')
    latex_string.append(r'    \centering')
    latex_string.append(f'    \\caption{{{caption}}}')
    latex_string.append(r'    \begin{tabular}{|l|r|r|}')
    latex_string.append(r'        \hline')
    latex_string.append(r'        \textbf{Runtime} & \textbf{Count} & \textbf{Occurrence} \\')
    latex_string.append(r'        \hline')
    sorted_items = runtime_counts.most_common()
    for runtime, count in sorted_items:
        percentage = count / total_count if total_count > 0 else 0
        formatted_runtime = runtime.capitalize()
        formatted_count = format_latex_number(count)
        formatted_percent = format_latex_percent(percentage)
        latex_string.append(f'        {formatted_runtime} & {formatted_count} & {formatted_percent} \\\\')
    latex_string.append(r'        \hline')
    latex_string.append(r'    \end{tabular}')
    latex_string.append(f'    \\label{{{label}}}')
    latex_string.append(r'\end{table}')
    return '\n'.join(latex_string)

# --- Main Counting Logic ---
lines_read = 0
records_processed = 0
errors_parsing = 0
runtime_counter = Counter()
total_runtime_entries = 0

logging.info(f"Script started: {' '.join(sys.argv)}")
logging.info(f"Current Working Directory: {os.getcwd()}")
logging.info(f"Attempting to read from: {INPUT_FILENAME}")
logging.info(f"Attempting to write logs to: {LOG_FILENAME}")

try:
    if not os.path.isfile(INPUT_FILENAME):
        logging.error(f"Input file check failed. File does not exist or is not a file at: {INPUT_FILENAME}")
        exit(1)

    with open(INPUT_FILENAME, 'r', encoding='utf-8', errors='ignore') as infile:
        logging.info(f"Successfully opened input file: {INPUT_FILENAME}")
        for i, line in enumerate(infile):
            lines_read += 1
            line_num = i + 1
            try:
                data = json.loads(line.strip())
                records_processed += 1
                runtimes_list = []
                serverless_config = data.get('serverless_config')
                # Handle both list and dict formats
                if isinstance(serverless_config, list):
                    for entry in serverless_config:
                        config = entry.get('config', {})
                        runtimes = config.get('runtimes', [])
                        if isinstance(runtimes, list):
                            runtimes_list.extend(runtimes)
                        elif runtimes:
                            logging.warning(f"Line {line_num}: 'runtimes' field is not a list ({type(runtimes)}). Skipping runtimes for this entry.")
                elif isinstance(serverless_config, dict):
                    runtimes = serverless_config.get('runtimes', [])
                    if isinstance(runtimes, list):
                        runtimes_list.extend(runtimes)
                    elif runtimes:
                        logging.warning(f"Line {line_num}: 'runtimes' field is not a list ({type(runtimes)}). Skipping runtimes for this record.")
                processed_runtimes_for_record = set()
                for rt in runtimes_list:
                    base_runtime = get_base_runtime(rt)
                    if base_runtime and base_runtime not in processed_runtimes_for_record:
                        runtime_counter[base_runtime] += 1
                        total_runtime_entries += 1
                        processed_runtimes_for_record.add(base_runtime)
                        logging.debug(f"Line {line_num}: Found runtime '{rt}', grouped as '{base_runtime}'.")
            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors_parsing += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line. Error: {e}")
                errors_parsing += 1
            if lines_read % 5000 == 0:
                logging.info(f"Processed {lines_read} lines...")

    logging.info(f"Finished processing input file. Found {len(runtime_counter)} unique base runtimes.")
    logging.info(f"Total runtime entries counted: {total_runtime_entries}")

    if not runtime_counter or total_runtime_entries == 0:
        logging.warning("No valid runtimes found in the input file. Cannot generate table.")
    else:
        latex_output = generate_runtime_latex_table(runtime_counter, total_runtime_entries, caption=TABLE_CAPTION, label=TABLE_LABEL)
        print("\n--- Generated Runtime LaTeX Table ---")
        print(latex_output)
        print("--- End Generated Runtime LaTeX Table ---\n")
        try:
            with open(OUTPUT_LATEX_FILE, 'w', encoding='utf-8') as outfile:
                outfile.write(latex_output)
            logging.info(f"LaTeX table also saved to: {OUTPUT_LATEX_FILE}")
        except IOError as e:
            logging.error(f"Could not write LaTeX output to file {OUTPUT_LATEX_FILE}: {e}")

except FileNotFoundError:
    logging.error(f"Error: Input file not found at the path calculated: '{INPUT_FILENAME}'")
    exit(1)
except IOError as e:
    logging.error(f"IOError reading input file: {e}")
    exit(1)
except Exception as e:
    logging.exception(f"An unexpected critical error occurred: {e}")
    exit(1)
finally:
    logging.info("--- Processing Summary ---")
    logging.info(f"Total lines read: {lines_read}")
    logging.info(f"JSON records successfully processed: {records_processed}")
    logging.info(f"Unique base runtimes found: {len(runtime_counter)}")
    logging.info(f"Total runtime entries counted: {total_runtime_entries}")
    logging.info(f"Errors parsing lines: {errors_parsing}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")