import json
import os
import logging
import glob
import sys
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
OUTPUT_LATEX_FILE = os.path.join(PAPER_TABLES_DIR, "language_bytes.tex")
LOG_FILENAME = os.path.join(LOGS_DIR, "language_bytes_log.log")
TOP_N_LANGUAGES = 15
TABLE_CAPTION = 'Total code size (bytes) per language across projects'
TABLE_LABEL = 'tab:language-bytes'

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

def format_latex_number(n):
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)

def format_latex_percent(p):
    if p is None or isnan(p):
        return "N/A"
    try:
        return f"{p * 100:.2f}\\%"
    except (ValueError, TypeError):
        return "N/A"

def generate_language_latex_table(language_bytes_totals, total_bytes_all_langs, top_n=None, caption="Language Bytes", label="tab:lang-bytes"):
    latex_string = []
    latex_string.append(r'\begin{table}[htbp]')
    latex_string.append(r'    \centering')
    latex_string.append(f'    \\caption{{{caption}}}')
    latex_string.append(r'    \begin{tabular}{|l|r|r|}')
    latex_string.append(r'        \hline')
    latex_string.append(r'        \textbf{Language} & \textbf{Total Bytes} & \textbf{Occurrence (\%)} \\')
    latex_string.append(r'        \hline')
    sorted_items = language_bytes_totals.most_common(top_n)
    for language, count in sorted_items:
        percentage = count / total_bytes_all_langs if total_bytes_all_langs > 0 else 0
        formatted_language = language
        formatted_count = format_latex_number(count)
        formatted_percent = format_latex_percent(percentage)
        latex_string.append(f'        {formatted_language} & {formatted_count} & {formatted_percent} \\\\')
    latex_string.append(r'        \hline')
    latex_string.append(r'    \end{tabular}')
    latex_string.append(f'    \\label{{{label}}}')
    latex_string.append(r'\end{table}')
    return '\n'.join(latex_string)

# --- Main Counting Logic ---
lines_read = 0
records_processed = 0
errors_parsing = 0
language_bytes_counter = Counter()
total_bytes_overall = 0

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
                languages_bytes_dict = {}
                github_metadata = data.get('github_metadata')
                if isinstance(github_metadata, dict):
                    languages_bytes_dict = github_metadata.get('languages_bytes', {})
                    if not isinstance(languages_bytes_dict, dict):
                        logging.warning(f"Line {line_num}: 'languages_bytes' field is not a dict ({type(languages_bytes_dict)}). Skipping languages for this record.")
                        languages_bytes_dict = {}
                for lang, byte_count in languages_bytes_dict.items():
                    if isinstance(byte_count, (int, float)) and byte_count > 0:
                        language_bytes_counter[lang] += byte_count
                        total_bytes_overall += byte_count
                    else:
                        logging.debug(f"Line {line_num}: Invalid byte count '{byte_count}' for language '{lang}'. Skipping.")
            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors_parsing += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line. Error: {e}")
                errors_parsing += 1
            if lines_read % 5000 == 0:
                logging.info(f"Processed {lines_read} lines...")

    logging.info(f"Finished processing input file. Found {len(language_bytes_counter)} unique languages.")
    logging.info(f"Total bytes counted across all languages: {total_bytes_overall}")

    if not language_bytes_counter or total_bytes_overall == 0:
        logging.warning("No valid language byte counts found in the input file. Cannot generate table.")
    else:
        effective_caption = TABLE_CAPTION
        if TOP_N_LANGUAGES is not None and TOP_N_LANGUAGES < len(language_bytes_counter):
            effective_caption = f'Top {TOP_N_LANGUAGES} languages by total code size (bytes) across projects'
        elif TOP_N_LANGUAGES is None:
            effective_caption = 'Total code size (bytes) per language across projects'

        latex_output = generate_language_latex_table(
            language_bytes_counter,
            total_bytes_overall,
            top_n=TOP_N_LANGUAGES,
            caption=effective_caption,
            label=TABLE_LABEL
        )

        print("\n--- Generated Language Bytes LaTeX Table ---")
        print(latex_output)
        print("--- End Generated Language Bytes LaTeX Table ---\n")

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
    logging.info(f"Unique languages found: {len(language_bytes_counter)}")
    logging.info(f"Total bytes counted: {format_latex_number(total_bytes_overall)}")
    logging.info(f"Errors parsing lines: {errors_parsing}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")