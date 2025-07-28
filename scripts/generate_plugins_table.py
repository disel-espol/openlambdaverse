import json
import os
import logging
import glob
import sys
from collections import Counter

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
OUTPUT_LATEX_FILE = os.path.join(PAPER_TABLES_DIR, "plugin_counts.tex")
LOG_FILENAME = os.path.join(LOGS_DIR, "plugin_counter_log.log")
TOP_N_PLUGINS = None
TABLE_CAPTION = 'Top Serverless Framework plugins used in our dataset.'
TABLE_LABEL = 'table:plugin_counts'

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

def escape_latex(text):
    """Basic escaping for special LaTeX characters."""
    return (text.replace('_', r'\_')
                .replace('#', r'\#')
                .replace('%', r'\%')
                .replace('&', r'\&')
                .replace('$', r'\$')
                .replace('{', r'\{')
                .replace('}', r'\}')
                .replace('~', r'\textasciitilde{}')
                .replace('^', r'\textasciicircum{}'))

def generate_latex_table(plugin_counts, top_n=None, caption="Plugin Counts", label="table:plugins"):
    latex_string = []
    latex_string.append(r'\begin{table}[htbp]')
    latex_string.append(r'    \centering')
    latex_string.append(r'    \begin{tabular}{|p{5cm}|p{2cm}|}')
    latex_string.append(r'        \hline')
    latex_string.append(r'        Plugin & Count \\ [0.5ex]')
    latex_string.append(r'        \hline\hline')
    sorted_items = plugin_counts.most_common(top_n)
    num_items = len(sorted_items)
    for i, (plugin, count) in enumerate(sorted_items):
        escaped_plugin = r'\texttt{' + escape_latex(plugin) + '}'
        extra_space = r' \\[1ex]' if i == num_items - 1 and num_items > 0 else r''
        latex_string.append(f'        {escaped_plugin} & {count}{extra_space}')
        if i < num_items - 1:
            latex_string.append(r'        \hline')
    if num_items > 0:
        latex_string.append(r'        \hline')
    latex_string.append(r'    \end{tabular}')
    latex_string.append(f'    \\caption{{{caption}}}')
    latex_string.append(f'    \\label{{{label}}}')
    latex_string.append(r'\end{table}')
    return '\n'.join(latex_string)

# --- Main Counting Logic ---
lines_read = 0
records_processed = 0
errors_parsing = 0
plugin_counter = Counter()

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
                plugins_list = []
                serverless_config = data.get('serverless_config')
                # Handle both list and dict formats
                if isinstance(serverless_config, list):
                    for entry in serverless_config:
                        config = entry.get('config', {})
                        plugins = config.get('plugins', [])
                        if isinstance(plugins, list):
                            plugins_list.extend(plugins)
                        elif plugins:
                            logging.warning(f"Line {line_num}: 'plugins' field is not a list ({type(plugins)}). Skipping plugins for this entry.")
                elif isinstance(serverless_config, dict):
                    plugins = serverless_config.get('plugins', [])
                    if isinstance(plugins, list):
                        plugins_list.extend(plugins)
                    elif plugins:
                        logging.warning(f"Line {line_num}: 'plugins' field is not a list ({type(plugins)}). Skipping plugins for this record.")
                if plugins_list:
                    plugin_counter.update(plugins_list)
                    logging.debug(f"Line {line_num}: Found plugins: {plugins_list}")
            except json.JSONDecodeError:
                logging.error(f"Line {line_num}: Failed to decode JSON. Skipping line: {line.strip()[:100]}...")
                errors_parsing += 1
            except Exception as e:
                logging.exception(f"Line {line_num}: Unexpected error processing line. Error: {e}")
                errors_parsing += 1
            if lines_read % 5000 == 0:
                logging.info(f"Processed {lines_read} lines...")

    logging.info(f"Finished processing input file. Found {len(plugin_counter)} unique plugins.")

    if not plugin_counter:
        logging.warning("No plugins found in the input file. Cannot generate table.")
    else:
        effective_caption = TABLE_CAPTION
        if TOP_N_PLUGINS is not None and TOP_N_PLUGINS < len(plugin_counter):
            effective_caption = f'Top {TOP_N_PLUGINS} Serverless Framework plugins used in our dataset.'
        elif TOP_N_PLUGINS is None:
            effective_caption = 'All Serverless Framework plugins used in our dataset.'
        latex_output = generate_latex_table(plugin_counter, top_n=TOP_N_PLUGINS, caption=effective_caption, label=TABLE_LABEL)
        print("\n--- Generated LaTeX Table ---")
        print(latex_output)
        print("--- End Generated LaTeX Table ---\n")
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
    logging.info(f"Unique plugins found: {len(plugin_counter)}")
    logging.info(f"Errors parsing lines: {errors_parsing}")
    logging.info(f"Detailed logs saved to: {LOG_FILENAME}")