# OpenLambdaVerse: A Dataset and Analysis of Open-Source Serverless Applications

This repository contains the code and instructions for building the dataset and performing its characterization.

See the end of this README for citation instructions.

> **Note:** All development and testing was done on macOS. Depending on the specific operating system, some of these instructions/commands may need to be adjusted.

## Requirements
- Python 3.11.3 (also tested with Python 3.13.3)
- A GitHub account
- `jq` command-line tool  
    ```bash
    brew install jq
    ```
  - [Learn more about jq](https://stedolan.github.io/jq/)

## Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv env
   source env/bin/activate
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch a local instance of Jupyter Notebook:
   ```bash
   jupyter notebook
   ```

## About the `.env` File
The `.env_demo` file provides the environment variables required by the scripts, and their placeholder values should be changed to those that fit your implementation in an unversioned `.env` file.

### Environment Variables
- `GITHUB_AUTH_TOKEN`:  
  A token used to access the GitHub REST API.  
  GitHub recommends using a fine-grained personal access token instead of a classic personal access token.  
  Learn how to create a fine-grained personal access token: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token
- `CLONED_REPOS_DIRECTORY`:
  The directory where repositories will be cloned to.
- `CONFIG_FILES_DIRECTORY`:
  The directory where configuration files will be stored for quicker analysis on certain steps.
- `REPOS_SOURCE_DIRECTORY`:
  The directory where repositories can be sourced from using `scripts/copy_repos_from_broader_clone.py`.

## Methodology for Data Extraction
Based on Wonderless. The original implementation can be found [here](https://github.com/prg-grp/wonderless).
This implementation is also based on improvements introduced in OS<sub>3</sub>. Its implementation can be found [here](https://github.com/edgeumd/serverless_dataset).

### Code search
The `get_urls.sh` script performs a targeted code search on GitHub via its API, identifying repositories that contain specific serverless configuration files, such as:
- `serverless.yml`: (used by the Serverless Framework)

Additional configuration files can also be specified within the script.

**To run:**
1. Make the script executable:
   ```bash
   chmod +x src/get_urls.sh
   ```
2. Run the script:
   ```bash
   sh src/get_urls.sh
   ```

The results will be stored in the `data/raw/code_search_YYYYMMDD_hhmmss` directory, where:
   - `YYYY`: Year the search started  
   - `MM`: Month (zero-padded)  
   - `DD`: Day (zero-padded)  
   - `hh`: Hour (24-hour format)  
   - `mm`: Minute  
   - `ss`: Second

Inside the code search directory, you will find the following subdirectories:
1. `errors`: Contains JSON files that failed to parse, often due to improperly escaped special characters or malformed GitHub JSON responses.
2. `logs`: Stores a single `.TXT` file logging the entire process.
3. `results_by_filename`: Includes `.TXT` files listing URLs for each filename specified in the search configuration.

A combined results file containing all the URLs from the entire code search will also be available.

---

### Filtering out configuration files in test and demo directories
To clean up the initial set of file URLs and exclude those located in example, test, or demo directories, run the following script:

```bash
python src/filter_urls.py
```

#### Output
- **Filtered URLs**: The filtered results will be saved in `data/processed/code_search_YYYYMMDD_hhmmss/filtered_urls/filtered_urls.txt`
- **Logs**: Logs detailing the filtering process will be stored in `data/processed/code_search_YYYYMMDD_hhmmss/logs/url_filter_log.log`

#### Notes
- The script automatically identifies the latest `code_search_YYYYMMDD_hhmmss` directory and processes the corresponding results.
- It also does some cleaning of the previous output, keeping only valid URLs in the end (lines such as `# Results for:` are excluded).
- Ensure that the `data/raw` directory contains the results from the code search before running this script.

---

### Removing duplicates and generating unique repository URLs
To generate unique repository URLs by removing duplicates that arose from multiple `serverless.yml` files associated with the same repository, run the following script:

```bash
python src/generate_unique_repo_urls.py
```

#### Output
- **Unique Repository URLs**: The unique repository URLs will be saved in `data/processed/code_search_YYYYMMDD_hhmmss/unique_repo_urls/unique_repo_urls.txt`
- **Logs**: Logs detailing the deduplication process will be stored in `data/processed/code_search_YYYYMMDD_hhmmss/logs/base_url_extractor_log.log`

#### Notes
- The script automatically identifies the latest `filtered_urls.txt` file from the `data/processed/code_search_YYYYMMDD_hhmmss/filtered_urls/` directory.
- It extracts and deduplicates repository URLs, ensuring only unique base repository URLs are retained.
- Ensure that the `data/processed` directory contains the filtered URLs from the previous step before running this script.

---

### Removing Serverless Framework Contributions
To filter out projects belonging to the users `serverless` and `serverless-components`, run the following script:

```bash
python src/filter_serverless_repos.py
```

#### Output
- **Filtered Repository URLs**: The filtered repository URLs will be saved in `data/processed/code_search_YYYYMMDD_hhmmss/filtered_repo_urls/filtered_repo_urls.txt`
- **Logs**: Logs detailing the filtering process will be stored in `data/processed/code_search_YYYYMMDD_hhmmss/logs/filter_serverless_repos_log.log`

#### Notes
- The script automatically identifies the latest `unique_repo_urls.txt` file from the `data/processed/code_search_YYYYMMDD_hhmmss/unique_repo_urls/` directory.
- It filters out repositories owned by the users `serverless` and `serverless-components`.
- Ensure that the `data/processed` directory contains the unique repository URLs from the previous step before running this script.

---

### Fetching repository metadata
To gather metadata for each repository, run the following command:

```bash
python src/get_repos_metadata.py
```

#### Output
- **repository_metadata.jsonl**: Contains the extracted metadata for each repository in JSON Lines format.
- **extract_repo_metadata_log.log**: Log file detailing the metadata extraction process.

---

### Filtering unlicensed projects
To filter out repositories that do not have a valid license, run the following script:

```bash
python src/filter_unlicensed_repos.py
```

#### Output
- **Filtered licensed repositories**: The filtered repositories with a valid license will be saved in `data/processed/code_search_YYYYMMDD_hhmmss/results/licensed_repos.jsonl`
- **Logs**: Logs detailing the filtering process will be stored in `data/processed/code_search_YYYYMMDD_hhmmss/logs/filter_unlicensed_repos_log.log`

---

### Filtering forks, shallow, inactive, and toy projects

To ensure dataset quality, we apply a series of filters to remove repositories that are forks, shallow (small in size), inactive, or likely to be toy/example projects. Run the following scripts in order:

```bash
python src/filter_forked_projects.py
python src/filter_shallow_projects.py
python src/filter_inactive_projects.py
python src/filter_toy_projects.py
```

#### Inputs and Outputs

| Script                       | Input File                                               | Output File                |
|------------------------------|---------------------------------------------------------|----------------------------|
| filter_forked_projects.py    | results/licensed_repos.jsonl                            | results/filtered_no_forks.jsonl    |
| filter_shallow_projects.py   | results/filtered_no_forks.jsonl                                 | results/filtered_no_shallow.jsonl  |
| filter_inactive_projects.py  | results/filtered_no_shallow.jsonl                               | results/filtered_no_inactive.jsonl |
| filter_toy_projects.py       | results/filtered_no_inactive.jsonl                              | results/filtered_no_toy.jsonl      |

- **Logs:**  
  Each script produces a log file in `data/processed/code_search_YYYYMMDD_hhmmss/logs/`, named according to the script (e.g., `filter_forked_projects_log.log`).

---

### Filtering AWS-only projects

To retain only repositories that use AWS as their serverless provider, run:

```bash
python src/filter_non_aws_projects.py
```

#### Input
- `data/processed/code_search_YYYYMMDD_hhmmss/results/filtered_no_toy.jsonl`

#### Output
- **Filtered AWS Projects**:  
  `data/processed/code_search_YYYYMMDD_hhmmss/results/aws_provider_repos.jsonl`
- **Logs**:  
  `data/processed/code_search_YYYYMMDD_hhmmss/logs/filter_by_provider_log.log`

---

### Cloning repositories

To clone all filtered AWS repositories to your local machine (optionally to an external SSD by setting the `CLONED_REPOS_DIRECTORY` variable in your `.env` file), run:

```bash
python src/clone_projects.py
```

#### Input
- `data/processed/code_search_YYYYMMDD_hhmmss/results/aws_provider_repos.jsonl`

#### Output
- **Cloned Repositories**:  
  All repositories will be cloned into the directory specified by `CLONED_REPOS_DIRECTORY` in your `.env` file, or into `cloned_aws_repos` by default.
- **Logs**:  
  `data/processed/code_search_YYYYMMDD_hhmmss/logs/clone_aws_repos.log`

## CLOC
For code complexity analysis, install CLOC:

```bash
brew install cloc
```

Make sure to export your environment variables:
```bash
export $(cat .env | xargs)
```

Finally, run:
```bash
for d in "$CLONED_REPOS_DIRECTORY"/*/ ; do (cd "$d" && echo "$d" && cloc --vcs git); done >> cloc/cloc_output.txt
```

Output is saved on `cloc/cloc_output.txt`
You can then convert this output to CSV using:
```bash
python scripts/convert_loc_txt_csv.py
```

Then you can run the following notebooks to general additional CSV files for later:
- `notebooks/eda_loc_repos.ipynb` 
- `notebooks/eda_loc.ipynb` 

## Collecting configuration files
To make it easier to navigate through the SF config. files, run:
```bash
python scripts/move_config_files.py
```

## Preparing assets for the paper
### Tables
We generate LaTeX tables using:
```bash
python scripts/generate_code_table.py
python scripts/generate_plugins_table.py
python scripts/generate_runtimes_table.py
```

#### Outputs
- `paper/tables/language_bytes.tex`
- `paper/tables/plugin_counts.tex`
- `paper/tables/runtime_counts.tex`

### Figures
We run the following scripts to create additional CSV files to be used on the notebooks.

```bash
python scripts/generate_functions_counts.py
python scripts/generate_providers_runtimes.py
python scripts/generate_repo_metadata_counts.py
python scripts/generate_repo_sizes_detail.py
python scripts/generate_repo_topics_counts.py 
```
#### Outputs
- `csvs/events.csv`
- `csvs/runtimes.csv`
- `csvs/repo_metadata.csv`
- `csvs/repo_sizes_detail.csv`
- `csvs/repo_topics.csv`

After running these, we proceed to use additional notebooks to generate the images (executed in order):
- `notebooks/eda_functions_events_counts.ipynb`
- `notebooks/eda_functions_events_counts_loc_repos.ipynb` 
- `notebooks/eda_functions_events.ipynb` 
- `notebooks/eda_functions_runtimes.ipynb` 
- `notebooks/eda_github_repo_counts.ipynb` 
- `notebooks/eda_github_repo_sizes.ipynb` 
- `notebooks/eda_github_repo_topics.ipynb`

### Flowcharts
Use `notebooks/flowcharts.ipynb` to generate the flowchart images.

#### Outputs
- `paper/figs/flowchart`
- `paper/figs/flowchart_eda`
- `paper/figs/flowchart_eda.pdf`
- `paper/figs/flowchart.pdf`

# Additional analysis
Using pygount, we can gather additional code complexity measurements.

Make sure to export your environment variables:
```bash
export $(cat .env | xargs)
```

Then, run:
```bash
pygount --format=summary $CLONED_REPOS_DIRECTORY --format=cloc-xml --out=pygount/pygount_output.xml --verbose
```

## Yearly histogram
- `notebooks/eda_github_repo_creation_dates.ipynb`

---

Please cite as follows:

Ángel C. Chávez-Moreno and Cristina L. Abad. OpenLambdaVerse: A Dataset and Analysis of Open-Source Serverless Applications. _IEEE International Conference on Cloud Engineering (IC2E), to appear_. 2025.  

Link to code repository: [https://github.com/disel-espol/openlambdaverse](https://github.com/disel-espol/openlambdaverse).  
Link to dataset: [https://zenodo.org/records/16533581](https://zenodo.org/records/16533581).  
Link to pre-print: [https://arxiv.org/abs/2508.01492](https://arxiv.org/abs/2508.01492).  
