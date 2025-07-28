#!/usr/bin/env bash
#

url="https://api.github.com"

# Source the.env file if it exists, otherwise expect GITHUB_AUTH_TOKEN to be set
if [ -f ".env" ]; then
  source .env
fi
# Set token to your GitHub access token (public access)
token=${GITHUB_AUTH_TOKEN:-$token} # Use GITHUB_AUTH_TOKEN if set, else use token from.env
today=$(date +"%Y-%m-%d")

# --- Define Categories of Configuration Filenames to Search For ---

# Strategy 1 & 5: Serverless/Platform Configs
serverless_configs=(
    "serverless.yml"    # Serverless Framework
    "template.yaml"     # AWS SAM
    "template.yml"      # AWS SAM (alternative extension)
    "samconfig.toml"    # AWS SAM CLI config
    "function.json"     # Azure Functions
    "host.json"         # Azure Functions
    "stack.yml"         # OpenFaaS (Note: May yield some false positives)
    "service.yaml"      # Knative (Note: May yield many false positives)
    # Add other platform/framework specific files if needed
)

# Strategy 2: Security Artifact Filenames
security_configs=(
    ".checkov.yml"      # Checkov IaC Scanner
    "tfsec-config.yml"  # TFSec IaC Scanner config (less common filename, check variations)
    ".tfsec.yml"        # TFSec common config name
    ".snyk"             # Snyk config file
    # Add other security tool config filenames (e.g., Semgrep, Terrascan if common names exist)
)

# Strategy 3: Privacy Indicator Filenames
privacy_configs=(
    "PRIVACY.md"        # Common privacy policy filename (Note: Weak indicator alone)
)

# Strategy 4: AI/ML MLOps Tool Filenames
mlops_configs=(
    "MLproject"         # MLflow project file
    "dvc.yaml"          # DVC config file
    # Add other MLOps tool config filenames if common conventions exist
)

# Strategy 2/Implied: Common CI/CD Platform Config Filenames (Root level)
cicd_configs=(
    ".gitlab-ci.yml"    # GitLab CI/CD
    "azure-pipelines.yml" # Azure Pipelines
    "bitbucket-pipelines.yml" # Bitbucket Pipelines
    "Jenkinsfile"       # Jenkins Pipeline
    ".travis.yml"       # Travis CI
    "circle.yml"        # CircleCI (older format)
    # Note: GitHub Actions are usually in.github/workflows/, harder to target directly via filename search alone at root.
    # Could add common workflow names like 'main.yml', 'build.yml' but might be too noisy without path context.
)

# Combine all filename arrays into one for iteration
all_config_files=(
    "${serverless_configs[@]}"
    "${security_configs[@]}"
    "${privacy_configs[@]}"
    "${mlops_configs[@]}"
    "${cicd_configs[@]}"
)


# --- Define Parent Directory for the code search results ---
parent_dir="data/raw/code_search_$(date +"%Y%m%d_%H%M%S")" # Unique parent dir per run

# --- Define Subdirectories ---
results_dir="$parent_dir/results_by_filename" # More specific name
errors_dir="$parent_dir/errors"
logs_dir="$parent_dir/logs" # Separate logs directory

# --- Define Log File ---
log_file="$logs_dir/code_search_${today}.log"

# --- Dynamic Interval Parameters ---
lower_bound=0 # 0 bytes (adjust as needed, smaller files are more likely config files)
upper_bound=384000 # 384kB (adjust as needed, larger files may not be config files)
min_interval=20       # Starting and smallest interval
max_interval=100000     # Largest allowed interval (adjust as needed)
current_interval=$min_interval # Start with the minimum
# Thresholds for adjusting interval (adjust as needed)
low_results_threshold=900
high_results_threshold=900 # Consider decreasing if > this OR API limit hit


# --- Helper Functions ---

dependency_test()
{
  echo "Checking dependencies..."
  for dep in curl jq sed sort wc tr mkdir; do # Added mkdir
    if ! command -v "$dep" &> /dev/null; then
      echo -e "\nError: I require the '$dep' command but it's not installed.\n"
      exit 1
    fi
  done
  echo "All dependencies found."
}


token_test()
{
  if [ -z "$token" ]; then
    echo "Error: You must set a Personal Access Token to the GITHUB_AUTH_TOKEN environment variable or in a .env file."
    exit 1
  fi
  http_status=$(curl --silent --output /dev/null --write-out "%{http_code}" -H "Authorization: token $token" "$url/user")
  if [ "$http_status" -ne 200 ]; then
      echo "Error: GitHub token seems invalid or lacks permissions (HTTP status: $http_status)."
      echo "Warning: Proceeding potentially with reduced rate limits."
      token_cmd=""
  else
      echo "GitHub token validated."
      token_cmd="Authorization: token $token"
  fi
}

# Progress indicator
working() {
   echo -n "."
}

work_done() {
  echo -n "done!"
  echo -e "\n"
}

# Function to append results to the output file
output_list() {
    local current_filename=$1
    local size_range=$2
    local batch_array_name=$3
    local target_file=$4

    local items_ref="${batch_array_name}[@]"
    local items=("${!items_ref}")
    local count=${#items[@]}

    if [ "$count" -gt 0 ]; then
        echo "# Results for: $current_filename (size: $size_range)" >> "$target_file"
        printf '%s\n' "${items[@]}" >> "$target_file"
        echo "" >> "$target_file"
    fi
    echo $count # Return count
}

# Function to fetch repos for a specific filename
get_repos_for_file() {
  local current_filename=$1
  echo "--- Starting search for filename: $current_filename ---"

  # Define and Clear Specific Output File
  local base_filename="${current_filename}_results_${today}.txt"
  base_filename=$(echo "$base_filename" | sed 's/[^a-zA-Z0-9._-]/_/g') # Sanitize
  local specific_output_file="$results_dir/$base_filename"

  echo "Clearing/creating output file for this config: $specific_output_file"
  # Ensure directory exists before writing
  mkdir -p "$(dirname "$specific_output_file")"
  > "$specific_output_file"

  # Reset interval and start point for each file
  current_interval=$min_interval
  local i=$lower_bound

  while [[ $i -le $upper_bound ]]; do
    local hit_api_limit=0
    local batch_count=0
    local max_page=0

    local j=$((i + current_interval - 1))
    if [[ $j -gt $upper_bound ]]; then j=$upper_bound; fi
    if [[ $i -gt $j ]]; then
        echo "Warning: Calculated start $i exceeds end $j. Finishing search for $current_filename."
        break
    fi
    local size_range="$i..$j"
    echo "Searching size range: $size_range bytes (interval: $current_interval) for $current_filename"
    sleep 8 # API rate limit precaution

    local query="filename:$current_filename+size:$size_range"
    local api_endpoint="$url/search/code?q=$query&per_page=100"

    # Check Pagination
    local last_repo_page=$(curl --silent --head -H "$token_cmd" "$api_endpoint" | sed -nE 's/^link:.*page=([0-9]+)>; rel="last".*/\1/p')
    if [[ $? -ne 0 ]]; then
        echo "Error checking pagination for $current_filename size $size_range. Skipping range."
        i=$((i + current_interval))
        continue
    fi

    # Preemptive Retry Optimization
    local potential_max_page=${last_repo_page:-1}
    local requires_retry_immediately=0
    if [[ "$potential_max_page" -ge 10 ]]; then requires_retry_immediately=1; fi

    if [[ $requires_retry_immediately -eq 1 ]]; then
        echo "Optimization: Detected >= 10 pages needed for interval $current_interval (range $size_range)."
        local next_interval=$((current_interval / 2))
        if [[ $next_interval -lt $min_interval ]]; then next_interval=$min_interval; fi

        if [[ $next_interval -lt $current_interval ]]; then
            echo "Reducing interval to $next_interval and retrying range starting at $i immediately."
            current_interval=$next_interval
            continue # Skip fetching for the current wide interval
        else
            echo "Warning: >= 10 pages required, but interval is already at minimum ($min_interval). Proceeding to fetch results for $size_range (may be incomplete)."
            hit_api_limit=1
            max_page=10
        fi
    else
        max_page=$potential_max_page
        if [[ "$max_page" -gt 10 ]]; then max_page=10; fi
    fi

    # Proceed with fetching pages
    local repos_batch=() # Local array for the batch

    if [[ -z "$last_repo_page" ]] && [[ $requires_retry_immediately -ne 1 ]]; then
      # Single page
      echo "Fetching single page or no results for $current_filename size $size_range"
      sleep 8
      local response=$(curl --silent -H "$token_cmd" "$api_endpoint")
      if [[ $? -ne 0 ]]; then
          echo "Error fetching results for $current_filename size $size_range. Skipping range."
          i=$((i + current_interval))
          continue
      fi

      if ! echo "$response" | jq -e . > /dev/null 2>&1; then
          echo "ERROR: Invalid JSON received for $current_filename size $size_range PAGE 1. Skipping range."
          local error_base_filename="error_response_${current_filename}_${size_range}_page1_$(date +%s).json"
          local error_filepath="$errors_dir/$error_base_filename"
          echo "Saving invalid JSON to: $error_filepath"
          mkdir -p "$(dirname "$error_filepath")" # Ensure error dir exists
          echo "$response" > "$error_filepath"
          i=$((i + current_interval))
          continue
      fi

      local paginated_repos_str=$(echo "$response" | jq --raw-output 'if .items then .items[].html_url else empty end // empty')

      repos_batch=()
      while IFS= read -r line; do if [[ -n "$line" ]]; then repos_batch+=("$line"); fi; done <<< "$paginated_repos_str"
      if [[ ${#repos_batch[@]} -eq 0 ]]; then echo "No repositories found in this batch."; fi
      hit_api_limit=0

    elif [[ $max_page -gt 0 ]]; then
      # Multiple pages
      if [[ "$max_page" -eq 10 ]]; then hit_api_limit=1; fi
      echo "Fetching $max_page pages for $current_filename size $size_range"
      for (( k=1; k<=$max_page; k++ )); do
        working
        sleep 8
        local response=$(curl --silent -H "$token_cmd" "$api_endpoint&page=$k")
        if [[ $? -ne 0 ]]; then echo "Error fetching page $k for $current_filename size $size_range. Skipping page."; continue; fi

        if ! echo "$response" | jq -e . > /dev/null 2>&1; then
            echo "ERROR: Invalid JSON on page $k for $current_filename size $size_range. Skipping page."
            local error_base_filename="error_response_${current_filename}_${size_range}_page${k}_$(date +%s).json"
            local error_filepath="$errors_dir/$error_base_filename"
            echo "Saving invalid JSON to: $error_filepath"
            mkdir -p "$(dirname "$error_filepath")" # Ensure error dir exists
            echo "$response" > "$error_filepath"
            continue
        fi

        local paginated_repos_str=$(echo "$response" | jq --raw-output 'if .items then .items[].html_url else empty end // empty')

        local page_batch=()
        while IFS= read -r line; do if [[ -n "$line" ]]; then page_batch+=("$line"); fi; done <<< "$paginated_repos_str"
        if [[ ${#page_batch[@]} -gt 0 ]]; then repos_batch+=("${page_batch[@]}"); else echo "No repositories found on page $k."; fi
      done
      work_done
    fi # End fetching logic

    # Output results for this batch
    batch_count=$(output_list "$current_filename" "$size_range" "repos_batch" "$specific_output_file")
    if [[ "$batch_count" -gt 0 ]]; then
        echo "Appended $batch_count repository URLs for $current_filename (size: $size_range) to $specific_output_file"
    fi

    # Dynamic Interval Adjustment Logic
    local next_interval=$current_interval
    if [[ $batch_count -lt $low_results_threshold ]] && [[ $hit_api_limit -ne 1 ]]; then
        next_interval=$((current_interval * 2))
        if [[ $next_interval -gt $max_interval ]]; then next_interval=$max_interval; fi
        if [[ $next_interval -ne $current_interval ]]; then
            echo "Adjusting interval: Low results ($batch_count). Increasing interval for next search to $next_interval"
        fi
    # Optional: Add logic here to decrease interval if hit_api_limit was 1 and interval > min_interval
    elif [[ $hit_api_limit -eq 1 ]] && [[ $current_interval -gt $min_interval ]]; then
         next_interval=$((current_interval / 2))
         if [[ $next_interval -lt $min_interval ]]; then next_interval=$min_interval; fi
         if [[ $next_interval -ne $current_interval ]]; then
             echo "Adjusting interval: Hit API limit. Decreasing interval for next search to $next_interval"
         fi
    fi

    # Calculate Next Loop Start Point & Set Interval
    local interval_used_this_iteration=$current_interval
    i=$((i + interval_used_this_iteration))
    current_interval=$next_interval

  done # End while loop

  echo "--- Finished search for filename: $current_filename ---"
  echo ""
} # End function get_repos_for_file


#### MAIN

# Initial checks output to console
dependency_test
token_test

# Create directories first - this echo will go to console
echo "Ensuring directories exist: $results_dir, $errors_dir, and $logs_dir"
mkdir -p "$results_dir" "$errors_dir" "$logs_dir"

# Setup Log File Redirection
exec > "$log_file" 2>&1
echo "--- Log started at $(date) ---"
echo "Full log is being written to: $log_file"
echo "Results will be saved per-file in '$results_dir/'"
echo "Errors will be saved in '$errors_dir/'"

# Loop through each config file and fetch repos
# All output from this loop goes to the log file
for filename in "${all_config_files[@]}"; do
    get_repos_for_file "$filename"
done

# --- Post-processing: Combine, Deduplicate, and Filter URLs ---
# This part runs after the main loop, output goes to log file
combined_output_file="$parent_dir/combined_unique_results_${today}.txt"
echo "Combining results from '$results_dir/' into '$combined_output_file'..."

# Clear or create the combined file
> "$combined_output_file"

# Find all result files, concatenate them, filter only URLs, sort uniquely, and save
find "$results_dir" -name "*_results_${today}.txt" -type f -print0 | xargs -0 cat | grep '^http' | sort -u > "$combined_output_file"

if [[ $? -eq 0 ]]; then
    echo "Successfully combined, deduplicated, and filtered results into '$combined_output_file'."
    # Optional: Count unique URLs
    unique_count=$(wc -l < "$combined_output_file")
    echo "Total unique repository URLs found: $unique_count"
else
    echo "Error during combining/deduplicating results. Check individual files in '$results_dir/'."
fi
# --- End Post-processing ---


echo "--- Log finished at $(date) ---"
echo "All searches complete."

exit 0