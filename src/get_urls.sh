#!/usr/bin/env bash

url="https://api.github.com" # GitHub REST API base URL

# Source the .env file and set the GitHub token
if [ -f ".env" ]; then
  source .env
fi

if [ -z "$GITHUB_AUTH_TOKEN" ]; then
  echo "Error: GITHUB_AUTH_TOKEN is not set in your .env file."
  exit 1
fi

token="$GITHUB_AUTH_TOKEN"

today=$(date +"%Y-%m-%d") # Current date for filenames

# Filename-based code search
config_files=(
    "serverless.yml" # Serverless Framework
    # Add other platform/framework specific files if needed
)

# We define the base directory for the code search
parent_dir="data/raw/code_search_$(date +"%Y%m%d_%H%M%S")" # The timestamp guarantees uniqueness per run

# We define subdirectories for the code search results, errors, and logs
results_dir="$parent_dir/results_by_filename"
errors_dir="$parent_dir/errors"
logs_dir="$parent_dir/logs"

# Log file path
log_file="$logs_dir/code_search_${today}.log"

# To comply with GitHub API rate limits, we will implement dynamic interval adjustment, starting with a moderate interval and then adjusting based on results

# File size bounds (in bytes)
lower_bound=0 # 0 bytes (adjust as needed)
upper_bound=384000 # 384KB (current limit for searchable files, adjust as needed)

# Interval settings
min_interval=20 # Start with a small interval for file sizes (adjust as needed)
max_interval=100000 # Largest allowed file size interval (adjust as needed)
current_interval=$min_interval # Start with the previously defined minimum

# Thresholds for adjusting interval (adjust as needed)
low_results_threshold=900
high_results_threshold=900 # Consider decreasing if > this OR API limit hit

# Function to check for required dependencies
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

# Function to validate GitHub token
token_test()
{
  if [ -z "$token" ]; then
    echo "Error: You must set a Personal Access Token to the GITHUB_AUTH_TOKEN environment variable or in a .env file."
    exit 1
  fi
  http_status=$(curl --silent --output /dev/null --write-out "%{http_code}" -H "Authorization: token $token" "$url/user")
  if [ "$http_status" -ne 200 ]; then
      echo "Error: GitHub token seems invalid or lacks permissions (HTTP status: $http_status). Please check it and try again."
      exit 1
  else
      echo "GitHub token validated."
      token_cmd="Authorization: token $token"
  fi
}

# Progress indicators
working() {
  printf "Fetching page..."
}

work_done() {
  printf " done!\n"
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
  echo "Starting search for filename: $current_filename"

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
      # Single page results or no pagination
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
      # Multiple pages (up to 10)
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

    # Adjusting interval based on results
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

    # Calculate the next starting point
    local interval_used_this_iteration=$current_interval
    i=$((i + interval_used_this_iteration))
    current_interval=$next_interval

  done # End while loop

  echo "Finished search for filename: $current_filename"
  echo ""
} # End function get_repos_for_file


#### MAIN

# Initial checks output to console
dependency_test
token_test

# Create directories first - this echo will go to console
echo "Ensuring directories exist: $results_dir, $errors_dir, and $logs_dir"
mkdir -p "$results_dir" "$errors_dir" "$logs_dir"

# Setup log file - redirect all output from here on to the log file
exec > "$log_file" 2>&1
echo "Log started at $(date)"
echo "Full log is being written to: $log_file"
echo "Results will be saved per-file in '$results_dir/'"
echo "Errors will be saved in '$errors_dir/'"

# Loop through each config file and fetch repos
# All output from this loop goes to the log file
for filename in "${config_files[@]}"; do
    get_repos_for_file "$filename"
done

# Post-processing step: we combine, deduplicate, and filter results
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
# End of post-processing

echo "Log finished at $(date)"
echo "All searches complete."

exit 0